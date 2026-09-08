# FOLD-R アーキテクチャ v0.2

作成日: 2026-09-09。状態: **設計仮説**。`fold_memory.py` の既存FOLD二次形式カーネルは参照実装だが、本書で定義するFOLD-R、ニューラルWriter/Reader、GPUカーネル、言語モデル本体は未実装。

## 1. 設計目標

FOLD-Rは「TransformerのAttentionだけを別演算へ置換する」ことを目標にしない。長文LLMで支配的になり得る複数の費用を分離し、それぞれに役割を与える。

1. **長文Attention / KV cache**: 全履歴をトークン列として保持せず、長期情報を訂正可能な関係状態へ移す。
2. **Dense FFNの重み帯域**: 全トークンで巨大なDense MLPを必須にしない。小さな共有経路と条件付き計算を比較する。
3. **自己回帰生成の逐次性**: 正しさは1-token causal decodeで保ちつつ、multi-token prediction / speculative block decodeを独立した高速化層として評価する。
4. **動的グラフ演算のGPU非効率**: 任意サイズのグラフを毎token操作せず、固定形状にbucket化したcapsuleとchunk境界でのcommitを採用する。
5. **学習時のactivation/optimizer負荷**: FOLD-Rの推論上の省メモリと学習上の省メモリを混同せず、chunked training、checkpointing、truncated state gradientを別々に測る。

目標は「無限長を定数容量で完全記憶」ではない。**将来必要な問い合わせ・訂正の有効次元が小さい系列で、同等精度をより少ない総コストで維持できるか**を検証する。

## 2. 正規構成

```text
Token IDs
   │
Embedding
   │
┌──▼────────────────────────────────────────────┐
│ Local Context Mixer                           │
│ fixed causal window W                         │
│ baseline: short-window attention              │
│ ablation: recurrent / convolutional mixer     │
└──┬────────────────────────────────────────────┘
   │ h_t
   ├──────────────┐
   │              │
   │        Memory Controller / Writer
   │              │
   │        semantic operations
   │              ▼
   │        ┌──────────────┐
   │        │ H1 Hot Buffer │ recent, mutable, unfolded
   │        └──────┬───────┘
   │               │ chunk commit / pressure
   │               ▼
   │        Capsule Compiler
   │               │
   │               ▼
   │        ┌──────────────────┐
   │        │ H2 FOLD-R Bank   │ fixed-shape response capsules
   │        └────────┬─────────┘
   │                 │
   └──────────────► Reader
                     │ r_t + coverage status
                     ▼
              Context / Memory Fusion
                     │
                     ▼
              Conditional Compute
                     │
              ┌──────┴──────┐
              │             │
         Next-token head   MTP heads (optional)
```

**global full-history self-attentionは正規構成に含めない。** Local Context Mixerは固定窓Wのため、系列全長に比例してKVを保持しない。短期Attention自体を残すかどうかはアブレーションで決める。

## 3. 記憶階層

### H0: Local Context

直近W tokenだけを扱う。語順、構文、照応の途中状態など、関係メモリへ直ちに昇格させる必要がない局所情報を担当する。

- Wは固定。
- full-context attentionへの自動fallbackは禁止。fallbackを実験する場合は別条件とする。
- decode時のH0 state / KVはWに上限を持つ。

### H1: Hot Relational Buffer

最近生成された記憶操作を、まだ縮約せず保持する可変領域。

目的:

- 文を読み終える前の早すぎる圧縮を防ぐ。
- 直後に起こる訂正・取消しを安価に扱う。
- GPUへ不規則な1件ずつのgraph mutationを投げず、chunk単位へまとめる。

H1は容量・滞在token数に上限を持つ。上限超過時は無条件に捨てず、commit、capsule分割、保持延長、coverage低下のいずれかを明示的に選ぶ。

### H2: FOLD-R Capsule Bank

長期記憶の本体。各capsuleは「何でも読める圧縮グラフ」ではなく、**保護する読み出し方向Qと訂正方向Uを契約として持つ応答関数**である。

二次形式

$$
E(z)=\frac12z^T Jz-\eta^Tz
$$

に対し、読み出しを`Qz`、許可する低ランク訂正を

$$
J'=J+UWU^T,\qquad \eta'=\eta+Ub
$$

とする。圧縮時に

$$
y_0=QJ^{-1}\eta,\quad g=U^TJ^{-1}\eta,
$$

$$
V=QJ^{-1}U,\quad K=U^TJ^{-1}U
$$

を保持すれば、対象範囲内の訂正後読み出しは

$$
y(W,b)=y_0+V(I+WK)^{-1}(b-Wg)
$$

で求める設計とする。

この低ランク更新・線形代数自体を新規性として主張しない。研究対象は、**Q/Uを因果的に学習し、訂正列への応答と総コストの両方から保護範囲を決めること**である。

## 4. Capability Contract

各capsuleは、圧縮データだけでなく次を持つ。

