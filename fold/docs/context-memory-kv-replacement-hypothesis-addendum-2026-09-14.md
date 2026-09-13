# FOLD Context Memory / KV Replacement — 追補レビュー 2026-09-14

状態: **研究仮説レポート補遺 / 実装・実験前の制約追加。元レポートを置換しない。**

対象:

- `fold/docs/context-memory-kv-replacement-hypothesis-report.md`
- commit `1f094fb90cea7a0191077f729590106dd7e8c372`

この補遺は、元レポートの仮説集合を維持したまま、現在のFOLD Gate-C実験で得られた制約、実験公平性、Memory authority境界、実装順を追加する。

---

# 1. まず固定する重要な訂正

## 1.1 現在のFOLD小型Gate-C coreはTransformer型KV Cacheを持たない

元レポートの `Experiment A — KV low-rank observability` は、

> 既存小型FOLD modelのlayer-wise K/Vをdumpする

という意味では実行できない。

現在Gate Cで検証しているFOLD coreは、Transformer attention stack / layer-wise KV Cacheを主構造としていない。

従ってH1 `Shared KV Basis` の観測対象は、第一候補として **比較用Transformer / GQA baseline** とする。

```text
Reference Transformer / GQA
    -> K/V dump
    -> layer/head redundancy observation
    -> Shared KV Basis feasibility

FOLD candidate
    -> KV-free / hybrid memory experiments
```

H1はFOLD本体の必須構成ではなく、

- Transformer型baselineがどこまで圧縮できるか
- KVを残すHybrid pathでどこまでcacheを縮められるか

を測る比較Trackとして扱う。

Shared KV Basisが失敗してもKV-free Trackは継続できる。

---

# 2. Gate-C runtime実験から追加される制約

Context-as-WeightsやOperator Bankは、Shared Basisと同じ「basis + coefficient」型計算を使う可能性が高い。

そのため、parameter側のGate-C実験で観測されたruntime特性を無視してはならない。

## 2.1 C70 — GEMM-native recurrence equivalence

Gate-Cでは、

```text
W_eff = W_base + A @ B
```

を毎回materializeする代わりに、

```text
F.linear(x, [W_base; B])
+
coefficient addmm
```

で評価するGEMM-native式が、現在の3 task / 3 seed、最大64回のstate updateまで数値的・意味的に一致した。

意味:

> Context-as-Weightsでも「動的重みをmaterializeしない」実行は有力。

ただし、数値同値性とruntime効率は別問題である。

## 2.2 C71-C72 — 小型shapeでは追加GEMM costが重い

小型Gate-B/Gate-C shapeではShared-basis GEMMがDenseに対しておよそ1.3-1.4x程度のlatency taxを持った。

CUDA Graph replayでも全体として改善しなかった。

従って、Context-as-Weights / Operator Bankについても、

```text
basis数を増やせば記憶容量が増える
```

だけを最適化してはならない。

basis数 / effective rankは、

```text
memory quality
active bytes
FLOPs
HBM traffic
temporary bytes
latency
```

を同時に見る。

## 2.3 C73 — rank fractionはruntime costそのもの

full coreをwidth 32〜5120まで測った結果、代表的なrank fractionでruntime behaviorが大きく異なった。

概略:

```text
lean   rank = W/16  -> width5120でDenseの約1.06x
medium rank = W/8   -> width5120で約1.08-1.12x
high   rank = W/4   -> width5120でも約1.22x前後
```

さらにfull-core persistent storage削減率もrankで変わる。

この結果から、Context Memoryでも次を原則とする。

> **必要品質を満たす最小effective rank / slot count / operator countを選ぶ。**

rank / slot / operator capacityは品質だけでなくruntime costの設計変数である。

## 2.4 C74 — lower rankは自動的に採用しない

Condition rank3はrank4よりrouted-weightをさらに削減したが、12-seed exhaustiveではDenseに対して弱い負方向が残った。

従って、

```text
小さい
=
採用
```

ではない。

Context Memoryでも、capacityを削る場合は必ずquality / recall / failure-tailまで比較する。

---

# 3. Context-as-Weightsの追加Gate

