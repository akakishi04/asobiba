# FOLD v0.5 理論仕様 — 状態更新・圧縮・適応計算・情報取得

更新日: 2026-09-10。

**状態: `architecture-v0.5.md` を実装可能な数理仮説へ落とすための正規ブリッジ。以下は研究仮説・設計契約であり、実装済み・性能実証済みを意味しない。**

## 1. 中心研究仮説

最終構想の中心を次で表す。

> **課題に必要な状態更新を、共有された高精度コアと低容量の処理部品コードで表し、反復後の最終品質まで保つよう学習する。さらに、追加計算より外部情報の取得が有効な場面では、制御器が検索・観測・質問へ切り替える。**

この仮説は「再帰」「量子化」「MoE」「外部記憶」のどれか一つの採用を成果としない。評価対象は、**同じ総保存容量・実行費用に対して実際の課題解決能力が改善するか**である。

## 2. 最適化問題

最終モデルを単一のパラメータ数で評価しない。概念上の学習目的を、

$$
J = \mathbb{E}[L_{task}]
+ \lambda_R R_{storage}
+ \lambda_C C_{compute}
+ \lambda_A C_{acquire}
+ \lambda_U C_{update}
$$

と考える。

- `L_task`: 言語生成、推論、指示追従、訂正、情報取得後の最終課題損失。
- `R_storage`: 辞書、コード、scale、補正、設定、必要な入出力資産を含む保存量。
- `C_compute`: active FLOPsだけでなく、復号、routing、kernel launch、転送、反復による実時間を含む。
- `C_acquire`: 検索・観測・ユーザー質問の時間、往復、課金、ユーザー負担。
- `C_update`: 学習・再学習・コード再割当・教師生成に必要な実時間とRAM/VRAM。

ただし、この重み付き和だけで最終採用を決めない。低品質でも費用が安ければ勝てるため、**品質、coverage、latency、peak VRAM、ローカル更新可能性には別のhard gateを置き、Pareto frontierで比較する。** `lambda` を調整して未達を成功扱いにしない。

## 3. 二つの時間軸

モデル内部では、外部から証拠が増える時間と、同じ証拠を使って考える時間を分離する。

- `t`: evidence time。ユーザー入力、検索結果、画像観測、ツール結果など、外部証拠が追加されたときだけ進む。
- `k`: internal step。同じ証拠集合のまま内部計算を反復するときに進む。

状態を概念上、

$$
S_{t,k} = (X_t, H_{t,k}, M_t, G_{t,k}, B_{t,k})
$$

とする。

- `X_t`: 現在利用可能な入力と根拠参照。内部反復だけでは増やさない。
- `H_{t,k}`: 複数slotを持つ作業状態。
- `M_t`: 記憶。FOLD-R、可変記憶、原文参照など。
- `G_{t,k}`: 未解決の依存、不足情報、矛盾、仮説の状態。
- `B_{t,k}`: 計算・取得の残予算。

### 不変条件

1. `k` だけ進んでも、新しい観測事実を `X_t` へ追加しない。
2. 内部で生成した仮説を、外部証拠と同じ provenance で記録しない。
3. 長期記憶への確定commitは、内部状態更新とは別の境界で行う。
4. 取得失敗、検索0件、`OUT_OF_SCOPE` を「存在しない事実」へ変換しない。

## 4. 状態更新コア

一回の内部計算を、最初の候補として次の形で扱う。

$$
Z_{t,k} = Mix(H_{t,k}, X_t, Read(M_t), G_{t,k})
$$

$$
H_{t,k+1} = H_{t,k}
+ g_{t,k} \odot \left(
F_{shared}(Z_{t,k})
+ \sum_{j \in A_{t,k}} \alpha_{j,t,k} F_j(Z_{t,k})
\right)
$$

- `F_shared`: 常時通る共有状態更新コア。
- `F_j`: 選択可能な処理部品。
- `A_{t,k}`: そのstepで選んだ少数の部品集合。
- `alpha`: 部品の混合係数。top-k等の疎な選択を候補とする。
- `g`: どの状態成分を更新するかのgate。

これは最終式ではなく、実装・比較を始めるための参照形である。Attention、SSM、MLP等を内部に使うことは許容する。目的は既存演算を禁止することではなく、**固定された巨大な層列を最終構造の前提にしないこと**である。

### 作業状態

`H` は単一vectorに限定せず、`n_slot x d_state` の小さな作業領域を第一候補にする。各slotへ人間が意味ラベルを固定しない。意味の分化が必要なら学習結果として検証する。

## 5. 圧縮処理部品の理論

各処理部品を、自由なDense重みとして保存する代わりに、共有基底と離散コードから構成する。