```text
capsule_id
shape_bucket
read_port_descriptor      # Qの表現
update_port_descriptor    # Uの表現
protected_factor_ids      # 撤回可能性を残す対象の最小索引
scope / epoch
numerical_condition_meta
coverage_policy
```

Reader/Writerは、操作が保護範囲内かを判定する。

- **SUPPORTED**: capsuleだけで規定精度の処理が可能。
- **HOT_REQUIRED**: H1の未縮約情報が必要。
- **OUT_OF_SCOPE**: 既に捨てた方向が必要で、現在状態だけでは正答を保証できない。
- **NUMERIC_UNSAFE**: 正定値性・条件数・solve失敗などで保証を出せない。

`OUT_OF_SCOPE`を0や「存在しない」と解釈しない。未知・未保持と事実上の否定を区別する。

この契約は、圧縮した記憶が何を保証しているかを観測可能にするための設計要件である。

## 5. 記憶操作の正規語彙

Writerが生成する内部操作は最低限、次を区別する。

```text
ASSERT(factor_id, scope, relation)
RETRACT(factor_id)
REPLACE(factor_id, new_relation)
ASSUME(scope_id, relation)
END_SCOPE(scope_id)
QUERY(read_request)
```

同じentityへ別値が来たことを自動的なREPLACEとみなさない。引用、仮定、過去時刻、現在の事実をscopeで分離する。

自然言語からこれらの操作へ変換する部分は学習対象であり、FOLD-Rの数値カーネルが解決する問題ではない。

## 6. Capsule CompilerとGPU制約

FOLD-Rが理論上FLOPsを削減しても、不規則な小行列演算でGPU利用率を失えば失敗である。正規実装は次を要求する。

### 6.1 固定shape bucket

capsuleの`q = rows(Q)`と`r = cols(U)`を少数のbucketへ量子化する。例として`r ∈ {4, 8, 16, 32}`のような候補を実験するが、値は性能測定で決める。

- per-tokenの動的mallocを避ける。
- 同shapeのsolve/updateをbatch化する。
- paddingによる無駄も計測する。

### 6.2 Chunk commit

Writer操作はH1へ蓄積し、C tokenごと、またはpressure条件でまとめてcompileする。

- decodeのcritical pathで大規模Schur補完を毎token実行しない。
- commit latencyとstalenessを両方測る。
- queryが未commit情報を必要とする場合はH1とH2を合成して読む。

### 6.3 逆行列を形成しない

Cholesky / linear solveを基本とし、明示的`inverse()`を正規経路にしない。近似solve、低精度、sparsificationはexact modeと分離する。

### 6.4 Fill-in budget

縮約によりnnzやcapsule rankが増えすぎる場合、compilerは無条件に圧縮しない。

候補:

- capsuleを分割する。
- H1滞在を延長する。
- 一部方向を非保証として落とす。ただしcoverage低下を記録する。
- 近似sparsificationを使う場合はexact実験と混ぜない。

## 7. Local Context Mixer

長期記憶をFOLD-Rへ移しても、局所的な言語処理は必要である。

正規baselineは**固定窓のcausal local attention**とする。理由は、まずFOLD-Rの効果を既知の安定した局所処理から切り分けるため。

同じtokenizer、hidden size、学習予算で以下を比較する。

1. local attention
2. gated recurrence
3. causal convolution / state mixer

FOLD-Rの成功条件を「local mixerまで新規であること」には置かない。最終的にattention-free構成を試すのは、長期記憶の価値が確認された後とする。

## 8. Dense FFNボトルネックへの方針

FOLD-RがKV/long attentionを削減すると、decode時のDense FFN weight bandwidthが相対的に支配的になる可能性がある。

v0.2では二段階で扱う。

### Baseline FFN

通常のSwiGLU系Dense FFN。まず記憶アーキテクチャの効果を分離する。

### Conditional Compute候補

FOLD-R有効性確認後に、以下を独立アブレーションする。

- 小さなshared trunk
- top-k / top-1 expert path
- low-rank expert adapter
- active parameter / tokenを固定予算として評価

「総parameter数」ではなく、decode時に実際に読み出すweight bytes/token、実測帯域、latencyを記録する。MoE等の既存原理をFOLD-R固有の新規性として扱わない。

## 9. 自己回帰逐次性への方針

正規の意味論はcausal next-token generationとし、FOLD-Rの正しさをmulti-token高速化に依存させない。

高速化層として、複数future tokenを予測するMTP headsを追加可能にする。

```text
shared hidden
  ├─ head +1  # 必須
  ├─ head +2  # 補助
  ├─ head +3
  └─ head +4
```

学習ではnext-token CEを主目的に保ち、MTPは補助損失。推論ではdraft / verify方式やblock acceptanceを別実験とする。

測定:

- accepted tokens / forward
- tok/s
- p50/p95 latency
- 品質差
- FOLD-R state更新を1tokenずつ行う場合とblock commitする場合の整合性

## 10. ニューラル部品

最小LLMは次の学習可能部品を持つ。