元レポートH6は、FOLD固有研究として引き続き高優先度とする。

ただし採用条件へ次を追加する。

## 3.1 Dynamic Basis Runtime Gate

Context-as-Weightsを、

```text
W_t = W_0 + sum_i c_i B_i
```

として実装する場合、少なくとも以下を測る。

```text
context basis count
effective active rank
coefficient sparsity
active basis count / token
projection FLOPs
coefficient FLOPs
HBM bytes
peak temporary memory
prefill latency
decode latency
```

全basisを毎token評価する方式を既定にしない。

有力候補:

```text
small fixed bank
+
sparse active basis
+
query-conditioned top-k operator selection
```

ただしtop-k routing自体のcostも計上する。

## 3.2 Capacity-vs-Collision curve

単一scoreでなく、

```text
operator slots / rank
        vs
recall / collision / latency
```

のPareto curveを取る。

特にfixed-size Operator Bankでは、slot数が足りないと急激なcollision cliffが起こる可能性がある。

---

# 4. Canonical Writerはauthorityと観測を分離する

H4 `Canonical Shared Writer + Module-specific Reader` は本命候補として維持する。

ただし、

> canonical authorityが1つ

と、

> observation / proposal mechanismも1つ

を同一視しない。

初期比較は次の3系統を推奨する。

## A. Single Canonical Writer

```text
all observations
    -> one shared writer
    -> canonical memory
```

最も単純でdeterministic。

## B. Shared Writer + Module-conditioned Write Adapter

```text
module observation
    -> shared writer
       + small module adapter
    -> canonical memory
```

module固有の観測差を残しつつauthorityは一つにする。

## C. Module Write Proposal + Canonical Merger

```text
module A proposal --+
module B proposal --+--> canonical merger --> canonical memory
module C proposal --+
```

moduleごとに「重要だと思う情報」を提案できるが、authoritative commitは共有mergerだけが行う。

この方式は複雑なのでA/Bで不足が観測された場合のみ進める。

---

# 5. Transactional Memory Writeを必須候補に追加

Runtime Memoryへ即時commitする設計は危険である。

生成中には、

```text
speculative token
rejected decode branch
未検証仮説
途中reasoning
一時的module scratch
```

が存在する。

これらをcanonical long-lived stateへ即時書き込むと、後から棄却された情報が残留する。

従ってMemory Writer APIは第一候補として、

```text
observe
  -> stage
  -> validate / accept
  -> commit
```

を持つ。

失敗時:

```text
stage
  -> reject
  -> rollback / discard
```

最低限の概念API:

```text
stage_write(candidate)
commit(write_id)
rollback(write_id)
```

## 5.1 commit boundary

何をcommit可能とするかを明示する。

候補:

- accepted input token
- accepted generated token
- verified tool result
- verified retrieval result
- verified state transition
- explicitly promoted module scratch state

原則として、未検証仮説や棄却branchはcanonical memoryへcommitしない。

## 5.2 speculative decodeとの整合

将来speculative decodingを使う場合、accepted prefixだけMemoryへcommitする。

```text
speculative tokens
    -> staged memory delta
accepted prefix
    -> commit corresponding delta
rejected suffix
    -> rollback
```

---

# 6. Memory taxonomyを既存FOLD-Rと分離する

Context Memoryは既存FOLD-Rの記憶を置き換えない。

次の4階層を明確に分ける。

## 6.1 Runtime Context Memory

現在のsequence / conversationに依存する短中期状態。

```text
Local Exact
Warm / Chunk Memory
Operator / Associative State
Global Context State
Context Archive Index
```

## 6.2 Long-lived Validated Memory

sessionを超えて保持し得る検証済み状態。

既存FOLD-R側の例:

```text
Response Memory
Structural Memory
Validated learned knowledge
```

## 6.3 Temporary Working State

捨てられる状態。

```text
Module Scratchpad
Router scratch
Search frontier
Temporary latent reasoning state
```

## 6.4 Hypothesis Workspace

未確定情報。

```text
candidate relations
unverified bridges
branch-local assumptions
validation history
```

Runtime ContextとLong-lived Memoryへ自動昇格させない。

### Promotion rule

