# FOLD Context Memory / KV Replacement — 研究仮説レポート

作成日: 2026-09-14  
状態: **研究仮説 / 探索案。実証済み仕様ではない。FOLDの将来設計を拘束しない。**

関連文書:

- `fold/docs/architecture-v0.3.md`
- `fold/docs/research-plan.md`
- `fold/docs/shared-basis-runtime-output-impact-report.md`
- `fold/docs/shared-basis-auto-module-partition-report.md`
- `fold/docs/experiment-ledger-and-handoff.md`

---

## 1. 目的

FOLDでは現在、Shared Basis により、moduleやtaskごとの差異を巨大な独立重みとして持つのではなく、共有された低次元構造と小さなmodule固有差分で表現する方向を検証している。

この流れをruntime contextへ拡張する場合、単にTransformer型KV Cacheを圧縮するだけでなく、より根本的に次の問いを立てる価値がある。

> **過去contextを、各token・各layerのKey/Value列として保持し続ける必要は本当にあるのか。**

本書では、KV Cacheを改善する仮説と、KV Cacheそのものを置き換える仮説を分離して整理する。

目的は現時点で最終アーキテクチャを決定することではない。

目的は、

1. KV Cacheが担っている機能を分解する
2. FOLDのShared Basis思想と整合する代替構造を複数立てる
3. 各仮説の長所・破綻条件を明示する
4. 安価な人工課題から順に棄却可能な実験計画へ落とす
5. 将来の長context性能、VRAM、decode速度、module routingとの両立可能性を評価できる状態にする

ことである。

---

## 2. 本書の重要な前提

### 2.1 固定サイズ状態に無限のexact memoryは入らない

KV Cacheを排除したとしても、情報量そのものは消えない。

過去100万tokenに含まれるランダムな文字列や数値を、固定サイズ数KBの状態へ完全に圧縮し、任意位置から一字一句復元することはできない。

したがって、KV代替方式は必ず次のどれか、または組合せを選ぶ。

```text
A. 固定サイズ状態に圧縮する
   -> active memoryは小さい
   -> exact recall能力には容量上限がある

B. 記憶量をcontext長に応じて増やす
   -> exact性を保ちやすい
   -> O(T)要素が残る

C. 過去情報をGPU外へ退避する
   -> active GPU memoryをboundedにできる
   -> retrieval / 再encodeが必要になる
```

従って本研究の成功条件は、

> 「長contextでも何も保存しなくてよい」

ではない。

より現実的には、

> **通常生成で必要な情報を、denseなlayer-wise KV列より大幅に少ないactive stateで保持し、必要なexact情報だけ別経路で復元できること**

を目標とする。

---

## 3. KV Cache問題を3つに分解する

KV Cacheの問題を1種類として扱わない。

少なくとも次の3軸がある。

### 3.1 Layer / Head方向の冗長性

同じtokenについて、各layer / KV headが似た情報を別々に保持している可能性がある。

概念的には通常、

```text
token t
  |- layer 1: K,V
  |- layer 2: K,V
  |- layer 3: K,V
  |- ...
```

となる。

もしlayer間に低rank構造が存在するなら、ここはShared Basis化できる可能性がある。

### 3.2 Token長方向の線形増加

layer方向を圧縮しても、過去tokenごとの状態を残す限り、memoryはcontext length `T` に比例する。

```text
1k tokens   -> 1k分
10k tokens  -> 10k分
100k tokens -> 100k分
```

ここはShared KV Basisだけでは解決しない。

### 3.3 圧縮によるexact recall喪失

固定stateやsummaryへ圧縮すると、意味的情報は残っても、

- 数字
- UUID
- コード識別子
- 固有名詞
- 遠距離の変数binding
- 正確な引用

などが失われる危険がある。

従って、

```text
layer redundancy
long-context growth
exact recall
```

を別々に評価する必要がある。

---

## 4. 研究系統を3 Trackに分ける

本書では、初めから1方式へ一本化しない。

### Track A — KVを改善する

既存のAttention + KV semanticsを大きく壊さず、cache量を減らす。

候補:

- Shared KV Basis
- KV quantization
- chunk compression
- local-window化
- layer / head共有

最も安全側の系統。

### Track B — KVを置き換える

過去をKey/Value列として保存するという前提自体を外す。

候補:

