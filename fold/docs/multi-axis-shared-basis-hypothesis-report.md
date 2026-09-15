# Multi-Axis Shared Basis — 多次元因子化ニューラル構造 仮説レポート

作成日: 2026-09-16  
状態: **研究仮説 / 比較実験提案。実証済み仕様ではない。現行FOLD設計の置換決定ではない。**

関連文書:

- `fold/docs/shared-basis-auto-module-partition-report.md`
- `fold/docs/shared-basis-runtime-output-impact-report.md`
- `fold/docs/architecture-v0.3.md`
- `fold/docs/research-plan.md`

---

## 1. 目的

本書は、現在FOLDで検討している Shared Basis 構造を、単一の `module` 軸から複数の独立した意味軸へ一般化できるかを検討する研究仮説である。

現行Shared Basisの概念モデルは次である。

```text
W_module = W_base + A_module @ B_shared
```

またはBasis Groupを導入した形では、

```text
W_module = W_base + A_module @ B_group(module)
```

と表せる。

この構造では、巨大な独立重みをmoduleごとに保持する代わりに、共有される低次元更新空間 `B_shared` / `B_group` と、module固有の小さい係数・射影 `A_module` を持つ。

本書では次の問いを立てる。

> `module` を一つの離散的な箱として扱う代わりに、Task / Stage / Role など複数の軸の座標として表し、その組合せから有効な更新を構成できないか。

狙いは単にテンソルの次元数を増やすことではない。

**能力・処理段階・状態に対する役割などを因子化し、組合せ数を増やしても保存パラメータを組合せ数に比例して増やしにくい構造を作れるか**を検証する。

---

## 2. 結論

第一候補は、現行FOLDを置換せず、次の順序で独立仮説として検証することである。

```text
MA-0: 現行 Shared Basis
      Shared Basis x Module

MA-1: 2軸因子化
      Shared Basis x Module/Task x Layer/Stage

MA-2: 3軸因子化
      Shared Basis x Module/Task x Layer/Stage x Role

MA-3: 必要な場合のみInteraction Residualを追加
      + Task x Role 等の組合せ固有差分

MA-X: 動的Context軸
      token / context依存の係数生成
      ※初期検証では扱わない
```

最初の検証対象は **MA-1** とする。

理由は次の通り。

1. 現行Shared Basisをそのまま比較対象として残せる。
2. 2軸なら失敗原因を追跡しやすい。
3. 組合せ汎化の有無を最小構成で検証できる。
4. tokenごとの動的weight生成を避け、GEMM中心の実行形を維持しやすい。
5. 成功後にRole軸やInteraction Residualへ段階的に拡張できる。

---

## 3. 「多次元」の意味

本仮説でいう多次元は、activation tensorが4次元・5次元であるという意味ではない。

通常のニューラルネットワークでも、

```text
Batch x Token x Feature
Batch x Head x Token x Feature
```

のような多次元tensorは普通に使用する。

本仮説の対象は、**モデルの適応・能力を指定する構造軸**である。

例:

```text
Task axis
- Language
- Composition
- Condition
- Retrieval

Stage axis
- Early
- Middle
- Late

Role axis
- Working-State Read
- Working-State Write
- Semantic-State Read
- Semantic-State Write
```

一つの処理点を、例えば次の座標として表す。

```text
Task  = Composition
Stage = Middle
Role  = Semantic-State Read
```

この座標から、有効な更新重みまたは更新係数を構成する。

したがって本仮説は、

> ニューラルネットワークを幾何学的な「4次元空間」にする案

ではなく、

> **適応パラメータを複数の意味軸で因子分解する案**

である。

---

## 4. 現行FOLDとの違い

### 4.1 現行Shared Basis

概念的には、module `m` に対して、

```text
Delta W_m = A_m @ B_g
```

を持つ。

同じBasis Groupに属するmoduleは、共有された低次元更新空間を使う。

これは、

> このmodule群は同じ低次元更新方向を共有してよい