```text
Temporary / Hypothesis
        -> validation
        -> explicit promotion
        -> canonical validated state
```

を基本にする。

---

# 7. Shared Memory / Readerの評価を「共有率」だけにしない

Shared Memoryはmodule数分の複製を避けられる可能性が高いが、共有するとnegative transferが起こり得る。

Auto-Partition側と同様、以下を区別する。

```text
capacity不足
writer co-adaptation不足
reader capacity不足
本当のmemory representation conflict
```

Memory性能低下を見て即module-local memoryへSplitしない。

推奨diagnostic順:

```text
KEEP
  -> Writer / Reader co-adaptation check
  -> Grow slot/rank
  -> Interference measurement
  -> Shadow grouped-memory trial
  -> Split if persistent benefit
```

---

# 8. Equal-Budget Comparisonを必須Gateに追加

KV代替方式を比較するとき、単純なaccuracy比較だけでは不公平になる。

比較条件を最低でも2種類用意する。

## 8.1 Equal Active Bytes

```text
same active GPU memory budget
```

で、

- Dense KV
- local KV
- Chunk Memory
- Associative Memory
- Context-as-Weights
- Operator Bank

を比較する。

## 8.2 Equal Runtime Budget

可能な範囲で、

```text
similar FLOPs / latency budget
```

でも比較する。

## 8.3 Pareto評価

単一winnerを決めず、

```text
recall
NLL
active bytes
peak VRAM
prefill tokens/s
decode tokens/s
p95 latency
```

のPareto frontierを見る。

容量を2倍使った方式が1%だけ高精度でも、自動的な勝者とはしない。

---

# 9. Shared KV Basisのposition-aware観測

H1をTransformer / GQA baselineで測る場合、Kを一種類として扱わない。

最低限、

```text
pre-positional-transform K
post-positional-transform K
V
```

を分けて観測する。

RoPE系の場合、position適用前後でlayer/head間のlow-rank性が変わる可能性がある。

Phase 1では、

```text
K-pre-position effective rank
K-post-position effective rank
V effective rank
attention-logit reconstruction error
attention-output reconstruction error
```

を別に記録する。

行列MSEが小さくてもattention semanticsが壊れる場合は棄却する。

---

# 10. Exact Archiveはtail latencyを評価する

Exact Archive / Retrievalでは平均latencyだけでは不十分。

必須:

```text
p50
p95
p99
```

加えて、

```text
retrieval hit rate
false positive rate
re-encode cost
GPU transfer bytes
stall time
```

を測る。

将来候補:

```text
retrieval prediction
prefetch
asynchronous CPU retrieval
background chunk encoding
```

ただし最初のPhaseでは同期baselineを先に固定し、最適化を混ぜない。

---

# 11. Surprise Writerは単独authorityにしない

H11は有望だが、surprise / prediction errorだけをwrite authorityにしてはならない。

重要だが予測可能な情報が存在するためである。

例:

```text
"以後JSONだけで返す"
"絶対にこの変数を変更しない"
security-critical constraint
```

推奨write scoreは複合とする。

概念:

```text
write_score =
    novelty
  + task relevance
  + future-use estimate
  + explicit importance
  + constraint / instruction priority
  + overwrite significance
```

最終commitにはhard rule / authority ruleを併用する。

---

# 12. Writer policyをMemory形式と独立研究軸にする

今後のMemory研究では、

```text
What to store?
How to encode?
Where to store?
When to retrieve?
How to forget / overwrite?
```

を分けて扱う。

Memory形式が優れていてもWriterが悪ければ性能は崩れる。

逆に単純なMemoryでもWriter policyが良ければ高効率になる可能性がある。

従って、Writer policyを独立ablation対象にする。

---

# 13. 推奨する初期統合候補

現時点では純粋なContext-as-Weights単独を本命に固定しない。

第一候補の研究構成:

```text
Local Exact Memory
        +
Canonical Shared Writer
        +
Context Operator / Associative Memory
        +
Module-specific Reader
        +
Transactional Commit
        +
Optional Exact Archive
```

Context-as-Weightsは、

```text
runtime model modulation / dynamic operator representation
```