- Context-as-Weights
- Fast-Weight Associative Memory
- Predictive State
- Context Operator Bank
- Multiscale Context Pyramid
- Surprise Memory
- Event / Relation Memory

FOLD独自性が最も出る系統。

### Track C — Hybrid

直近だけはKV / exact local attentionを使い、それより古い情報をKV-free stateへ移す。

```text
Local Exact Attention
        +
KV-free Long-Term State
        +
Optional Exact Archive
```

現時点では、このHybrid系が最も現実的な本命候補である。

ただしこれは暫定評価であり、Track B単独が成立するならKV自体をさらに削減できる。

---

## 5. 仮説 H1 — Shared KV Basis

### 5.1 仮説

各layer / moduleのKV表現には共通する低rank構造が存在し、完全独立KVを保持しなくてもよい可能性がある。

例えば、layer `l`、token `t` のKeyを、

```text
K[l,t] ~= sum_r aK[l,r] * K_basis[r,t]
```

Valueを、

```text
V[l,t] ~= sum_r aV[l,r] * V_basis[r,t]
```

と近似する。

通常:

```text
token
 |- layer 1 KV
 |- layer 2 KV
 |- layer 3 KV
 |- ...
```

仮説:

```text
token
 |- shared KV basis 1
 |- shared KV basis 2
 |- shared KV basis 3
      |
      |- layer 1 coefficients
      |- layer 2 coefficients
      |- layer 3 coefficients
```

### 5.2 FOLDとの整合性

現在のShared Basisが、

```text
W_module = W_base + A_module @ B_shared
```

という形なら、runtime context側でも、

```text
KV_layer = coefficients_layer @ KV_shared_basis
```

という類似思想を試す価値がある。

### 5.3 限界

Shared KV Basisはlayer方向の冗長性しか消さない。

過去token単位のbasis stateを保存する限り、token長 `T` に対するO(T)は残る。

### 5.4 棄却条件

- layer方向のeffective rankが高い
- rankを落とすとAttention logits / outputが急激に崩れる
- NLLは保ててもexact recall / reasoningが崩れる
- cache削減量に対して再構成計算が高過ぎる

場合は深追いしない。

---

## 6. 仮説 H2 — Local Exact Memory

### 6.1 仮説

大部分のtoken生成では、直近contextが最も高頻度に使われるため、最近の数百〜数千tokenだけを高精度に保持し、それより古い情報を別表現へ移せる可能性がある。

```text
recent tokens -> exact
older tokens  -> compressed / structured / archived
```

### 6.2 役割

Local Exact Memoryは、

- 文法
- 直近の会話
- 生成中コード
- 局所的な変数依存
- reasoning途中状態
- exact copy

を守る。

KV-free構造へ一気に移行せず、性能低下の大きい局所依存だけ従来型処理で保護する安全弁になる。

### 6.3 棄却条件

local windowを縮小した時点で、長距離ではなく局所品質まで大幅に崩れる場合、windowを小さくする余地が少ない。

---

## 7. 仮説 H3 — Shared Chunk Memory

### 7.1 仮説

古くなったtoken列を、1個のsummary vectorではなく複数のlatent slotsへ圧縮すれば、意味情報・関係・局所詳細を分散して保持できる可能性がある。

例:

```text
64 tokens
   |
   v
4-8 latent memory slots
```

### 7.2 重要点

これは自然言語の要約文を生成する方式ではない。

モデル内部で利用するlatent representationであり、slotごとに異なる情報を保持できる余地を残す。

### 7.3 Shared Memory化

moduleごとに別Chunk Memoryを作ると、contextがmodule数だけ複製される。

従って第一候補は、

```text
          Shared Memory Bank
                 |
        +--------+--------+
        |        |        |
     language   logic    code
      reader    reader   reader
```

とする。

**Memory内容は共通、読み方だけmodule固有**という仮説である。

### 7.4 棄却条件

- module間で必要Memory representationが強く競合する
- 共有するとnegative transferが大きい
- slot数を増やしてもexact / semantic recallが飽和しない

場合、module-local memoryやgrouped memoryが必要になる。

---

## 8. 仮説 H4 — Canonical Shared Writer + Module-specific Reader

### 8.1 仮説

長期Memoryへの書き込みauthorityは共通化し、moduleは同じMemoryを異なる方法で読む方が、routing変更に強い。

