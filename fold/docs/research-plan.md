# FOLD-R 実験計画 v0.2

更新日: 2026-09-09。本文のP1以降は計画であり、実施済みの結果ではない。

## 検証する中心仮説

**将来の問い合わせ・訂正が持つ有効次元が小さい系列では、因果的に学習したread/update capabilityを応答capsuleへ圧縮することで、長期履歴をtoken/KVとして保持する方式より少ない総コストで、同等の予測・訂正性能を維持できる。**

次は仮説に含めない。

- 任意の文章が小さなcapabilityを持つ。
- Schur補完や低ランク更新だけでTransformerに勝てる。
- capsule本体が小さければ、システム全体のメモリも小さい。
- 理論FLOPsが少なければGPU実時間も短い。
- conditional computeやMTPを追加すれば必ず高速化する。

正規構成は [architecture-v0.2.md](architecture-v0.2.md)。

## P0: FOLD v0.1数学カーネル（実装済み）

実装:

- float64二次形式メモリ
- 重み付き関係追加
- 直接求解
- Schur補完
- 元メモリを使った条件付き解の検証
- 数値payload集計

受け入れ済み:

- 単体テスト28件通過
- 固定seed 100ケースで境界解とprofile energyが絶対誤差1e-10以内
- 消去済み内部への更新を拒否
- 古い要約では内部更新を反映できない反例
- fill-in反例

数値結果は`../results/`。これはFOLD-Rや言語モデルの成功判定ではない。

## P1: FOLD-R response capsule参照実装

### 目的

v0.1の「消した内部を訂正できない」という制約を、保護したread/update方向の範囲内で解消する。

### 実装

float64 CPU参照実装として、Q/Uを教師から与える。

保持量:

$$
y_0=QJ^{-1}\eta,\quad g=U^TJ^{-1}\eta,
$$

$$
V=QJ^{-1}U,\quad K=U^TJ^{-1}U.
$$

訂正:

$$
J'=J+UWU^T,\qquad \eta'=\eta+Ub
$$

読み出し:

$$
y(W,b)=y_0+V(I+WK)^{-1}(b-Wg).
$$

逆行列を正規実装として形成せず、solveで検証する。

### 必須テスト

- 単一更新
- 複数更新の累積
- 追加 -> 撤回
- 置換
- 訂正順序の同値性が成立する条件
- 正定値性を壊す更新の拒否
- U外の更新をSUPPORTEDと誤判定しない
- Q外のqueryをSUPPORTEDと誤判定しない
- 数値条件の悪い系

### 合格条件

full memoryへ同じ訂正列を適用した結果と、capsuleだけへ適用した結果が規定誤差内で一致する。保証範囲外の操作は明示的statusで返す。

## P2: MemoryOpとCapability Contract

### 目的

数値更新と自然言語上の意味を混同しないため、内部操作の意味論を固定する。

最低操作:

```text
ASSERT(factor_id, scope, relation)
RETRACT(factor_id)
REPLACE(factor_id, new_relation)
ASSUME(scope_id, relation)
END_SCOPE(scope_id)
QUERY(read_request)
```

Capability status:

```text
SUPPORTED
HOT_REQUIRED
OUT_OF_SCOPE
NUMERIC_UNSAFE
```

### 必須仕様

- factor IDの再利用禁止またはversion規則
- ASSERTとREPLACEの明確な区別
- 仮定scopeと現在事実の分離
- 引用・別話者・別時刻を同一stateへ無条件に上書きしない
- OUT_OF_SCOPEを不存在として扱わない
- provenance/index bytesをコスト計測に含める

### 合格条件

構造化入力だけで追加・撤回・置換・scope分離を決定論的に再現でき、曖昧な操作を暗黙変換しない。

## P3: 微分可能カーネル（固定Q/U）

### 目的

FOLD-Rの連続パラメータを学習経路へ接続する。

### 実装

PyTorch等で、固定shape・固定Q/Uのcapsuleを実装する。

先にCPU float64で参照実装とforward一致を確認し、その後autogradを有限差分と比較する。

### 合格条件

独立3 seedで:

- forwardが参照実装と規定誤差内
- gradientが有限
- finite-differenceとautogradが一致
- held-out structured query lossが学習で改善

正解Q/Uを与えた結果を「記憶管理を学習した」と呼ばない。

## P4: H1 Hot Buffer + H2 Capsule Bank

### 目的

per-tokenの動的graph mutationを避け、最近の可変情報と長期圧縮情報を分離する。

### 実装

- H1容量上限
- chunk commit
- H1/H2の合成read
- capsule split
- fill-in / rank budget
- Capability Contract
- factor/provenance最小索引

### 検証

chunk長Cを複数比較し、以下を記録する。

- commit latency
- query staleness
- H1 bytes
- H2 bytes
- index bytes
- capsule数
- q/r rank分布
- fill-in
- OUT_OF_SCOPE率

### 合格条件

未commit情報を含むqueryで正答率を落とさず、per-token immediate compileより総実時間またはkernel launch数を改善する候補を示せること。改善しない場合はchunk commitを正規化しない。

## P5: Writer / Reader / Router / Port Selectorを学習

### データ

最初は自動生成された構造化系列。

例:

```text
ASSERT
RELATION
QUERY
REPLACE
QUERY
RETRACT
QUERY
```

