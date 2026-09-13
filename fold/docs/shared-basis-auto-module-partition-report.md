# Shared Basis Module Auto-Partition — 研究仮説・自動化設計レポート

作成日: 2026-09-13  
状態: **研究仮説 / 自動構造探索案。実証済み仕様ではない。**

関連文書:

- `fold/docs/shared-basis-runtime-output-impact-report.md`
- `fold/docs/experiment-ledger-and-handoff.md`

---

## 1. 目的

FOLDで検討中の Shared Basis 構造について、**どの module 群が同じ Basis を共有すべきかを自動決定する方法**を整理する。

本書の対象は、概念的に次の構造である。

```text
W_module = W_base + A_module @ B_shared
```

これを将来的に、moduleごとに所属する Basis Group を持つ形へ拡張する。

```text
W_module = W_base + A_module @ B_group(module)
```

ここで重要なのは、最初から人間が「数学module」「コードmodule」「言語module」のように意味分類することではない。

本書では、**各moduleが学習上どの更新空間を必要としているかを観測し、共有が有効な限り共有し、共有による干渉が確認された部分だけ自動的に分裂させる**方式を第一候補とする。

---

## 2. 結論

FOLD向けの第一候補は、次の方針である。

> **最大共有から開始し、必要性が観測された箇所だけ Split する。**

判定の中心は次の4信号とする。

1. **Subspace Residual** — 現在の Shared Basis で、そのmoduleが必要とする更新方向を十分表現できるか
2. **Gradient Conflict** — 同じ Basis を共有するmodule同士が、共有パラメータを相反する方向へ更新しようとしていないか
3. **Functional Interference** — 実際の validation / NLL / task performance 上で負の転移が起きていないか
4. **Runtime Reuse** — 同じ Basis を共有することで、保存容量だけでなく実行時計算も再利用できるか

自動化の判断は、単純な「分ける / 分けない」ではなく、少なくとも以下を区別する。

```text
共有維持
Rank増加
Basis Group Split
Private residual / singleton化
Merge
```

特に、**Rank不足とmodule間の本質的な非互換を区別すること**が重要である。

---

## 3. 中心仮説

### H1 — 最適なGroupingは意味分類ではなく更新部分空間で決まる

Shared Basis のmodule groupingは、module名、層番号、タスク名よりも、**各moduleが必要とする weight-update の低ランク部分空間の類似度**によって決まると仮定する。

すなわち、見かけ上異なるタスクでも同じ内部操作を必要とするなら同じ Basis を共有できる可能性がある。

逆に、同じカテゴリのmoduleでも必要な更新方向が大きく異なれば分離した方がよい可能性がある。

---

### H2 — Residual と Conflict の組合せで「容量不足」と「共有不適合」を区別できる

Shared Basis があるmoduleを十分表現できない場合、その原因は少なくとも2種類ある。

```text
A. Basisのrankが足りない
B. module同士が異なる方向を必要としており、共有そのものが不適切
```

この2つを区別せず Split すると、Basis Group が細分化し過ぎ、Shared Basis の利点を失う。

本書では、Subspace Residual と Gradient Conflict の組合せで両者を区別できると仮定する。

---

### H3 — Function-preserving Split により安全に専門化できる

親 Basis をそのまま子 Group に複製すれば、Split直後の出力を原理上維持したまま、その後の学習で専門化できる。

```text
B_parent
   |
   +-- copy --> B_child_0
   |
   +-- copy --> B_child_1
```

Split直後は、

```text
B_child_0 = B_parent
B_child_1 = B_parent
```

とする。

このため、構造変更自体による急激なモデル性能変化を避け、**共有から専門化へ連続的に移行できる**と期待する。

---

### H4 — Runtime Reuse を考慮したGroupingは、保存容量以外の利益を生む

同じ Basis を共有するmoduleが同じactivation入力 `x` を使える場合、

```text
z = B_shared @ x
```

を一度だけ計算し、複数moduleへ再利用できる可能性がある。

```text
              x
              |
        B_shared @ x
              |
              z
            /   \
        A_0 @ z A_1 @ z
```

したがってGroupingは、学習上の相性だけでなく、**実行グラフ上で Basis projection を共有可能か**も補助評価に入れる価値がある。

ただし優先順位は、

```text
品質互換性 > Runtime reuse > Storage reuse
```

とする。

品質を犠牲にして計算共有を優先してはならない。

---

## 4. Shared Basisで実際に共有されるもの

概念モデルを、

```text
Delta W_m = A_m @ B_g
```

とする。

`A_m` はmodule固有、`B_g` はGroup共有である。