という構造仮定である。

現在の `shared-basis-auto-module-partition-report.md` では、最大共有から開始し、Subspace Residual / Gradient Conflict / Functional Interference / Runtime Reuseを観測しながら、必要な場合のみSplitする方針を第一候補としている。

### 4.2 Multi-Axis案

Multi-Axis案では、`module` を一つのIDとして持つ代わりに、複数の軸へ分解する。

```text
Current:

Shared Basis
  |
  +-- Module A
  +-- Module B
  +-- Module C

Multi-Axis:

                  Shared Basis
                       |
       +---------------+---------------+
       |               |               |
     Task            Stage            Role
       |               |               |
       +---------------+---------------+
                       |
                 Effective Update
```

現在の構造が、

> 「どのmoduleか」

を選択するのに対し、Multi-Axisでは、

> 「Taskは何か」「Stageはどこか」「Roleは何か」

を独立に表現し、その座標の組合せから更新を構成する。

---

## 5. 中心数理仮説

### 5.1 単純な組合せ専用重み

Task数を `T`、Stage数を `S`、Role数を `R` とすると、全組合せは、

```text
C = T * S * R
```

個になる。

各組合せへ独立adapterを持たせる場合、組合せ数に比例してパラメータが増える。

これは能力軸を増やすほど不利になる。

### 5.2 Multi-Axis factorization

第一候補の概念モデルを次とする。

```text
z = B_shared @ x

gamma_k(t, s, r)
    = c_task[t, k]
    * c_stage[s, k]
    * c_role[r, k]

y_delta
    = sum_k gamma_k(t, s, r) * (A_k @ z)
```

すなわち、

```text
Delta W(t,s,r)
    = sum_k gamma_k(t,s,r) * A_k @ B_shared
```

とする。

ここで、

- `B_shared`: 共有される入力側低次元Basis
- `A_k`: 共有される出力側component
- `c_task`: Task軸の小さい係数
- `c_stage`: Stage軸の小さい係数
- `c_role`: Role軸の小さい係数
- `k`: 少数の共有component index

である。

これは厳密な最終仕様ではなく、**多次元因子化の効果を検証するための最小数学モデル候補**である。

本質は、組合せ `(t,s,r)` ごとに巨大な専用行列を保存せず、各軸の小さい係数と共有componentから有効更新を構成することにある。

---

## 6. パラメータスケーリング仮説

### 6.1 組合せ専用adapter

組合せ数を、

```text
C = T * S * R
```

とする。

各組合せが `A_c` を独立に持ち、入力側 `B_shared` のみ共有するなら、概念的なtrainable parameterは、

```text
P_combination
  ~= C * d_out * rank
   + rank * d_in
```

となる。

### 6.2 Multi-Axis

component数を `K` とすると、上記の最小案では、

```text
P_multi_axis
  ~= K * d_out * rank
   + rank * d_in
   + K * (T + S + R)
```

となる。

ここで `K << T*S*R` を維持できれば、軸の値を増やした際の保存量は、組合せ数の積ではなく、より加算的な増え方へ近づく。

例えば、

```text
Task  = 8
Stage = 8
Role  = 4
```

なら組合せは、

```text
8 * 8 * 4 = 256
```

通りになる。

Multi-Axis側では軸係数の個数は、

```text
8 + 8 + 4 = 20
```

個分の軸値に対する係数で表せる。

ただしこれは、

> 256個分の能力を20 parameterで完全表現できる

という意味ではない。

実際には `K`、`rank`、component本体、必要なInteraction Residualが存在する。

ここで主張しているのは、**能力の組合せ数と保存量の増加を直接比例させない可能性がある**というスケーリング仮説である。

---

## 7. 中心研究仮説

### H1 — 組合せ汎化が構造的に発生する

Task軸とRole軸を独立に学習できれば、学習時に直接十分観測していない組合せでも、既知の軸成分を再利用して性能を得られる可能性がある。

例:

```text
observed:
Language    x Semantic Read
Composition x Working-State Read

held-out:
Composition x Semantic Read
```

Multi-Axisが正しく因子化できていれば、held-out combinationでも、

```text
Composition方向
+
Semantic Read方向
```

の既学習成分から有効な処理を構成できる可能性がある。

この効果が確認されれば、Shared Basisは単なる圧縮ではなく、**compositional generalizationを誘導する構造**として評価できる。

### H2 — 能力数を増やしても保存量を増やしにくい

軸数・軸値を増加させても、組合せごとに独立adapterを作るより、保存parameter増加を抑えられると仮定する。

ただし、品質維持に必要な `K` やrankが組合せ数と同程度まで増えるなら、この利点は消える。

したがって評価対象は単純なparameter countではなく、

```text
quality / storage
quality / trainable parameter
quality / runtime cost
```

のPareto frontierとする。

### H3 — Shared Basis自動分割と両立する

Multi-Axisは `shared-basis-auto-module-partition-report.md` の方針を置き換えない。

Basis Groupは引き続き、

```text
B_group
```

として存在可能である。

概念的には、

```text
Delta W(t,s,r)
  = sum_k gamma_k(t,s,r) * A_k @ B_group(t,s,r)
```

のように、あるGroup内だけMulti-Axis factorizationを使える。

したがって、

```text
最大共有
 -> Multi-Axisで因子化
 -> Rank不足ならK/rank増加
 -> 軸間相互作用不足ならInteraction Residual
 -> 本質的共有不適合ならBasis Group Split
```

という階層的な構造探索が可能になる。

### H4 — 静的な軸なら実行時オーバーヘッドを抑えられる

Task / Stage / Roleがlayer単位・block単位など比較的静的に決まる場合、係数から有効adapterを事前合成またはcacheできる可能性がある。

```text
A_effective(t,s,r)
  = sum_k gamma_k(t,s,r) * A_k
```

とし、一定区間では、

```text
y_delta = A_effective @ (B_shared @ x)
```

として実行できる。

この場合、tokenごとに巨大なweightを生成する必要はない。

本仮説では、**推論速度を犠牲にしたparameter圧縮を成功とは扱わない。**

### H5 — 全能力が完全に分離可能とは限らない

Task / Stage / Roleの効果が完全に独立とは限らない。

例えば、

```text
Language x Write
```

でのみ必要な特殊処理が存在し、

```text
Language成分 + Write成分
```

だけでは表現できない可能性がある。

したがってMulti-Axisの失敗を、ただちに「rank不足」と判断してはならない。

非分離な相互作用を表現するため、必要な場合のみInteraction Residualを導入する。

---

## 8. Interaction Residual

Multi-Axisを純粋な完全因子分解に固定すると、軸間相互作用を表現できず品質を失う危険がある。

そのためMA-3以降では、必要な組合せだけに限定した小さいresidualを許容する。

例:

```text
Delta W
  = MultiAxisSharedUpdate
  + TaskRoleResidual(task, role)
  + PrivateResidual(optional)
```

優先順位は次とする。

```text
1. 共有維持
2. K / rank増加
3. pairwise Interaction Residual
4. private residual
5. Basis Group Split
```

ただし実際の順序はResidual / Conflict / validation結果で決める。

目的は、

> 何でも分解できると仮定する

ことではなく、

> **分解できる部分は最大限共有し、分解不能な相互作用だけを局所的に専用化する**

ことである。

---

## 9. 既存Auto-Partition信号との統合

既存Shared Basis自動分割案では、次を主要信号としている。

- Subspace Residual
- Gradient Conflict
- Functional Interference
- Runtime Reuse

Multi-Axis導入後は、これらを次のように解釈できる。