```text
token stream
    |
    v
Shared Context Writer
    |
    v
Canonical Shared Memory
    |
 +--+--+
 |  |  |
 A  B  C
readers
```

### 8.2 理由

moduleごとにMemoryを書かせると、

```text
module A state
module B state
module C state
```

が分裂し、routerがmoduleを切り替えたときに、

- inactive moduleが新しいcontextを知らない
- 同じentityがmoduleごとに異なる状態を持つ
- cache / memory所有権が複雑化する

可能性がある。

Shared Writer方式なら、contextのcanonical stateを1つにし、moduleはread semanticsだけ変えられる。

### 8.3 ReaderのShared Basis化

module-specific Reader自体も、

```text
W_reader(module) = W_reader_shared + A_module @ B_reader
```

のようなShared Basis構造へできる可能性がある。

これにより、

```text
Shared Memory
+
Shared Reader Basis
+
small module adapter
```

という二段共有が成立する。

---

## 9. 仮説 H5 — Exact Archive

### 9.1 仮説

古い情報をGPU上のKVとして保持しなくても、raw token historyそのものは比較的低コストでCPU RAM / storageへ保存できる。

```text
GPU
 |- recent exact state
 |- warm memory
 |- global state

CPU / storage
 |- exact token archive
```

### 9.2 目的

圧縮Memoryの役割を、

> 過去を完全保存する

から、

> 必要な過去を探し出せる程度に意味を残す

へ変える。

exact情報が必要な場合は、Archiveから該当chunkを取得し再encodeする。

### 9.3 意義

総storageはO(T)のままだが、active GPU memoryをcontext lengthから切り離せる可能性がある。

FOLDの長context目標では、

> total memoryを完全O(1)にする

より、

> **高価なactive stateをboundedにする**

方が現実的である。

---

# 10. KV-free Track

以下はKV Cacheを圧縮するのではなく、過去をKey/Value列として保持する構造自体を置き換える仮説である。

---

## 11. 仮説 H6 — Context-as-Weights

### 11.1 中心発想

通常のKV方式は、

```text
past
  |
KV Cache
  |
current query reads past
```

である。

Context-as-Weightsでは、

```text
past
  |
Context Writer
  |
runtime coefficients
  |
model computation itself changes
```

とする。

つまり、

> **過去を毎回参照するのではなく、過去によって現在のモデル状態を変化させる。**

### 11.2 Shared Basisとの接続

学習済みContext Basis `B_i` と、小さなruntime係数 `c_t` を使う。

```text
W_t = W_0 + sum_i c[t,i] * B_i
```

巨大な `W_t` をmaterializeする必要はなく、概念的には、

```text
y = W_0 x + sum_i c_i * (B_i x)
```

として評価できる。

### 11.3 FOLDとしての統一性

静的能力:

```text
Shared Basis
+
Module coefficient
```

動的context:

```text
Context Basis
+
Runtime coefficient
```

とできる。

つまりShared Basis思想を、

- 保存されるweight
- module差分
- 推論時context state

まで統一的に展開できる。

### 11.4 最大の懸念

単一の小さなcontext coefficient vectorへ長文全体を押し込むと、情報衝突が起きる。

従ってContext-as-Weights単独より、複数slotを持つContext Operator Bankとの組合せを第一候補とする。

---

## 12. 仮説 H7 — Context Operator Bank

### 12.1 仮説

単一runtime stateではなく、少数の文脈演算子slotを持つ。

例:

```text
Context Operator Bank

[slot 0]
[slot 1]
[slot 2]
...
[slot 31]
```

各slotはContext Basis coefficientを持ち、現在のquery / hidden stateによって必要slotだけ使用する。

### 12.2 KVとの違い

KV Cacheは、

> token単位の記憶を選択する

Context Operator Bankは、

> 過去から形成された少数の文脈演算子を選択する

構造になる。

### 12.3 期待

slot数を固定できれば、context lengthに対するactive stateを固定化できる。

### 12.4 棄却条件

association数やcontext lengthの増加に対し、slot collisionによる性能崩壊が急激なら、単独長期Memoryとしては不十分。

---

## 13. 仮説 H8 — Fast-Weight Associative Memory

### 13.1 仮説

過去の `(key, value)` ペアそのものを保存せず、固定サイズMemory matrixへその場で書き込む。