```text
Tokenizer / Embedding        # 標準部品
Local Mixer                  # 短期
Writer                       # h_t -> memory operations
Port Selector                # read/update capability selection
Capsule Router               # どのH1/H2を読む・書くか
Reader                       # memory -> r_t
Fusion                       # h_t + r_t
FFN / Conditional Compute    # 表現変換
LM Head                      # next-token
MTP Heads                    # optional
```

Writer、Port Selector、Capsule Router、ReaderがFOLD-R固有の主要研究対象。

## 11. 学習目的

基本損失を

$$
L = L_{next}
+\alpha L_{op}
+\beta L_{read}
+\gamma L_{correction}
+\delta L_{coverage}
+\lambda L_{cost}
+\rho L_{mtp}
$$

の形で比較する。

- `L_next`: 次token予測。
- `L_op`: 構造化実験での正しいASSERT/RETRACT/REPLACE等。
- `L_read`: query応答。
- `L_correction`: 訂正列適用後の応答差。
- `L_coverage`: 保証外操作をSUPPORTEDと誤判定することへの罰則。
- `L_cost`: capsule bytes、rank、solve、routing、H1滞在量等の明示的費用。
- `L_mtp`: optional multi-token補助損失。

すべてを最初から同時に学習しない。段階実験で必要性を検証してから追加する。

未来のquery/updateをPort Selector入力へ漏らさない。未来操作は教師信号としてのみ使用する。

## 12. 訂正閉包テスト

FOLD-Rの中心評価は、単一queryではなく操作列に対する整合性とする。

```text
full memory + edit_1 + edit_2 + ... + edit_k -> answer A

compress first
  -> capsule
  -> edit_1 + edit_2 + ... + edit_k
  -> answer B
```

保護範囲内ならA/Bが規定誤差内で一致することを要求する。

最低限の系列:

- ASSERT -> QUERY
- ASSERT -> REPLACE -> QUERY
- ASSERT -> RETRACT -> QUERY
- ASSERT -> REPLACE -> RETRACT -> QUERY
- 仮定scopeの開始/終了
- 訂正後に新しい関係を追加
- 現在は無関係だが、後続relationで必要になる情報

正解portを教師が与えた結果と、因果的に学習したportの結果を分離して報告する。

## 13. 計測する総コスト

FOLD-Rが既存のボトルネックを別の場所へ移しただけかを検出するため、少なくとも次を記録する。

### 推論

- TTFT / prefill throughput
- decode tokens/s
- p50 / p95 token latency
- peak VRAM / RSS
- H0 bytes
- H1 bytes
- H2 capsule bytes
- provenance/index bytes
- active weight bytes/token
- capsule route数/token
- solve数、matrix shape、batch size
- GPU utilization / kernel launch数
- padding waste
- MTP acceptance rate

### 学習

- tokens/s
- peak VRAM
- parameter / gradient / optimizer state bytes
- activation bytes
- recomputation cost
- communication time（multi-GPU時）
- total training FLOPsの推定とwall-clock

原グラフや全文replay archiveを保持するモードでは、その保存量を必ず別項目で計上する。archiveを隠して「定数メモリ」と主張しない。

## 14. 非目標と安全弁

現段階では次を保証しない。

- 任意の自然言語を正しいfactorへ変換できること。
- 任意の過去情報を圧縮後に復元できること。
- 一般的な論理・因果推論の完全性。
- Transformerより高速・高精度であること。
- GPU上で理論FLOPs削減が実時間短縮になること。
- Dense FFN、MTP、FOLD-Rを同時導入すれば相乗効果が出ること。

各最適化は独立アブレーションし、改善しないものは正規構成から外す。

## 15. v0.2の新規性候補

新規性を主張する候補は、既知の線形代数や既知のMoE/MTPではない。

> **因果的な言語ストリームから、将来のquery/edit utilityと実測コストを基に低次元のread/update capabilityを学習し、そのcapabilityの範囲内では訂正列への応答を代数的に保存するrecurrent relational memory。さらに各圧縮状態が、何を保証できるかをCapability Contractとして明示する。**

この組み合わせの完全な先行研究調査は継続事項であり、同等方式が既発表でないことは現時点では断定しない。

## 16. 実装優先順位

1. FOLD-R response capsuleのfloat64参照実装と訂正列テスト。
2. `MemoryOp` / scope / factor IDの意味論固定。
3. PyTorchで固定Q/Uの微分可能capsule。
4. oracle Writer/Readerで構造化系列を学習。
5. H1 + H2、chunk commit、Capability Contract。
6. 学習するWriter/Router/Port Selector。
7. 小型LM + fixed local mixer。
8. GPU shape bucket / batched solve。
9. Dense FFN対conditional computeのアブレーション。
10. MTP / speculative decodeのアブレーション。
11. Transformer / SSM / recurrent baselineとの同予算比較。

**長期記憶、Dense compute、decode逐次性を同時に発明しない。まずFOLD-R固有部分を成立させ、その後に残った実測ボトルネックだけを置換する。**