このとき、同じ `B_g` を使うmoduleは、**更新が利用できる低次元方向を共有する**。

つまり、Shared Basis grouping とは単なる重み圧縮ではなく、

> 「このmodule群は、同じ低次元更新空間を使ってよい」

という構造的仮定である。

この仮定が正しいGroupでは、共有による圧縮・正の転移・計算再利用が期待できる。

間違っているGroupでは、表現能力不足、gradient conflict、negative transfer、出力均質化などが起き得る。

---

## 5. 自動分割で観測する4信号

## 5.1 Subspace Residual — 最重要信号

module `m` が本来必要としている更新方向を `G_m` とする。

現在の Basis `B_g` が張る部分空間への射影を `P_B` としたとき、概念的には次のような残差を測る。

```text
R_m = ||G_m - G_m P_B||_F^2 / ||G_m||_F^2
```

解釈:

```text
R_m が小さい
-> 現在の Shared Basis 内でmoduleの更新を十分表現できている

R_m が大きい
-> moduleが必要とする更新方向の一部が Shared Basis の外にある
```

これは module 分割判定の中心指標とする。

ただし、Residual が高いだけでは Split しない。

理由は、単純な rank 不足でも Residual は上がるためである。

---

## 5.2 Gradient Conflict — 共有方向の競合

同じ Basis を共有する各moduleが共有パラメータ `B_g` に与える gradient contribution を、

```text
g_m = dL_m / dB_g
```

とする。

module `i` と `j` の関係を見る簡易指標として、

```text
cos(g_i, g_j)
```

を使える。

概念的解釈:

```text
+1 に近い
-> 同じ方向へ Shared Basis を更新したい

0 付近
-> 互いにほぼ独立

負
-> 相反する方向へ更新したい
```

単発batchの値はノイズが大きいため、判定には移動平均または一定windowの統計を用いる。

---

## 5.3 Functional Interference — 最終確認

Residual / Gradient は構造推定用の内部信号である。

最終的な Split 採否は、実際のtask performanceでも確認する。

例:

- validation loss
- NLL
- accuracy
- calibration
- task-specific score
- cross-domain negative transfer

特に、あるmoduleを改善した結果、同じ Basis Group の別moduleが悪化するなら、共有干渉の疑いが強い。

したがって、**内部統計でSplit候補を作り、Functional評価で最終採否を決める**構成を推奨する。

---

## 5.4 Runtime Reuse — コスト側の補助信号

同じ Basis Group に属することで、

```text
B_g @ x
```

を実際に共有できるmodule群は、同一Groupに残す追加価値がある。

ただし、同じ重みを共有していても異なるactivationを入力するなら、projection計算そのものは共有できない。

したがってRuntime Reuseは、

```text
同じBasisを持つか
```

だけではなく、

```text
同じ実行点 / 同じ入力activation / reuse可能なscheduleか
```

まで見て評価する必要がある。

v0.1では品質判定へ直接混ぜず、**Split候補同士のtie-breakまたはcost評価**として扱うのが安全である。

---

## 6. 最重要Decision Table

自動化では、Residual と Conflict の組合せから少なくとも次を区別する。

| Subspace Residual | Gradient Conflict | 主な解釈 | 第一候補Action |
|---|---|---|---|
| 低 | 低 | 問題なく共有可能 | Share維持 |
| 高 | 低 | 共通方向だが容量不足の可能性 | Rank増加 |
| 高 | 高 | 必要空間そのものが異なる可能性 | Split候補 |
| 特定moduleのみ高 | 任意 | 外れmodule / 専門module | singleton / private residual候補 |
| 低 | 高 | 表現可能だが学習干渉 | Shadow Splitで確認 |

この表は v0.1 の中心ロジック候補とする。

重要なのは、

> **「Shared Basisで苦しんでいる」ことと「Shared Basisを分けるべき」ことは同義ではない。**

Rankを増やせば解決する問題をSplitで解決すると、構造が不必要に複雑化する。

---

## 7. 推奨Controller: Split -> Specialize -> Merge

自動化全体を、仮に **Basis Partition Controller** と呼ぶ。

Controllerは次の3操作を持つ。

```text
Split
Specialize
Merge
```

### 7.1 初期状態

物理的に共有可能なmoduleは、可能な限り少数の Basis Group から開始する。

例:

```text
Basis G0
 |- M0
 |- M1
 |- M2
 |- M3
```

形状が異なるなど共有不能なものは別bucketとする。

つまり「全modelで必ず1 Basis」ではなく、**共有可能性のハード制約ごとに最大共有**とする。