概念的には、

```text
M[t+1] = lambda * M[t] + update(k_t, v_t)
```

読み出しは、

```text
r = M q
```

とする。

### 13.2 KVとの違い

通常:

```text
k1,v1
k2,v2
k3,v3
...
全部保存
```

Fast Weight:

```text
new information
      |
      v
+-------------+
| Memory M    |
+-------------+
      ^
      |
    query
```

### 13.3 長所

Memory matrixサイズを固定できる。

### 13.4 最大の問題

多数のassociationを書き込むと干渉・上書きが発生する。

従って、

- overwrite semantics
- decay
- normalization
- slotting
- routing
- write sparsity

の設計が性能を大きく左右する。

### 13.5 Shared Basis化

さらに、

```text
M = sum_i c_i * B_i
```

のようにMemory自身をBasis展開する仮説も立てられる。

これはContext-as-Weightsと境界が近く、別々に実験した上で統合可能性を見る。

---

## 14. 仮説 H9 — Predictive State

### 14.1 発想

LLMに本当に必要なのは過去全文そのものではなく、

> 次tokenを予測するために必要な過去の十分統計

である可能性がある。

そこで、

```text
s_t = f(s_{t-1}, x_t)
```

だけを保持し、

```text
p(x_{t+1}) = g(s_t)
```

とする。

### 14.2 理想

context lengthによらずstateサイズ一定。

### 14.3 弱点

next-token prediction上で低価値なランダム情報は消えやすい。

例:

```text
AB19-XQ72-ZP40
```

を後からexact recallする能力と相性が悪い可能性がある。

従ってPredictive State単独を本命とせず、Local Exact / ArchiveとのHybrid候補とする。

---

## 15. 仮説 H10 — Multiscale Context Pyramid

### 15.1 仮説

時間距離に応じてcontext解像度を落とす。

```text
current
 |
 |- newest        : exact/high resolution
 |- recent        : compressed
 |- older         : coarser
 |- very old      : global state
```

例:

```text
latest 64 tokens        -> exact
previous 256 tokens     -> 4-8 slots
previous 1k tokens      -> 4-8 coarser slots
previous 4k tokens      -> 4-8 coarser slots
previous 16k tokens     -> 4-8 coarser slots
older                   -> global state / archive index
```

### 15.2 更新

levelが満杯になったら上位levelへmergeする。

```text
Level 0 full
   |
 merge
   v
Level 1

Level 1 full
   |
 merge
   v
Level 2
```

### 15.3 期待

構造次第では、active memory growthをdense O(T)からO(log T)に近づけられる可能性がある。

### 15.4 リスク

距離だけで情報重要度を決めると、非常に古いが重要な情報を過剰圧縮する。

従ってSurprise / Importance Writerとの併用が有力。

---

## 16. 仮説 H11 — Surprise Memory

### 16.1 中心発想

> **予測可能な情報は保存量を減らし、予測困難な情報へMemory容量を重点配分する。**

文章の大部分は、学習済みモデルがある程度再構成できる可能性がある。

一方で、

```text
Server port = 58317
```

のような予測困難な情報はMemoryに残す価値が高い。

概念的には、

```text
prediction error / novelty / surprise
        |
        v
memory write strength
```

とする。

### 16.2 狙い

Memory使用量をtoken数ではなく、

> **新規情報量・予測誤差・将来利用価値**

へ近づける。

### 16.3 注意

「予測しやすい = 不要」ではない。

指示文、否定、条件、security-critical tokenなど、予測可能でも保持すべき情報がある。

従ってSurprise score単独をwrite authorityにしてはならない。

---

## 17. 仮説 H12 — Event / Relation Memory

### 17.1 仮説

文章をtoken列として保存するのではなく、内部的なentity / relation / event構造へ変換する。

例:

```text
Alice runs Minecraft.
The server port is 8123.
The runtime is Java 21.
```

を、概念的に、

```text
Entity: Minecraft Server
  owner/runtime relation -> Alice / Java 21
  port                   -> 8123
```

のような構造へ保持する。

### 17.2 強い用途

- Agent
- long-running task
- game state
- codebase state
- entity tracking
- planning

### 17.3 弱点

- 文体
- exact wording
- token order
- quotation
- 曖昧さそのもの

は失われやすい。