ブロック `b` を持つ部品 `j` の重みを、

$$
W_{j,b} = W^{base}_{g(j),b}
+ \sum_{q=1}^{Q} D_{g(j),b,q}[c_{j,b,q}]
+ E_{j,b}
$$

と表す候補を採る。

- `W_base`: 同じ役割/shapeの部品で共有する基本変換。
- `D`: 学習可能な重みパターン辞書/codebook。
- `c`: 部品・ブロックごとの離散index。
- `E`: 圧縮で壊れやすい箇所だけに許す追加補正。

`D` の複数項の和で一つのblockを表す additive quantization を有力候補とする。AQLMは関連する先行研究だが、本構造全体の性能を保証するものではない。

### 正規の容量計上

$$
R_{storage} = bits(W^{base}) + bits(D) + bits(c) + bits(scales) + bits(E) + bits(metadata)
$$

を最低限計上する。

次を禁止する。

- 共有重みを反復回数だけ「独立パラメータ」として数える。
- codeから復号できるDense要素数を、自由な連続学習値の数と同一視する。
- 辞書・scale・補正・metadataを除外して平均bit数を出す。
- 推論時に全てを高精度Denseへ展開・常駐させ、配布ファイルだけを小さく見せる。

報告では `independent continuous scalars`、`discrete code bits`、`decoded/effective elements`、`serialized bytes` を分ける。

## 6. 圧縮誤差と反復安定性

一回だけ精度のよい部品でも、反復で誤差が増幅する可能性がある。高精度参照経路と圧縮経路の状態差を `e_k` とし、一回の更新が既存誤差を最大 `a_k` 倍、新しい圧縮誤差を `delta_k` 加えると仮定すれば、

$$
\|e_{k+1}\| \le a_k\|e_k\| + \delta_k
$$

となる。

一定 `a` の単純化では、

$$
\|e_K\| \le \delta\sum_{i=0}^{K-1} a^i
$$

である。これは実モデルのglobal Lipschitz定数を証明する式ではない。**反復後の誤差を測る必要性を示す設計上の上界**として使う。

### 実装時に測るもの

- 1-stepの状態差・部品出力差。
- 2/4/8/... step後の状態差と最終課題損失。
- 小さな入力摂動に対する経験的な増幅率。
- 圧縮によりrouting・停止・情報取得の選択が変わる割合。
- 補正 `E` を追加したときの品質改善 / byte。

単純にスペクトルノルムを小さくすることを目的にしない。情報保持まで消える可能性があるため、安定性regularizerは課題品質とセットで評価する。

## 7. 制御器 — 計算と情報取得を同じ行動空間で扱う

制御器の候補行動を、最低限次に分ける。

```text
ANSWER
PARTIAL_ANSWER
COMPUTE(module_set, steps)
READ_MEMORY(query)
RETRIEVE(source/query)
OBSERVE(target)
ASK_USER(requested_information)
STOP_UNRESOLVED
```

実際の外部アクセス権限はruntime側で管理し、モデルの選択だけで増やさない。

行動価値は概念上、

$$
Q(S,a) = \mathbb{E}[U_{final}\mid S,a]
- cost_{compute}(a)
- cost_{acquire}(a)
- cost_{user}(a)
$$

と考える。`U_final` は最終回答の品質・coverageを含む。

「追加情報の量」や「自信が増えたこと」自体を報酬にしない。**行動後に課題が実際に改善したか**を評価する。

### 不足情報を学習するための対課題

情報取得の必要性を教師できるよう、同じ可視入力に対して隠れた条件だけが異なる対課題を作る。

- 条件Aなら答えX、条件Bなら答えY。
- 可視入力だけではA/Bを識別不能。
- 一つの観測・質問で区別可能。

この条件では、内部計算を増やすだけでは新情報は得られない。対照として、欠落項目が結論に影響しない課題も用意し、不要質問を罰する。

学習では正解の隠れ条件をモデル入力・検索索引へ漏らさない。

## 8. FOLD-Rとの接続

FOLD-Rは全記憶を置き換えるものではなく、**保護する問い合わせ `Q` と訂正方向 `U` の範囲で応答を圧縮する装置**として使う。

- Writer: 自然言語・観測からMemoryOpへ変換。
- Port selector: 保護すべきread/update方向を選択。
- FOLD-R kernel: 指定された数値契約を実行。
- Coverage classifier: `SUPPORTED / HOT_REQUIRED / OUT_OF_SCOPE / NUMERIC_UNSAFE` を区別。

未来のqueryや正解操作は教師信号には使えるが、write時点の入力へ混ぜない。Writerが意味を誤った場合、数値kernelが正確でも課題としては失敗とする。