---

### 7.2 Observation Phase

一定stepの間は構造を変更せず、次の統計を蓄積する。

```text
per-module Subspace Residual
per-pair Gradient Similarity / Conflict
per-module validation contribution
Group rank utilization
runtime reuse potential
```

単発batchの結果では Split しない。

EMA、window average、複数seedなど、ノイズ耐性を持たせる。

---

### 7.3 Candidate Detection

Group内で、

```text
高Residual + 継続的Conflict
```

を持つmodule集合が形成された場合、Split candidate を作る。

ここではまだ構造変更を確定しない。

候補例:

```text
G0 = {M0, M1, M2, M3}

cluster A = {M0, M1, M2}
cluster B = {M3}
```

---

### 7.4 Function-Preserving Split

親 Basis を各候補Groupへコピーする。

```text
B_G0 -> B_G1
B_G0 -> B_G2
```

初期値は同一にする。

```text
B_G1 = B_G0
B_G2 = B_G0
```

これによりSplit直後は元の挙動を維持しやすい。

その後、各Groupを独立に学習させる。

---

### 7.5 Shadow Trial

Split候補は即採用せず、短い比較trialを行う。

比較対象:

```text
A. 親Groupを維持
B. Rankだけ増加
C. GroupをSplit
```

評価軸:

- validation loss / NLL
- task score
- cross-task interference
- parameter count
- serialized size
- peak memory
- training FLOPs
- inference FLOPs
- runtime reuse loss

Splitで性能が改善しても、コスト増が大き過ぎる場合は採用しない。

---

### 7.6 Commit

Shadow Trialで明確な利益が確認できた場合のみSplitを確定する。

```text
Basis G1
 |- M0
 |- M1
 |- M2

Basis G2
 |- M3
```

以後、各Groupは別々にrank調整可能とする。

---

### 7.7 Merge

一度分裂したGroupも永続固定にはしない。

長期間、

- subspace similarity が高い
- gradient conflict が低い
- merge trial で性能劣化しない

場合は、再統合候補にする。

SplitだけでMergeを持たない設計は、学習が進むほどGroup数が単調増加するため避ける。

---

## 8. Adaptive Rank との統合

Shared Basis Auto-Partition と Adaptive Rank は分離して考えない方がよい。

理想形は、Groupごとに必要rankを持つ構造である。

```text
Basis G0 rank=2
 |- M0
 |- M1

Basis G1 rank=6
 |- M2
 |- M3

Basis G2 rank=1
 |- M4
```

この構造なら、

```text
共通性が高いmodule群
-> 小rank Shared Basis

複雑なmodule群
-> 大rank Shared Basis

特殊module
-> singleton / private residual
```

と、必要な場所だけ容量を増やせる。

このためControllerのActionは、

```text
Share / Split
```

だけでは不足し、最低でも、

```text
KEEP
GROW_RANK
SHRINK_RANK
SPLIT
MERGE
PRIVATE_RESIDUAL
```

程度の操作空間を検討する価値がある。

ただし v0.1 実験では複雑化を避け、まず `KEEP / GROW_RANK / SPLIT` の3系統から始める方がよい。

---

## 9. Private Residual の位置付け

Group全体をSplitするほどではないが、特定moduleだけ不足する場合がある。

その場合、

```text
Shared update + small private residual
```

という構造を検討できる。

概念例:

```text
Delta W_m
  = A_m @ B_group
  + P_m
```

`P_m` は小さい専用補正である。

これにより、

- 共有の大部分は維持
- 特殊moduleだけ自由度追加
- Group増加を抑制

できる可能性がある。

ただし v0.1 では、自動分割そのものの効果を曖昧にしないため、Private Residual は後段候補とする。

---

## 10. 生のA/B重みクラスタリングを主判定にしない理由

単純に `A_m` や `B_m` の重み値を比較してclusterする方法は第一候補にしない。

低ランク分解には一般に、

```text
A B = (A Q) (Q^-1 B)
```

のような座標変換自由度がある。

同じ実効更新 `A B` を表していても、因子 `A` / `B` 自体の数値は異なり得る。

そのため、

```text
Aが近い
Bが近い
```

だけでmodule相性を判断すると、パラメータ化の取り方に依存する危険がある。

優先すべきは、

- 実効更新空間
- projection residual
- gradient interaction
- functional behavior

である。

---

## 11. 初版でDynamic Routerを使わない理由

module grouping 自動化と、推論時の dynamic routing は分ける。

初版では、

```text
入力ごとにRouterがBasisを選ぶ
```