従ってUniversal Memoryではなく、semantic / world-state layer候補とする。

---

# 18. 統合仮説 — FOLD Context Engine

現時点で最も有望に見える統合案は、単一Memoryではなく複数stateを役割分担させる構造である。

```text
                       Input
                         |
                         v
                  Context Writer
                         |
          +--------------+---------------+
          |              |               |
          v              v               v
     Local Exact     Context Operator   Associative
       State              Bank            Memory
          |              |               |
          |              +-------+-------+
          |                      |
          |              Global / Pyramid State
          |                      |
          +----------+-----------+
                     |
             Shared Context View
                     |
          +----------+-----------+
          |          |           |
       Module A   Module B    Module C
       Reader     Reader      Reader
          |          |           |
          +----------+-----------+
                     |
                Memory Fusion
                     |
                   Output

Optional side path:
Exact Token Archive <-> Retrieval / Re-encode
```

重要なのは、これを現時点で採用仕様としないことである。

各構成要素を独立にablationし、必要性が確認されたものだけ残す。

---

## 19. 暫定本命 — Context-as-Weights + Associative Memory + Selective Writer

KV-free側の研究候補としては、次の組合せを優先度高とする。

```text
Context-as-Weights
        +
Fast-Weight / Associative Memory
        +
Selective Writer
        +
Optional Local Exact Window
```

理由:

1. Shared Basisとの思想的・計算的接続が強い
2. contextをmodel stateへ吸収するというFOLD固有の研究軸になる
3. fixed-size active stateを狙える
4. association recallを単一hidden vectorより明示的に扱える
5. exact local windowを残せば初期実験を安全に進められる

ただし、これもあくまで**優先実験候補**であり、最終採用ではない。

---

## 20. Module-local Scratchpadの位置づけ

Shared Contextをcanonical memoryとする一方、module固有の一時状態は許容できる。

```text
Shared Memory      = authoritative long-lived context
Module Scratchpad  = temporary / disposable working state
```

例:

- reasoning途中計算
- code moduleの局所解析
- router内部判断

など。

moduleが切り替わったときに失ってはいけない情報は、Shared Writerを通じてcanonical stateへ昇格させる。

この境界を明示することで、moduleごとのMemory複製を避けつつ専門的な作業状態を持てる。

---

## 21. Memory Fusion

異なる種類のMemoryを1個のsoftmaxへ全部入れる方式は第一候補にしない。

Local Exact、Chunk、Global、Retrieved Archiveでは情報の意味・scale・precisionが異なる。

従って、別々に読み出し、最後に融合する方が検証しやすい。

概念:

```text
R_local
R_chunk
R_global
R_retrieved
```

を得て、

```text
R = g_local * R_local
  + g_chunk * R_chunk
  + g_global * R_global
  + g_retrieved * R_retrieved
```

のように融合する。

このgate自体もShared Basis / module adapterの対象になり得る。

---

## 22. Chunk処理と並列性

完全recurrentにtoken単位でstateを書き換えると、学習・prefillの並列性を失う可能性がある。

従って、KV-free Memoryでもchunk単位処理を優先候補とする。

例:

```text
64-token chunk
  |- parallel token processing
  |- local interaction
  `- consolidate -> memory update