| 観測 | 主な仮説 | 第一候補Action |
|---|---|---|
| Residual低 / Conflict低 | 現因子化で十分 | 維持 |
| Residual高 / Conflict低 | component容量不足 | Kまたはrank増加 |
| 特定の軸値でResidual高 | その軸の表現不足 | 軸component増強 |
| 特定の軸ペアだけ失敗 | 非分離Interaction | pairwise residual候補 |
| 特定組合せのみ失敗 | 局所特殊化が必要 | private residual候補 |
| 継続的にResidual高 / Conflict高 | 共有自体が不適切 | Basis Group Split候補 |
| 品質同等でruntime reuse高 | 計算共有価値あり | 共有維持を優先 |

これにより、

```text
Shared Basisで性能が悪い
```

という現象を、

```text
rank不足
component不足
軸表現不足
軸間interaction不足
共有不適合
```

へ分解して診断できる可能性がある。

---

## 10. Routing / Control Laneとの関係

現行FOLDのroutingを概念的に、

```text
which module?
```

と見ると、Multi-Axisでは、

```text
Task?
Stage?
Role?
```

を決める構造へ拡張できる。

ただし、初期検証でrouting学習まで同時に導入すると、

```text
factorizationが悪いのか
routingが悪いのか
```

を区別できなくなる。

したがってMA-1 / MA-2の初期比較では、**軸ラベルを実験側で固定またはoracle指定し、factorization単体を評価する。**

Multi-Axisの有効性が確認された後にのみ、Control Laneへ軸推定を任せる。

将来のrouting候補:

```text
Input / State
    |
Control Lane
    |
    +-- Task distribution
    +-- Stage distribution
    +-- Role distribution
    |
Multi-Axis coefficient composition
```

なお、複数軸のsoft routingをtokenごとに行う場合、計算量・不安定性・routing collapseを別途評価する必要がある。

---

## 11. 動的Context軸を初期段階で扱わない理由

理論上は、

```text
Task x Stage x Role x Context
```

のように、context依存係数を追加できる。

さらに、

```text
gamma_k = f(context)_k
```

のような小型networkで係数を生成することも可能である。

しかし、tokenごとに有効weightを動的生成すると、

- weight materialization
- kernel fragmentation
- cache invalidation
- coefficient calculation
- routing overhead
- memory traffic

が増える可能性がある。

FOLDでは、保存parameter削減だけでなくruntime効率も重要である。

そのため初期段階では、

```text
Layer / Stage
Task
Role
```

のような比較的静的な軸に限定する。

Context軸は、**静的Multi-Axisが実測で有効だった後の別Gate**とする。

---

## 12. 現行設計との比較

| 項目 | 現行Shared Basis | Multi-Axis仮説 |
|---|---|---|
| 基本単位 | module | 複数軸の座標 |
| 共有 | Basis Group | Basis + axis component |
| 専門化 | `A_module` / Group Split | axis係数 / Interaction Residual / Split |
| 保存量 | module数に依存 | 軸値数とcomponent数に依存 |
| 組合せ能力 | 原則moduleを用意 | 軸組合せから構成可能 |
| 未学習組合せ汎化 | 副次的 | 中心仮説 |
| Routing | module選択 | 複数軸選択 |
| 学習難度 | 相対的に低い | 高い |
| 診断容易性 | 高い | 軸干渉の診断が必要 |
| 実行最適化 | Shared projection reuse可能 | 静的なら合成/cache可能 |
| 失敗リスク | 比較的低い | factorization biasが強い |
| 現時点の位置づけ | 現行候補 | 追加研究仮説 |

---

## 13. 最小比較実験 MA-1

最初から3軸以上へ進めない。

第一実験は、

```text
Shared Basis x Task x Layer/Stage
```

の2軸構造とする。

### 13.1 Baseline A — 現行Shared Basis

```text
Delta W_m = A_m @ B_shared
```

module / conditionごとに現在方式のadapterを持つ。

### 13.2 Baseline B — 組合せ専用adapter

Task x Stageの各組合せへ専用adapterを持つ。

これは保存量が多いが、factorization biasを持たない上限比較として使う。

### 13.3 Candidate C — Multi-Axis