内部仮説をFOLD-Rへ事実として自動commitしない。出典付き外部証拠、ユーザー確定情報、検証済みの導出など、commit policyは別に持つ。

## 9. 学習対象を三種類に分ける

### 9.1 連続値

共有コア、codebook、scale、補正、routerの連続パラメータは通常のgradientを使える。固定code条件で、materializeした参照計算と直接復号計算のforward/gradient一致を小型float64テストで最初に確認する。

### 9.2 離散code

`c` は整数indexなので、通常のgradientと同一視しない。最初の正規候補は alternating optimization とする。

1. codeを固定して `W_base / D / E` を更新。
2. 更新対象blockを限定してcode候補を探索・再割当。
3. 1-step誤差だけでなく複数反復後の課題品質を確認。
4. 採用後に連続値を再調整。

STEは比較候補に置けるが唯一の正規解にしない。PV-Tuning等の離散/連続最適化を関連研究として参照する。

### 9.3 行動選択

routing、停止、取得、質問は行動結果で学ぶ。

1. 小さな合成課題では全候補を試し、oracle/near-oracle actionを教師化。
2. 次にモデル自身のroutingで学習し、誤った経路からの回復を含める。
3. 課題品質が同じなら少ない計算・取得を優先する。
4. 取得不能、予算切れ、矛盾した証拠も訓練に含める。

## 10. ローカル学習を成立させる原則

完成時の保存容量と学習時の作業メモリを分ける。

- 全decoded weightの高精度copy・gradient・optimizer stateをGPUへ常駐させることを必須にしない。
- 更新対象の共有部品・codebook・一部moduleを限定し、残りを圧縮状態で利用する方式を優先比較する。
- activation checkpointing、CPU/RAM offload、事前生成したteacher dataset等を利用できる。ただし実時間・IOを総費用へ含める。
- teacher modelとstudentを同時GPU常駐させることを必須にしない。
- optimizerやcheckpoint方式は実験manifestへ記録し、再開可能性をテストする。

「VRAMに収まった」だけで成功にしない。**同じ環境で反復的に改善できるwall-clock時間か**を評価する。

## 11. 入出力と因果性

最終候補は UTF-8 byte + 軽量local encoder/decoder + causal variable grouping。固定BPE/Unigramは比較対象に残す。

可変長groupingを学習するときも、生成時点で未生成のfuture byteを境界決定へ使わない。training/inference parityを専用テストで確認する。

異なる入力単位のモデルではtokens/sだけを比較しない。同じ文章・同じ課題を完了するwall-clock時間、byte当たりのloss、KV/状態量を併記する。

Visionは `Encoder -> Projector -> Input representations` として後付け可能にする。位置、画像領域、取得時点への参照を失わない。画像特徴があるだけで「見えている」と判定しない。

## 12. 実装上の必須検証

### 数値・圧縮

- materialized参照重みと、codebookから直接計算したforwardの一致。
- 固定code時のautogradとfloat64 finite differenceの比較。
- serializationしたbyte数とレポート値の一致。
- 辞書・scale・補正を除外した偽のbit/weightを出さない。

### 反復

- 1/2/4/8 stepで課題品質と状態差を測る。
- 同じ重みを使うことを理由に異なるstepのcache/stateを無条件共有しない。
- 追加stepが常に改善するという仮定を置かない。

### 因果性

- internal stepのみではevidence revisionが進まない。
- teacher forcingのfuture情報がgrouping、routing、memory writeへ漏れない。
- 仮説と観測のprovenanceが区別される。

### 制御

- 十分な情報がある課題で不要な質問をしない。
- 必要情報がない課題では、同じ証拠で内部反復しただけで架空情報を生成しない。
- 取得後に実際に答えを更新する。
- 取得失敗を回答値へ変換しない。

### 記憶

- ASSERT/RETRACT/REPLACE/scopeを区別する。
- `OUT_OF_SCOPE`を`false`や0へ落とさない。
- 訂正後に古い回答をcacheから無検証再利用しない。

## 13. 関連研究 — 制約ではなく比較材料

- Rate Distortion For Model Compression: From Theory To Practice — arXiv:1810.06401
- Extreme Compression of Large Language Models via Additive Quantization (AQLM) — arXiv:2401.06118
- PV-Tuning: Beyond Straight-Through Estimation for Extreme LLM Compression — arXiv:2405.14852
- PonderNet: Learning to Ponder — arXiv:2107.05407
- Dynamic Inference with Neural Interpreters — arXiv:2110.06399
- Byte Latent Transformer: Patches Scale Better Than Tokens — arXiv:2412.09871

これらを最終構造のテンプレートにはしない。どの部品も、同じ条件で有効性を確認してから採用する。