```

その後次chunkへ進む。

これにより、

- token-level完全逐次依存を避ける
- GPU parallelismを残す
- Memory update頻度を下げる

ことが期待できる。

---

# 23. 実験計画

全方式を一度に実装しない。

何が効いたのか分からなくなるため、段階的に仮説を潰す。

---

## Phase 0 — Baseline

通常Attention + KV方式の基準値を固定する。

測定:

- NLL
- exact recall
- semantic recall
- peak VRAM
- cache bytes / token
- prefill tokens/s
- decode tokens/s
- parameter count
- runtime working-set bytes

特に、

```text
cache bytes / token
```

を主要指標にする。

---

## Phase 1 — KV冗長性の観測

モデル構造を変更せず、既存K/Vを収集する。

調査対象:

- layer方向effective rank
- head方向effective rank
- token / task / moduleごとのrank変化
- KとVでrank特性が異なるか

SVD / PCA等で、rank 1,2,4,8,... の再構成品質を見る。

ただし行列誤差だけで合否を決めない。

再構成KVを使ったときの、

- Attention logit差
- Attention output差
- NLL
- exact recall
- downstream task performance

を必ず見る。

---

## Phase 2 — Shared KV Basis

他のMemory構造は変えず、Shared KV Basisだけ導入する。

比較:

```text
Dense KV
rank 1
rank 2
rank 4
rank 8
...
```

目的:

> quality lossに対してcache reductionが十分大きいか

を判定する。

---

## Phase 3 — KV-free Synthetic Memory Bench

言語モデル全体を作り替える前に、人工課題でMemory容量を測る。

基本課題:

```text
A = 7381
B = 2944
C = 5830
...
Question: What is B?
```

方式比較:

- normal attention + KV
- fixed recurrent state
- associative matrix
- Context-as-Weights
- Context Operator Bank
- Pyramid Memory

association数を、

```text
64
128
256
512
1024
...
```

と増やし、破綻点を見る。

---

## Phase 4 — Memory干渉Bench

単純key-value recallだけでは不十分。

追加:

- overwrite
- same key, newer value
- distractor増加
- multiple needles
- ordered events
- entity binding
- compositional lookup
- relation chain
- duplicated values
- adversarial similarity

ここで固定state方式のcapacity / collision特性を測る。

---

## Phase 5 — Local + KV-free Hybrid

Syntheticで有望だったKV-free stateへ、小さいLocal Exact Windowを組み合わせる。

比較:

```text
full KV
local KV only
local KV + associative
local KV + context-as-weights
local KV + operator bank
```

長距離性能とactive memoryを同時に見る。

---

## Phase 6 — Exact Archive / Retrieval

圧縮stateで失われるexact情報を、raw token archiveから救済できるか検証する。

評価:

- retrieval hit rate
- retrieval false positive
- re-encode overhead
- latency
- exact recall recovery
- archiveなしとの差

---

## Phase 7 — Full Language / Reasoning Context Bench

人工課題を通過した方式だけを本モデル評価へ進める。

ここで初めて、

- language NLL
- reasoning
- code
- instruction retention
- long document
- conversation state

を総合評価する。

---

# 24. 必須Benchmark

KV代替構造はNLLだけで評価してはならない。

## 24.1 Exact Recall

ランダム文字列・数値・識別子を後から完全一致で復元できるか。

## 24.2 Entity Binding

```text
Alice = 31
Bob = 72
Carol = 44
```

のようなmappingを保持できるか。

## 24.3 Multiple Needle

遠距離情報が1個だけならなく、複数混在した場合。

## 24.4 Ordering

```text
A before B before C
```

の順序を維持できるか。

## 24.5 Update / Overwrite

古い値を新しい値で正しく更新できるか。

## 24.6 Code Dependency

遠くのfunction / variable / type定義を利用できるか。

## 24.7 Instruction Retention

会話冒頭の制約を長距離後も守れるか。

## 24.8 Semantic Recall

完全一致ではなく、過去の意味内容を正しく保持できるか。

## 24.9 Distance Curve

```text
128
512
2k
8k
32k
...
```

と距離を伸ばしたときの性能曲線を見る。

---

# 25. 最重要グラフ

研究判断には少なくとも次の2グラフを常設する。

## 25.1 Recall vs Distance

```text
X = context distance
Y = recall accuracy
```

Memory構造がどの距離から崩れるかを見る。

## 25.2 Active Memory vs Context Length

```text
X = context length
Y = active runtime memory / VRAM
```

理想形:

```text
Dense KV
  /
 /
/