学習系列長候補: 16 / 32 / 64操作。
評価: 16 / 32 / 64 / 128 / 256操作。

### 学習対象

- Writer: relationとMemoryOp
- Router: 対象H1/H2 capsule
- Reader: query readout
- Port Selector: Q/U capability
- coverage classifier

### 損失候補

$$
L = L_{query}
+\alpha L_{op}
+\beta L_{correction}
+\gamma L_{coverage}
+\lambda L_{cost}.
$$

未来のquery/editをPort Selector入力へ漏らさない。未来操作は教師信号としてのみ使う。

### 評価課題

- 関係合成
- 同名の別時刻
- 観測追加と置換
- 仮定scope
- 長い訂正列
- 現在は無関係だが後続relationで必要になる情報
- 独立ランダム事実
- capsule capability外のquery/update

### 合格条件

oracle Q/Uなしで、縮約なし同予算baselineに対する精度・総コスト差を測定できること。境界/rank肥大、coverage failure、再保持量も隠さない。

## P6: 小型言語モデル

### 正規baseline構成

```text
Tokenizer / Embedding
Fixed-window causal local attention
Writer / H1 / H2 / Reader
Fusion
Dense SwiGLU FFN
LM Head
```

ここでは**global full-history attentionを使わない**。

FOLD-Rの効果を切り分けるため、Local MixerとDense FFNはまず既存の安定した部品を使う。

### データ段階

1. 構造化系列の文章化
2. 合成短文・物語
3. 小規模一般コーパス

### 評価

- next-token loss / perplexity
- structured query accuracy
- correction-chain accuracy
- long-context extrapolation
- OUT_OF_SCOPE calibration
- TTFT
- prefill throughput
- decode tok/s
- peak VRAM/RSS

### 必須比較

- full-attention Transformer
- fixed-window local-attention only
- recurrent/SSM baseline
- FOLD-Rなし同Local Mixer
- FOLD v0.1型で訂正portなし
- oracle Q/U FOLD-R
- learned Q/U FOLD-R

同一tokenizer、可能な限り同じparameter / training-token / FLOP予算を使う。完全一致できない場合はPareto曲線として報告する。

## P7: GPU向け固定shape capsule

### 目的

数学的FLOPs削減が不規則GPU処理で相殺されないか確認する。

### 実装候補

- q/r shape bucket
- batched Cholesky / solve
- preallocated buffers
- chunk commit queue
- capsule grouping

### 記録

- solve shapeごとのbatch size
- kernel launch数/token
- GPU utilization
- HBM traffic推定またはprofiler値
- padding waste
- p50/p95 latency
- CPU/GPU synchronization回数

### 合格条件

参照実装より理論FLOPsが少ない、ではなく、対象GPUでwall-clockまたはthroughput改善を示すこと。

## P8: Dense FFNボトルネックのアブレーション

FOLD-Rでlong attention/KVを削った後、実測でDense FFN weight bandwidthが主要ボトルネックになった場合のみ着手する。

比較:

1. Dense SwiGLU
2. 小shared trunk + top-k expert
3. low-rank expert adapter

記録:

- total params
- active params/token
- weight bytes/token
- decode latency
- quality
- routing overhead

MoE等の既知方式をFOLD-R固有の新規性として扱わない。

## P9: 自己回帰逐次性のアブレーション

FOLD-Rの意味論は1-token causal decodeで固定し、MTPを独立高速化として追加する。

比較:

- next-token only
- +2 / +3 / +4 MTP heads
- draft/verifyまたはblock acceptance

記録:

- accepted tokens/forward
- tok/s
- latency
- quality
- FOLD-R state updateとの整合性

MTPが品質またはstate整合性を悪化させる場合、正規構成へ入れない。

## P10: 学習・システム総コスト

推論だけ速くても、大規模学習が成立しなければLLMアーキテクチャとして不十分である。

### 学習計測

- tokens/s
- peak VRAM
- parameter bytes
- gradient bytes
- optimizer-state bytes
- activation bytes
- recomputation
- multi-GPU communication time
- total training FLOPs推定
- wall-clock

### 比較する学習方式

- full BPTT相当
- chunked recurrence
- activation checkpointing
- truncated state gradient

意味が変わる方式は別実験にする。

## 必須アブレーション一覧

- FOLD-R on/off
- H1 on/off
- chunk commit vs immediate commit
- exact capsule vs approximate/sparse capsule
- oracle Q/U vs learned Q/U
- Capability Contract on/off
- local attention vs recurrent/conv mixer
- Dense FFN vs conditional compute
- next-token only vs MTP

複数変更を同時に有効化した結果だけで、どの要素が効いたかを結論しない。

## 成功判定

FOLD-Rの中心仮説については、**同程度の予測・訂正精度で総コストが下がること**を成功条件とする。

総コストには最低限:

- H0/H1/H2
- index/provenance
- routing
- solve
- model weights
- active weight traffic
- peak memory
- latency / throughput

を含める。

全文replay archiveや元グラフを保持する評価では、その保存量を隠さない。

失敗結果も重要である。特に、Q/U rankが系列長とともに増える、OUT_OF_SCOPEが高い、GPU utilizationが低い、Dense FFNが支配的、学習が不安定、という結果は中心仮説の適用範囲を定める。

## 現在地

- **P0: 実装・検証済み**
- **P1以降: 未実装**

次の実装対象はP1のFOLD-R response capsule参照実装とする。