としてこの中へ組み込んで比較する。

理由:

- Local Exactがcopy / syntax / near dependencyを保護する
- Operator / Associative Stateがbounded active memoryを狙える
- Canonical Writerがmodule switch時のstate分裂を避ける
- Module Readerで処理特性差を残せる
- Transactional Commitで棄却branch汚染を防げる
- Archiveでexact long-range情報を救済できる

---

# 14. 実験番号はCxxと分離する

現在の `Cxx` は主にGate-C parameter representation / runtime / recurrenceを追跡している。

Context Memory研究を同じ番号列へ混ぜると、

```text
parameter compression
context memory
runtime execution
```

のGateが混線する。

従ってContext Memory専用の実験系列を推奨する。

```text
M01, M02, M03, ...
```

仮称:

```text
M = Memory / Context Memory experiment
```

Cxx Gate-Cを止める必要はない。

Shared Basis representationを安定させつつ、Memory系を独立に並行できる。

---

# 15. 改訂版の最小実験順序

## M01 — Transformer KV observability baseline

比較用Transformer / GQA modelを対象に、

- K pre/post positional transform
- V
- layer/head effective rank
- cache bytes/token
- attention-output reconstruction impact

を測る。

これはH1だけの観測実験。

## M02 — Equal-byte synthetic memory competition

key-value association taskで、同じactive-byte budgetの下、

- Dense KV reference
- fixed recurrent state
- associative state
- Context-as-Weights
- Operator Bank

を比較する。

association countを増やしてcapacity cliffを見る。

## M03 — Interference / overwrite bench

- same-key update
- multiple needles
- distractor
- relation chain
- adversarial similarity

でcollision特性を測る。

## M04 — Local Exact Hybrid

M02/M03で残ったKV-free候補へ短いLocal Exact Windowを追加する。

```text
full KV
local only
local + associative
local + operator
local + context-as-weights
```

を比較する。

## M05 — Canonical Writer / Reader topology

A/B/C writer方式を比較する。

- single canonical writer
- shared writer + module adapter
- proposal + canonical merger

Memory内容とReader構造を固定し、writer topologyだけ変える。

## M06 — Transactional Write

speculative / rejected branchを混ぜ、

- staged writes
- commit
- rollback

がcanonical stateを汚染しないことを確認する。

## M07 — Multiscale Pyramid

距離と解像度のtradeoffを測る。

## M08 — Exact Archive

retrieval / re-encodeでexact recallを回復できるか測る。

p50/p95/p99 latencyを必須にする。

## M09 — Full language / reasoning integration

Syntheticを通過した構成だけを本体へ統合する。

---

# 16. 成功条件の追加

Context Memory方式を「成功」と呼ぶには、少なくとも次を満たす。

## Quality

- next-token / task quality
- exact recall
- semantic recall
- entity binding
- overwrite correctness
- instruction retention

## Memory

- active bytes / tokenまたはactive-state growth
- peak VRAM
- CPU/archive bytes

## Runtime

- prefill throughput
- decode throughput
- p50/p95/p99 latency
- retrieval stall
- basis/operator overhead

## Stability

- long sequence drift
- overwrite interference
- collision curve
- multi-seed reproducibility

## Authority correctness

- rejected branch does not persist
- speculative suffix rollback works
- canonical shared state remains deterministic under the same accepted event sequence

---

# 17. 現時点での研究判断

元レポートの方向性は維持する。

特に有望:

```text
Local Exact
+
Canonical Shared Writer
+
Operator / Associative State
+
Module-specific Reader
+
Optional Context-as-Weights
+
Exact Archive
```

ただし、追加の最重要原則は次である。

> **Memory capacityを増やすことにはruntime costがある。必要品質を満たす最小capacityを選び、equal-budgetで比較する。**

> **Canonical authorityとmodule固有の観測能力を分離する。**

> **Memoryへの書き込みはtransactionalに扱い、棄却されたtoken・branch・仮説をauthoritative stateへ残さない。**

> **Runtime Context Memory、Long-lived validated memory、Temporary scratch、Hypothesis workspaceを混同しない。**

この4点を、今後のMemory実装・Mxx実験の固定原則とする。