FOLD candidate
---------
```

完全水平でなくても、dense KVより増加率を大幅に落とせるかを見る。

---

# 26. 仮説一覧と棄却条件

| ID | 仮説 | 主な期待 | 主な破綻条件 |
|---|---|---|---|
| H1 | Shared KV Basis | layer/head冗長性削減 | high effective rank |
| H2 | Local Exact Memory | 局所品質保護 | 小windowで品質急落 |
| H3 | Shared Chunk Memory | 古いcontext圧縮 | slot collision / negative transfer |
| H4 | Canonical Writer + Module Reader | routing耐性 | module間Memory競合 |
| H5 | Exact Archive | exact情報救済 | retrieval/re-encode overhead過大 |
| H6 | Context-as-Weights | 過去をmodel stateへ吸収 | context係数capacity不足 |
| H7 | Operator Bank | 少数動的演算子でcontext保持 | slot collision急増 |
| H8 | Associative Memory | fixed-size relation memory | interference / overwrite |
| H9 | Predictive State | fixed active state | random detail消失 |
| H10 | Context Pyramid | O(log T)級active state候補 | 古い重要情報の過圧縮 |
| H11 | Surprise Memory | 情報量ベース書込 | 重要だが予測可能な情報を捨てる |
| H12 | Event/Relation Memory | semantic/world-state保持 | wording/order/exact性喪失 |

---

# 27. 暫定優先順位

現時点の推奨順序は以下。

### Priority 1 — 測る

まず既存KVの冗長性を観測する。

```text
layer rank
head rank
cache bytes/token
reconstruction quality
```

ここはモデル本体を大きく変えずに情報価値が高い。

### Priority 2 — 小型人工課題でKV-free方式を競わせる

特に、

```text
Context-as-Weights
Associative Memory
Context Operator Bank
```

を優先する。

### Priority 3 — Local Exact Hybrid

KV-free方式が単独ではexact性を失っても、短いLocal KVと組み合わせることで実用になるか確認する。

### Priority 4 — Pyramid / Archive

長contextへ拡張し、active memory growthを抑える。

### Priority 5 — 本モデル統合

Syntheticで勝てない方式は大規模実装へ進めない。

---

# 28. 現時点の判断

本書の時点では、FOLDのContext設計を次のどれかへ固定しない。

特に、以前考えた、

> 古いcontextを1個のShared Context Basisへまとめる

という単純案だけに依存しない。

現時点では、より有望な研究方向として、

```text
Shared / Canonical Context
        +
Module-specific Readers
        +
Context-as-Weights or Associative State
        +
Selective / Surprise-aware Writer
        +
Optional Local Exact Window
        +
Optional Exact Archive
```

を置く。

ただし、これも最終仕様ではない。

各部品を独立に検証し、失敗した仮説は切り捨てる。

---

# 29. FOLDとしての最大の研究価値

Shared Basisがweight側だけの圧縮技術で終わる場合、FOLDの差別化は主にparameter efficiencyになる。

一方、context側でも同じ思想が成立すれば、

```text
Static model capacity
  -> Shared Basis + module coefficients

Runtime context
  -> Shared context structure + dynamic coefficients

Long-term memory
  -> shared / compressed / structured state
```

という統一アーキテクチャに発展できる。

特にContext-as-Weightsが成立した場合、Transformer型KVとの違いは、

```text
Transformer:
Past = data retained and reread

FOLD hypothesis:
Past = changes absorbed into runtime model state
```

となる。

これは単なるKV圧縮ではなく、**contextの表現原理そのものを変える研究軸**になる。

---

# 30. 次の最小実験

次に実装へ進む場合、最小の一歩は以下とする。

## Experiment A — KV low-rank observability

既存小型modelのlayer-wise K/Vをdumpし、effective rankと再構成誤差を測定する。

目的:

> Shared KV Basis仮説がそもそも成立しそうかを安く判定する。

## Experiment B — KV-free associative synthetic benchmark

key-value association課題で、

```text
normal KV
fixed state
associative state
Context-as-Weights
Operator Bank
```

を比較する。

目的:

> KV-free stateがどの容量・干渉特性を持つかを言語モデル統合前に確認する。

このA/Bは互いに独立して進められる。

Shared KV Basisが失敗してもKV-free trackは継続できるし、その逆も成立する。

---

# 31. まとめ

現時点のFOLDでは、Shared Basisによりparameter側の冗長性へ手を付け始めているが、runtime contextの冗長性についてはまだ設計余地が大きい。

KV Cacheについては、

1. **KVをそのまま圧縮する**
2. **階層Memoryへ変換する**
3. **KVをmodel state / fast weightsへ置換する**
4. **exact情報だけ外部Archiveで保持する**

を別仮説として扱うべきである。

特にFOLD固有研究としては、

> **Context-as-Weights + Associative Memory + Selective Writer + Shared Reader**

が最も興味深い候補である。

ただし、現段階では採用しない。

最初にKVの実測とsynthetic memory benchmarkを行い、各方式のcapacity・干渉・品質・runtime costを数値で比較したうえで残す構造を決める。

本書はそのための研究仮説集合として扱う。