```text
z = B_shared @ x

gamma_k(task, stage)
  = c_task[task,k] * c_stage[stage,k]

y_delta
  = sum_k gamma_k * (A_k @ z)
```

とする。

初期版ではTask / Stageはoracle labelを使用し、routing networkを学習しない。

---

## 14. 組合せ汎化テスト

Multi-Axisを評価するには、通常のvalidationだけでは不十分である。

学習組合せと未学習組合せを意図的に分離する。

例:

```text
Task:  A B C D
Stage: 1 2 3 4
```

16組合せのうち一部をtrainingから完全に除外する。

```text
train:
A1 A2 A3
B1 B2 B4
C1 C3 C4
D2 D3 D4

held-out:
A4 B3 C2 D1
```

評価では、

```text
seen-combination performance
held-out-combination performance
seen -> held-out generalization gap
```

を分ける。

重要なのは、held-out combinationの正解情報がtraining input / routing label / retrieval sourceへ漏れないことである。

---

## 15. 評価指標

最低限、次を同時に記録する。

### 品質

- validation NLL
- task accuracy / task-specific score
- seen-combination score
- held-out-combination score
- held-out generalization gap
- calibrationが必要なtaskではcalibration指標

### 容量

- trainable parameter count
- checkpoint bytes
- optimizer state bytes
- peak RAM
- peak VRAM

### 計算

- training FLOPs推定
- inference FLOPs推定
- wall-clock latency
- throughput
- effective adapter合成時間
- materialization有無
- shared projection reuse率

### 干渉

- Subspace Residual
- Gradient cosine / conflict
- per-axis validation degradation
- pairwise combination degradation

parameter countだけを改善して、latencyやVRAMが悪化した場合は成功としない。

---

## 16. 公平な比較条件

各方式で、少なくとも以下を揃える。

```text
same base model
same tokenizer
same train / validation / held-out split
same training tokens
same optimizer family
same numerical precision
same evaluation budget
same seed set
```

加えて、2種類の比較を分ける。

### A. Equal quality target

同等品質へ到達するために必要な、

```text
parameters
storage
training cost
latency
```

を比較する。

### B. Equal parameter budget

同じtrainable parameter budgetで、

```text
seen quality
held-out quality
generalization
```

を比較する。

可能なら複数seedで平均・分散を記録する。

単一seedの偶然を構造上の改善と扱わない。

---

## 17. 成功条件

MA-1を次段階へ進める最低条件候補を以下とする。

1. 現行Shared Basisと同等以上のseen-combination品質を維持する。
2. 組合せ専用adapterより明確に少ない保存量で近い品質を得る。
3. held-out combinationで現行方式より再現性のある改善を示す。
4. latency / peak VRAMが、保存量削減を打ち消すほど悪化しない。
5. 改善がrouting oracleや評価リークによるものではない。
6. `K` / rankを組合せ数近くまで増やさないと成立しない状態ではない。

特に、

> held-out combinationで改善せず、単にparameter compressionだけが得られた

場合は、Multi-Axisを「組合せ汎化構造」とは呼ばない。

その場合でも圧縮手段として価値があるかは別評価する。

---

## 18. 撤回・縮小条件

次のいずれかが継続的に確認された場合、仮説を縮小または棄却する。

### F1 — Kが組合せ数に比例して増える

必要component数 `K` が、

```text
T * S * R
```

に近い規模まで増えるなら、因子化による保存上の利点は弱い。

### F2 — held-out combinationが改善しない

seen品質だけ維持してheld-out combinationへ一般化しないなら、compositional generalization仮説は棄却する。

### F3 — Interaction Residualが大部分を占める

ほぼ全組合せへ専用residualが必要なら、軸分解仮定が不適切である。

### F4 — runtime overheadが大きい

有効adapterの合成・routing・materializationがボトルネックになり、通常adapterより明確に遅い場合は、runtime設計を変更するか採用しない。

### F5 — 軸の意味が学習で安定しない