方式は採用しない。

理由:

- inference graph が複雑になる
- cache / batching が難しくなる
- FLOPsが予測しづらくなる
- load balancing問題が増える
- deterministic evaluation が難しくなる
- Shared Basis自体の効果とRouter効果を分離しにくい

自動化するのは**学習中の構造探索**であり、学習完了後は、

```text
module_0 -> basis_group_0
module_1 -> basis_group_0
module_2 -> basis_group_2
module_3 -> basis_group_1
```

という静的対応表に固定する。

これにより推論側の複雑性を抑える。

---

## 12. v0.1 自動化案

初版は欲張らず、次の構成を推奨する。

### 12.1 Hard buckets

まず共有不能なmoduleを形状・接続点等のハード制約で分ける。

### 12.2 Max-share initialization

各bucket内は1 Basis Groupから開始する。

### 12.3 Warmup

一定stepは構造変更しない。

目的:

- Shared Basisをまず学習させる
- 初期gradientノイズで誤Splitしない

### 12.4 Statistics collection

一定windowで、

```text
Residual_m
GradientCos_ij
Validation_m
```

を記録する。

### 12.5 Decision

最小ルール:

```text
Residual low
-> KEEP

Residual high + Conflict low
-> GROW_RANK candidate

Residual high + Conflict high
-> SPLIT candidate
```

### 12.6 Trial

同一checkpointから、短期間だけ、

```text
keep
rank-grow
split
```

を分岐比較する。

### 12.7 Commit or Revert

明確な improvement/cost ratio があるActionだけ採用する。

### 12.8 Freeze structure

学習後半では構造変更頻度を下げ、最終的には固定する。

これにより最終収束を安定させる。

---

## 13. Split candidate の作り方

最初から高度なgraph clusteringを導入する必要はない。

v0.1では、Group内module間の類似行列を作るだけでよい。

例:

```text
S_ij = alpha * subspace_similarity(i, j)
     + beta  * gradient_similarity(i, j)
```

必要ならruntime reuseを小さい補助項として加える。

```text
     + gamma * runtime_reuse(i, j)
```

ただし、係数調整が新たな不確定性になるため、初版では、

```text
subspace signalを主
conflict signalをgate
runtimeはtie-break
```

程度に留める方が解釈しやすい。

高度なspectral clusteringやlearned routerは、単純法で限界が確認されてから検討する。

---

## 14. Split採用Gate

自動Splitを採用する最低条件として、以下を推奨する。

### Quality Gate

Split後に対象module群のvalidation性能が改善する。

かつ、非対象moduleを悪化させない。

### Stability Gate

複数windowまたは複数seedで同じSplit傾向が再現する。

### Cost Gate

増えた serialized size / FLOPs / memory に対して性能向上が妥当である。

### Regression Gate

Dense / independent / fixed-shared baseline と比較可能な形で結果を保存する。

### Determinism Gate

同じcheckpoint・seed・データ順なら、Group決定が再現できる。

---

## 15. 評価baseline

最低でも以下を比較する。

```text
A. Independent Basis per module
B. One Shared Basis per hard bucket
C. Fixed manual grouping
D. Auto-partition Shared Basis
```

可能なら追加で、

```text
E. Shared Basis + adaptive rank only
F. Auto-partition + adaptive rank
```

を比較する。

見るべきなのは単独accuracyではなく、

- validation loss
- NLL
- task score
- parameter count
- serialized bytes
- peak training memory
- peak inference memory
- train FLOPs
- inference FLOPs
- negative transfer
- cross-module failure correlation
- group count
- rank distribution

のPareto関係である。

---

## 16. 成功条件

Auto-Partition を成功とみなすのは、単にmanual groupingより精度が高い場合ではない。

理想的な成功は、

```text
Independent Basisに近い品質
+
Full Sharedに近い保存効率
+
少数Group
+
安定した静的推論構造
```

を同時に満たすこと。

より具体的には、

1. Full Sharedより明確に品質が高い
2. Independent BasisよりBasis総量が少ない
3. Group数が無制限に増えない
4. Split位置がseedに対して過度に不安定でない
5. Runtime reuse可能なGroupが一定量残る
6. 構造探索コストが最終学習コストを支配しない

を確認する。

---

## 17. 失敗パターン

### 17.1 Split Explosion

少しの差でもSplitし続け、最終的にほぼper-module Basisになる。

対策:

- persistence threshold
- minimum gain gate
- merge
- group-count penalty

---

### 17.2 Rank Growthで全部解決してしまう

Split候補が出ても、単純にrankを増やした方が常に良い可能性がある。

この場合、Auto-Partitionの価値は低い。

これは失敗ではなく重要な実験結果である。

---

### 17.3 Early Split Lock-in

学習初期の偶然のgradient差を構造差と誤認し、早期に分割してしまう。

対策:

- warmup
- EMA
- minimum observation window
- reversible trial

---

### 17.4 Group Oscillation

SplitとMergeを繰り返す。

対策:

- hysteresis
- cooldown期間
- split/merge閾値を分離

---

### 17.5 Quality only optimization

精度改善だけを見ると、最終的に専用Basisだらけになる。

対策:

objectiveに、

```text
quality
storage
runtime
complexity
```

を入れ、Pareto評価する。

---

## 18. 実験順序の推奨

### Experiment 1 — Residualが共有不適合を検出できるか

人工的に、

- 同じ低ランク方向を必要とするmodule群
- 異なる低ランク方向を必要とするmodule群

を作り、Residualで区別できるかを見る。

### Experiment 2 — Rank不足とSplit必要性を区別できるか

同一Groupについて、

```text
rank増加
vs
Split
```

を比較する。

### Experiment 3 — Function-preserving Split

Basisコピー直後に出力差が実質ゼロになることを確認する。

### Experiment 4 — Shadow Trial

同一checkpointから、

```text
keep
rank-grow
split
```

の短期trialで最終傾向を予測できるか調べる。

### Experiment 5 — Merge

意図的に過剰Splitした状態から、Merge判定で元に戻せるか確認する。

### Experiment 6 — Runtime reuse

同品質のGrouping候補間で、projection reuseが実際のthroughput / latencyへ効くか測る。

---

## 19. 実装前に確定すべき項目

コード実装へ入る前に、以下を別途仕様化する。

1. `module` の厳密な単位
2. Shared Basisを共有可能なhard bucket条件
3. `G_m` / subspace targetをどう推定するか
4. Residualの正規化方法
5. Gradient contributionの取得方法
6. observation window
7. EMA係数
8. Split threshold
9. Rank-grow threshold
10. Shadow Trialの長さ
11. Split採用score
12. Merge条件
13. cooldown / hysteresis
14. Group IDのserialization
15. checkpoint互換性
16. optimizer stateのSplit/Merge時移行
17. deterministic tie-break
18. experiment artifact形式

現時点ではこれらを固定しない。

本書は、まず **何を自動化すべきか / どの信号で判断するか** の仮説を決める文書とする。

---

## 20. v0.1 推奨仕様まとめ

初版の最小構成を以下とする。

```text
Initialization
  hard bucketごとに最大共有

Observation
  Subspace Residual
  Gradient Conflict
  Validation performance

Decision
  KEEP
  GROW_RANK candidate
  SPLIT candidate

Validation
  Shadow Trial

Commit
  改善時のみ構造変更

Inference
  static module -> basis_group mapping
```

初版では以下を入れない。

```text
Dynamic Router
Learned Router
Token単位Routing
高度なgraph clustering
Private Residual自動生成
頻繁なonline Split/Merge
```

まず、**Residual + Conflict + Shadow Trial だけで自動module分割が成立するか**を検証する。

---

# 21. 直感的な説明

Shared Basis を「会社の共通部署」と考える。

最初は全員が同じ部署を使う。

```text
共通部署
 |- A
 |- B
 |- C
 |- D
```

A/B/C/Dが同じ種類の道具を必要としているなら、そのまま共有するのが最も効率的である。

しかし学習していくと、Cだけ別の道具を必要とするかもしれない。

このときシステムはまず、

> 「部署が違うべきなのか？」

ではなく、

> 「単に机が足りないだけなのか？」

を確認する。

机不足なら、

```text
Rankを増やす
```

だけで済む。

一方、A/Bは右へ進みたいのにCは左へ進みたいような状態なら、

```text
部署1
 |- A
 |- B

部署2
 |- C
```

と分ける。

しかも、新しい部署をゼロから作るのではなく、元の部署をコピーしてから専門化する。

そのため、Splitした瞬間に能力を壊しにくい。

要するに、この自動化の仕事は、

> **「容量が足りない」のか、「そもそも別物を共有させている」のかを見分けること**

である。

FOLDで狙う最終形は、

> **できるだけ共有して小さく・速く保ち、共有すると性能を落とす部分だけ自動的に専門化するモデル**

である。

そのためのv0.1本命は、

> **Subspace Residualを主判定、Gradient Conflictを補助判定、Shadow Trialを最終Gate、推論時はStatic Group**

とする。