人間がTask / Stage / Roleと名付けても、実際の更新部分空間がその分解に従わない可能性がある。

その場合は、意味ラベルによる固定軸ではなく、`shared-basis-auto-module-partition-report.md` のような**更新部分空間ベースの自動構造探索**を優先する。

---

## 19. 最重要リスク

### 19.1 Factorization Bias

最大の危険は、能力が独立軸へ分解可能だと先に決めつけることである。

実際のニューラル表現が強い非線形相互作用を必要とするなら、Multi-Axisはモデル容量を不自然に拘束する。

### 19.2 軸設計の恣意性

`Language`、`Reasoning`、`Read`、`Write` のような人間に分かりやすい分類が、ニューラルネットワーク内部の最適分解と一致する保証はない。

したがって「意味的にきれいだから採用する」ことは避ける。

### 19.3 Routing Complexity

複数軸を自動推定する場合、routingの誤りが増える。

Multi-Axis本体の能力とrouting能力を混同しないため、初期実験ではoracle軸を使う。

### 19.4 Gradient Coupling

一つのaxis coefficientが多数組合せへ影響するため、正の転移だけでなく負の転移も広範囲へ伝播する可能性がある。

このためper-axis / per-pairのGradient Conflictを観測する。

### 19.5 Runtime Materialization

理論上parameterが少なくても、毎tokenでweightを組み立てる構造は遅くなり得る。

静的合成・cache・shared projection reuseが成立する範囲を明示する。

---

## 20. FOLDに対する位置づけ

本仮説を一言で表すと、現行Shared Basisが、

> **多くのmoduleを同じ低次元更新空間から安く作る**

設計であるのに対し、Multi-Axis Shared Basisは、

> **能力そのものを複数の軸へ分解し、能力の組合せを座標から構成する**

設計である。

現行FOLDの否定ではない。

むしろ、

```text
Shared Basis
    |
module-specific adaptation
```

を、

```text
Shared Basis
    |
axis-factorized adaptation
    |
interaction residual when required
```

へ一般化できるかを問う。

成功すれば、FOLDの目標である、

```text
能力・役割の多様性を増やす
        |
        v
保存容量をできるだけ増やさない
        |
        v
必要箇所だけ専門化する
        |
        v
未学習組合せへの汎化も狙う
```

という方向を一つの構造で結び付けられる可能性がある。

---

## 21. 推奨研究順序

```text
Gate MA-0
現行Shared Basis baseline固定
        |
        v
Gate MA-1
Task x Stage 2軸
oracle routing
held-out combination test
        |
        +-- FAIL -> 原因分類して停止/縮小
        |
        v
Gate MA-2
Task x Stage x Role
        |
        v
Gate MA-3
必要な箇所だけInteraction Residual
        |
        v
Gate MA-4
Auto-Partitionとの統合
        |
        v
Gate MA-X
学習可能routing / dynamic context axis
```

同時に複数の新機構を導入しない。

特に、

- Multi-Axis
- learned routing
- dynamic context hypernetwork
- MoE
- quantization
- GPU kernel最適化

を同じ実験で導入すると、改善原因を特定できない。

---

## 22. 最終判断

現時点では、Multi-Axis Shared Basisは**採用済み設計ではなく、検証価値の高いFOLD派生仮説**として扱うべきである。

最も価値がある点はparameter圧縮そのものではない。

中心的な検証対象は、

> **軸ごとの学習成分を再利用することで、学習していない組合せへ構造的に一般化できるか**

である。

これが成立すれば、能力数の増加とモデルサイズ増加を切り離すだけでなく、FOLDのShared Basisを「共有圧縮機構」から「組合せ可能な能力表現」へ発展させられる可能性がある。

成立しなければ、現行Shared Basis + Auto-Partitionを維持し、Multi-Axisは圧縮用の限定手段または不採用とする。

したがって次の実装判断は、**MA-1の最小2軸実験を独立Gateとして設計し、現行Shared Basisをbaselineとして同条件比較すること**である。
