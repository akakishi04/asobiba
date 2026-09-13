# Shared Basis Module Auto-Partition — 研究仮説・自動化設計・実装準備レポート

作成日: 2026-09-13  
最終更新: 2026-09-13 / C68 accepted, C69 pending  
状態: **Living Design Document / 研究仮説 + 実験追随仕様。Auto-Partition本体は未実装。**

関連文書:

- `fold/docs/experiment-ledger-and-handoff.md`
- `fold/docs/shared-basis-runtime-output-impact-report.md`（別系統commitに存在。現在ブランチへ未統合の場合あり）

---

## 0. この文書の役割

この文書は一度書いて固定する研究メモではない。

目的は次の3つである。

1. Shared Basis の module grouping / auto split に関する仮説を保持する。
2. Cxx 実験の accepted result に合わせて仮説・優先順位・判定ロジックを修正する。
3. 実装開始時に、過去の会話を読み直さなくても最小実装へ着手できる状態を維持する。

### 更新ルール

accepted Cxx のうち、以下のいずれかに影響する結果が出た場合、この文書を更新する。

- rank / capacity
- native joint training
- factor/common co-adaptation
- seed robustness
- shared-vs-independent quality
- gradient / residual diagnostics
- runtime reuse
- recurrence stability
- split / merge / shadow trial

更新対象は最低でも次の4箇所とする。

```text
A. Evidence Ledger
B. Current Decision
C. Implementation Defaults
D. Open Questions / Next Validation
```

失敗した runner、import error、hash不一致、experiment ID不一致などの **invalid run は科学的根拠として追記しない**。

---

# 1. 目的

FOLD の Shared Basis 構造について、**どの module 群が同じ Basis を共有すべきかを自動決定する方法**を整理する。

現在の基礎表現は概念的に次である。

```text
W_module = W_base + A_module @ B_shared
```

将来的な Auto-Partition では、module ごとに所属する Basis Group を持つ形へ拡張する。

```text
W_module = W_base + A_module @ B_group(module)
```

重要なのは、最初から人間が、

```text
数学 module
コード module
言語 module
```

のように意味分類することではない。

第一候補は、**各 module が学習上どの更新空間を必要としているかを観測し、共有が有効な限り共有し、必要性が観測された箇所だけ分裂させる**方式である。

---

# 2. 現在の結論

FOLD向け第一候補は次である。

> **Hard constraint 内では最大共有から開始し、容量不足・学習不均衡・共有干渉を切り分けた後、本当に必要な箇所だけ Split する。**

初版の判断順は、単純な `Share / Split` ではない。

```text
KEEP
  ↓
CO-ADAPTATION CHECK
  ↓
GROW_RANK
  ↓
INTERFERENCE DIAGNOSIS
  ↓
SHADOW_SPLIT
  ↓
SPLIT
```

後段候補として、

```text
SHRINK_RANK
PRIVATE_RESIDUAL
MERGE
```

を追加する。

## 2.1 Split を急がない理由

C63-C68 により、性能低下には少なくとも以下が混在することが確認された。

```text
rank不足
optimizer / checkpoint問題
factor/commonのco-adaptation不均衡
seed依存の学習分散
本当の共有干渉
```

したがって、

> Shared Basis で性能が落ちた = Split が必要

とは扱わない。

---

# 3. Evidence Ledger — accepted experiments

この節は今後のCxx結果に合わせて継続更新する。

## 3.1 C63 — Condition rank frontier

Condition の post-hoc task-aware recovery では、

```text
rank1 -> 不足
rank2 -> 3 seedすべてを安定してDenseへ戻せない
rank4 -> 3/3 seedでDense以上
```

だった。

routed-weight ratio:

```text
rank4 = 0.78125
```

### Auto-Partitionへの意味

**性能不足を見てすぐSplitしてはいけない**ことを支持する。

このケースは rank を増やすだけで解決した。

したがって、

```text
Residual high + Conflict low
-> まず GROW_RANK
```

というDecision Tableの方向を強く支持する。

---

## 3.2 C64 — Language checkpoint / rank frontier

Language rank2 は、seed 20260911 でも step50 で Dense score 1.0 に到達した。

その後、固定600-stepまで学習すると 0.818182 へ低下した。

rank4 は3 seedすべてで固定最終checkpointまで1.0を維持した。

### Auto-Partitionへの意味

表現容量と optimizer / checkpoint 問題を分離する必要がある。

```text
低性能
!=
Basis group incompatibility
```

Split判定より前に training dynamics を見る必要がある。

---

## 3.3 C65 — Native direct joint training

Shared-basisを学習済みDenseから回復するのではなく、未学習初期状態から直接 joint training した。

結果:

```text
Composition rank2 -> 3/3 Dense一致
Condition rank4   -> ほぼ一致
Language rank4    -> 2/3 seedで大きく失敗
```

Languageではfactor lr=0.002、common lr=0.01だった。

### Auto-Partitionへの意味

Native shared-basis training 自体は成立する。

ただし、Group構造だけでなく **factor/commonの共適応速度** が重要。

---

## 3.4 C66 — Language factor LR frontier

Language rank4 / common lr0.01固定でfactor lrを比較した。

```text
factor lr 0.002 -> 失敗
factor lr 0.005 -> 1 seed未達
factor lr 0.010 -> 3/3 Dense一致
```

### Auto-Partitionへの意味

Gradient conflictのように見える現象が、実際には**片側が更新へ追従できていないco-adaptation問題**である可能性がある。

したがって、Conflict検出から直接Splitしてはいけない。

Decision cascadeに必ず、

```text
optimizer / co-adaptation check
```

を入れる。

---

## 3.5 C67 — aligned factor/common LR cross-task

ルール:

```text
factor_lr = common_lr
```

結果:

```text
Composition: 3/3 Dense一致
Language:    3/3 Dense一致
Condition:   128例validationで2 seedが1例差
```

Conditionの差は `1/128 = 0.0078125`。

### Auto-Partitionへの意味

単発・小規模validation差を構造差とみなしてはいけない。

構造変更前により大きな評価または複数seedのpersistenceを要求する。

---

## 3.6 C68 — Condition exhaustive held-out evaluation

Conditionの入力空間32,768のうち、学習256例を除く32,512例を各seedで全評価した。

```text
seed 20260911: Direct - Dense = +0.00249135
seed 20260912: Direct - Dense = -0.00639760
seed 20260913: Direct - Dense = +0.00658220
```

3 seed平均:

```text
+0.00089198
```

paired count合計:

```text
Dense-only correct  = 533
Direct-only correct = 620
Net Direct advantage = +87
```

### Auto-Partitionへの意味

Condition rank4 shared-basisが構造的にDenseより弱いとは言えない。

seedごとに勝敗が入れ替わるため、現時点では **seed-dependent optimization variance** とみなすのが妥当。

構造Split判定には複数seed / persistence gateが必須。

---

## 3.7 C69 — pending

予定:

```text
Condition rank4
factor/common lr0.01
12 seeds
各seed 32,512 exhaustive held-out trajectories
```

目的:

- C68のseed依存が再現するか
- Direct / Denseの勝敗比
- mean / median delta
- paired net advantage

を確認する。

### C69 accepted後の更新先

必ず以下を更新する。

```text
§2 Current Decision
§6 Decision Table
§13 Seed / Persistence Gate
§20 Implementation Defaults
§22 Open Questions
```

---

# 4. 中心仮説

## H1 — 最適Groupingは意味分類より更新部分空間で決まる

module grouping は、module名、タスク名、層番号より、**各moduleが必要とするeffective weight-updateの低ランク部分空間の類似性**で決まると仮定する。

見かけ上異なるタスクでも同じ内部操作を必要とすれば同じBasisを共有できる可能性がある。

逆に、同じカテゴリでも必要な更新方向が異なるなら分離した方がよい可能性がある。

### 現在の証拠状態

**未実証だが整合的。**

C63-C68は rank / optimizer / seed variance を示したが、更新部分空間によるgroupingそのものはまだ検証していない。

---

## H2 — ResidualとConflictで容量不足と共有不適合を区別できる

Shared Basis がmoduleを十分表現できない理由は少なくとも次の2種類ある。

```text
A. rank / capacity不足
B. module同士が異なる更新方向を必要としており共有自体が不適切
```

これを区別せずSplitするとBasis Groupが細分化し過ぎる。

### 現在の証拠状態

**部分支持。**

C63は「性能不足の一部はrank増加だけで解決する」ことを示した。

ただしResidual / Conflictセンサー自体は未検証。

---

## H3 — Function-preserving Splitで安全に専門化できる

親Basisを子Groupへコピーする。

```text
B_child_0 = B_parent
B_child_1 = B_parent
```

module固有係数 `A_module` を維持すれば、Split瞬間にはeffective weightを維持できる。

```text
A_m @ B_before == A_m @ B_after
```

### 重要な追加条件

weightだけでなく optimizer state も移行対象とする。

AdamWなら少なくとも、

```text
exp_avg
exp_avg_sq
step
```

を親から子へ複製する候補を第一案とする。

これを行わない場合、Split直後のforwardは同じでも学習軌道は保存されない。

### 現在の証拠状態

**理論上妥当 / 未実験。**

---

## H4 — Runtime ReuseをGroupingの補助価値として使える

同じBasisと同じactivation入力を使えるなら、

```text
z = B_group @ x
```

を共有できる可能性がある。

ただし、moduleごとにLayerNorm結果や実行点が異なる場合、同じBasisでもprojection結果は再利用できない。

優先順位:

```text
Quality compatibility
> Training stability
> Runtime reuse
> Storage reuse
```

Runtime Reuseはv0.1では **主判定にせずtie-break / cost評価** とする。

---

# 5. Shared Basisで共有されるもの

概念モデル:

```text
Delta W_m = A_m @ B_g
```

`A_m` はmodule固有、`B_g` はGroup共有。

同じ `B_g` を使うmoduleは、利用可能な低次元更新方向を共有する。

したがってShared Basis groupingは、単なる圧縮ではなく、

> このmodule群は同じ低次元更新空間を共有してよい

という構造仮定である。

---

# 6. 自動分割で観測する信号

## 6.1 Virtual Dense Effective-Weight Gradient Residual — 第一候補センサー

元レポートでは `G_m` をmoduleが必要とする更新方向としていた。

**実装時は、factor parameter gradientだけを `G_m` としない。**

理由:

現在のfactorized parameterization内部だけで、

```text
dL/dA
dL/dB
```

を見ると、すでに現在のBasis制約の影響を受けた勾配しか観測できず、Basis外へ出たい情報を失う可能性がある。

第一候補はeffective weightに対する仮想Dense gradientである。

```text
G_m = dL / dW_eff,m
```

where:

```text
W_eff,m = W_base + A_m @ B_g
```

`W` のshapeを `[out, in]`、`B_g` を `[rank, in]` とする場合、Basis row-spaceへの射影を、

```text
P_B = B_g^T (B_g B_g^T)^+ B_g
```

とし、

```text
R_m = ||G_m - G_m P_B||_F^2 / max(||G_m||_F^2, eps)
```

を第一候補Residualとする。

### 実装上の注意

- Up / Down roleは別々に測る。
- rank deficient時はpseudo-inverseまたはorthonormal basisを使う。
- full dense weightを永続保存する必要はない。
- diagnostic window中だけeffective-gradient統計を取れる設計にする。
- mixed precision時の数値安定性は別途確認する。

---

## 6.2 Gradient Conflict — 二種類を区別する

### Shared-parameter conflict

```text
g_m^shared = dL_m / dB_g
```

module pairについて、

```text
cos(g_i^shared, g_j^shared)
```

を見る。

これは「現在の共有parameterをどちらへ動かしたいか」を測る。

### Effective-gradient conflict

必要に応じ、

```text
cos(vec(G_i), vec(G_j))
```

も見る。

こちらはparameterizationより一段上の更新要求の類似性を見る。

### 判定原則

単一batchの負cosineではSplitしない。

```text
EMA
window statistics
複数validation slice
複数seed
```

でpersistenceを要求する。

---

## 6.3 Functional Interference — 最終Gate

内部センサーは候補生成用。

最終採否はfunctional評価で行う。

見るもの:

- validation loss
- NLL
- task score
- calibration
- negative transfer
- cross-module failure correlation

特に、あるmoduleを改善した結果、同Groupの別moduleが悪化する場合に共有干渉を疑う。

---

## 6.4 Co-Adaptation Signal — C66を受けて追加

Auto-Partition v0.1では、Residual / Conflictだけでなく、**factor/common学習速度の不均衡**を別要因として扱う。

最低限記録する候補:

```text
factor lr / common lr ratio
factor gradient norm
shared/common gradient norm
factor update norm
shared/common update norm
validation response
```

目的は、

```text
本当の共有不適合
```

と、

```text
片側が追従できないoptimizer imbalance
```

を区別すること。

---

## 6.5 Runtime Reuse — cost signal

品質判定へ直接混ぜない。

同じBasis / 同じactivation / 同じ実行点でprojectionを共有可能な場合のみ利益として計上する。

---

# 7. Current Decision Table

| Residual | Conflict | Co-adaptation | Functional | 第一候補Action |
|---|---|---|---|---|
| 低 | 低 | 安定 | 問題なし | KEEP |
| 高 | 低 | 安定 | 不足 | GROW_RANK |
| 任意 | 任意 | 不安定 | 不足 | OPTIMIZER / LR診断 |
| 高 | 高 | 安定 | 干渉あり | SHADOW_SPLIT |
| 低 | 高 | 安定 | 干渉なし | KEEPして観測継続 |
| 低 | 高 | 安定 | 干渉あり | SHADOW_SPLIT |
| 特定moduleのみ高 | 任意 | 安定 | 局所不足 | rank / singleton / private residual候補 |

### 重要

**SPLITは直接Actionにしない。**

最初に、

```text
SHADOW_SPLIT
```

へ入り、KEEP / RANK-GROW / SPLITを同checkpointから比較してからcommitする。

---

# 8. 推奨Controller

仮称:

```text
Basis Partition Controller
```

主要phase:

```text
MAX-SHARE INIT
↓
WARMUP
↓
OBSERVE
↓
DIAGNOSE
↓
SHADOW TRIAL
↓
COMMIT / REVERT
↓
SPECIALIZE
↓
(optional) MERGE
```

---

## 8.1 Hard Bucket

最初に共有不能なmoduleを形状・接続点・roleなどのハード制約で分ける。

全modelを必ず1 Basisにするのではなく、**物理的に共有可能なbucket内で最大共有**する。

---

## 8.2 Warmup

一定stepは構造変更しない。

目的:

- Shared Basisをまず形成する
- 初期gradientノイズで誤Splitしない
- C66型のco-adaptation問題をSplitと誤認しない

---

## 8.3 Observation Window

収集候補:

```text
per-module virtual-dense residual
per-pair shared-gradient cosine
per-pair effective-gradient cosine
factor/common update norm ratio
per-module validation contribution
group rank utilization
runtime reuse potential
```

---

## 8.4 Candidate Detection

候補生成は内部信号で行う。

例:

```text
Residual high + Conflict low
-> rank-grow candidate

Residual high + persistent Conflict
-> shadow-split candidate

Conflict high + co-adaptation unstable
-> optimizer diagnostic first
```

---

## 8.5 Shadow Trial

同一checkpointから短期間だけ分岐する。

```text
A. KEEP
B. GROW_RANK
C. SPLIT
```

必要なら、

```text
D. optimizer/co-adaptation adjustment
```

も比較する。

評価:

- quality
- NLL
- negative transfer
- parameter bytes
- runtime bytes
- training/inference FLOPs
- structure complexity

---

## 8.6 Commit / Revert

Splitを採用する最低条件:

```text
Quality benefit is persistent
AND
non-target regression is acceptable
AND
rank-grow / optimizer alternativeでは説明できない
AND
cost increase is acceptable
```

満たさなければrevertする。

---

# 9. Function-Preserving Split

Split直前:

```text
G0 = {M0, M1, M2, M3}
B_G0
```

Split候補:

```text
G1 = {M0, M1, M2}
G2 = {M3}
```

初期化:

```text
B_G1 = clone(B_G0)
B_G2 = clone(B_G0)
```

`A_module`は維持する。

## 9.1 Optimizer state migration

AdamW系なら第一候補:

```text
B_G0.exp_avg    -> clone to G1/G2
B_G0.exp_avg_sq -> clone to G1/G2
B_G0.step       -> clone to G1/G2
```

optimizer stateをリセットする案は、Function-preservingの学習軌道版ではないため別trialとして扱う。

---

# 10. Adaptive Rankとの統合

Auto-PartitionとAdaptive Rankは分離しない。

理想:

```text
G0 rank=2  -> M0,M1
G1 rank=6  -> M2,M3
G2 rank=1  -> M4
```

ただし、現在までの実験から、**一律rank ruleは採用しない**。

C63-C68の現時点の示唆:

```text
Composition: rank2で強い
Language:    rank2 capacityは足りるがrank4の方が固定scheduleに安定
Condition:   rank4がpost-hoc robust point、nativeではseed varianceあり
```

---

# 11. Private Residual

将来候補:

```text
Delta W_m = A_m @ B_group + P_m
```

特定moduleだけ不足する場合に、Group全体Splitを避けられる可能性がある。

v0.1では入れない。

理由:

Auto-Partition / Rank / Private Residualを同時導入すると原因切り分けが難しくなる。

---

# 12. 生のA/B重みクラスタリングを主判定にしない

低ランク分解には座標自由度がある。

```text
A B = (A Q)(Q^-1 B)
```

同じeffective updateでもfactor値は変わり得る。

したがって優先するのは、

```text
effective update space
virtual-dense gradient residual
gradient interaction
functional behavior
```

である。

---

# 13. Seed / Persistence Gate

C67-C68により、このGateは必須とする。

単一seed・単一validation sliceで構造変更しない。

v0.1の原則:

```text
同じ異常が複数windowで継続
AND
複数seedまたは独立validation sliceで再現
```

してからShadow Trial候補へ上げる。

具体thresholdはC69以降の結果で決める。

---

# 14. 初版でDynamic Routerを使わない

module grouping自動化と推論時dynamic routingは別問題。

v0.1では学習中に構造探索し、最終的に、

```text
module_0 -> basis_group_0
module_1 -> basis_group_0
module_2 -> basis_group_2
```

という静的mapへ固定する。

理由:

- inference graph単純化
- cache / batching容易化
- FLOPs予測可能性
- deterministic evaluation
- Shared Basis効果とRouter効果の分離

---

# 15. Auto-Partition v0.1 scope

## 入れる

```text
Hard bucket
Max-share initialization
Warmup
Virtual-dense residual observer
Gradient conflict observer
Co-adaptation observer
Functional validation hook
KEEP / GROW_RANK / SHADOW_SPLIT recommendation
Shadow Trial harness
Static final group map
```

## 入れない

```text
Learned Router
Token routing
Online frequent Split/Merge
Private Residual auto-generation
高度なgraph clustering
完全自律threshold tuning
```

---

# 16. Split採用Gate

## Quality Gate

Split後に対象module群のvalidation性能が改善する。

## Non-target Regression Gate

非対象moduleを許容範囲以上に悪化させない。

## Alternative Explanation Gate

以下で同等以上に解決できないこと。

```text
optimizer / LR adjustment
rank grow
checkpoint policy
```

## Stability Gate

複数window / seed / validation sliceで傾向が再現する。

## Cost Gate

増えたserialized bytes / resident bytes / FLOPs / memoryに対する利益が妥当。

## Determinism Gate

同checkpoint・seed・data orderなら同じ候補判定を再現できる。

---

# 17. 評価Baseline

最低限:

```text
A. Independent Basis per module
B. One Shared Basis per hard bucket
C. Fixed manual grouping
D. Auto-partition Shared Basis
E. Shared Basis + adaptive rank only
F. Auto-partition + adaptive rank
```

評価:

- task score
- NLL
- calibration
- parameter count
- serialized bytes
- resident bytes
- peak training memory
- peak inference memory
- train FLOPs
- inference FLOPs
- negative transfer
- failure correlation
- group count
- rank distribution
- split/merge count
- structure-search overhead

単一scoreではなくParetoで判断する。

---

# 18. 失敗パターン

## Split Explosion

少しの差でSplitし続け、per-module Basisへ崩壊。

対策:

- persistence threshold
- minimum gain
- complexity penalty
- merge

## Rank Growthで全部解決

これは失敗ではなく重要な結果。

Auto-Partitionが不要でAdaptive Rankだけで足りるなら、より単純な設計を採用する。

## Early Split Lock-in

初期gradient差を構造差と誤認。

対策:

- warmup
- EMA
- reversible shadow trial

## Co-adaptation False Positive

C66型。

共有不適合ではなく、factor/common更新速度の不均衡をSplit理由と誤認。

対策:

- update norm観測
- LR ratio診断
- optimizer trialをSplitより先に行う

## Seed False Positive

C67-C68型。

小さいvalidationまたは特定seedだけの差を構造差と誤認。

対策:

- larger validation
- exhaustive evaluation if possible
- multi-seed persistence

## Group Oscillation

Split/Mergeを反復。

対策:

- hysteresis
- cooldown
- split/merge threshold分離

---

# 19. Auto-Partition専用の実験順序

Gate C shared-basis候補の基礎が確定した後、次を推奨する。

## AP1 — Virtual Dense Residual Sensor validation

人工taskで、

- Basis内方向だけを要求するmodule
- Basis外方向を要求するmodule

を作る。

Residualが区別できるか確認。

## AP2 — Rank不足 vs Split必要性

同じcheckpointから、

```text
GROW_RANK
SPLIT
```

を比較し、Residual + Conflictの分類が正しいか確認。

## AP3 — Co-adaptation false-positive test

C66型のLR mismatchを人工的に作り、ControllerがSplitではなくoptimizer問題として判定できるか確認。

## AP4 — Function-preserving Split

forward output / logits / state digestがSplit直後に一致するか確認。

optimizer state migrationも検証。

## AP5 — Shadow Trial predictiveness

短期trialの選択が長期学習結果と一致するか確認。

## AP6 — Merge

過剰Split状態から安全に統合できるか確認。

## AP7 — Runtime reuse

同品質Grouping候補で実latency / throughput / memoryを比較。

---

# 20. Implementation Defaults — 実装開始時の暫定既定値

ここはaccepted Cxx / APx結果で更新する。

## 20.1 現在固定してよいもの

```text
Grouping principle: max-share within hard bucket
Inference mapping: static
Primary residual target: virtual dense effective-weight gradient
Split mechanism: function-preserving basis clone
Split adoption: shadow trial required
Runtime reuse: secondary cost signal
Dynamic router: out of v0.1
Private residual: out of v0.1
```

## 20.2 まだ固定しないもの

```text
Residual threshold
Conflict threshold
EMA coefficient
Observation window length
Warmup length
Shadow trial length
Rank grow quantum
Maximum group count
Merge threshold
Cooldown length
Complexity penalty
```

これらは実験から決める。

---

# 21. 実装開始時の最小コード構成

Auto-Partition実装を開始するとき、最初から構造変更まで作らない。

## Pass AP-OBSERVE — 観測のみ

第一実装は **read-only observer** とする。

候補ファイル構成:

```text
fold_lm/v05/partitioning.py

  PartitionObserver
  PartitionStatsWindow
  ModuleGradientStats
  GroupStats
  PartitionRecommendation
```

責務:

- module/group canonical keyの列挙
- virtual dense gradient residual計測
- gradient cosine計測
- update norm / co-adaptation計測
- JSON artifact出力

禁止:

```text
weight mutation
rank mutation
split
merge
router変更
```

### AP-OBSERVE Gate

- deterministic
- production forward結果を変えない
- observer無効時のruntime regressionなし
- diagnostic artifactがseed再現可能

---

## Pass AP-DECIDE — Recommendation only

次に、

```text
KEEP
GROW_RANK
SHADOW_SPLIT
OPTIMIZER_DIAGNOSTIC
```

のrecommendationを返す。

まだmodel mutationはしない。

---

## Pass AP-SHADOW — 分岐trial

checkpoint cloneから、

```text
keep
rank-grow
split
optimizer-adjust
```

を比較するharnessを追加。

---

## Pass AP-MUTATE — 構造変更

ここで初めて、

- Group Split
- optimizer state migration
- checkpoint serialization
- deterministic group ID

を実装する。

---

## Pass AP-MERGE — 後段

Splitが成立してからMergeを実装する。

---

# 22. 実装開始前に残るOpen Questions

1. moduleの厳密単位
2. hard bucket条件
3. Up/Downを同じgroup decisionにするか別判定にするか
4. virtual dense gradientの取得コスト
5. residualの正規化
6. shared-gradientとeffective-gradient conflictのどちらを主にするか
7. observation window
8. warmup
9. thresholds
10. rank grow step
11. shadow trial長
12. functional score aggregation
13. optimizer state split/merge
14. deterministic group ID
15. checkpoint schema
16. group map serialization
17. merge criterion
18. runtime reuse estimator
19. structure-search overhead budget
20. multi-worker / distributed training時の統計集約

---

# 23. 実験結果をこの文書へ反映するテンプレート

新しいaccepted resultがAuto-Partitionへ影響する場合、次の形で追記する。

```markdown
## Cxx — <name>

Observed:
- ...

Supports:
- H?

Weakens / revises:
- H? / Decision ?

Implementation consequence:
- ...

Still unknown:
- ...
```

さらに、必要に応じて以下を直接修正する。

```text
Decision Table
Implementation Defaults
Open Questions
Auto-Partition experiment order
```

古い記述を残すだけでなく、**実験で否定された既定値は本文から降格・修正する**。

---

# 24. 実装開始時の初動チェックリスト

実装担当は最初に以下を読む。

```text
1. experiment-ledger-and-handoff.md
2. この文書
3. 最新Shared Basis core / benchmark implementation
```

その後、次を確認する。

```text
[ ] Gate C candidate familyがまだ W_base + A @ B 系か
[ ] 最新accepted rank policy
[ ] 最新co-adaptation rule
[ ] recurrence/runtimeで追加制約が入っていないか
[ ] observer対象module単位が確定しているか
[ ] checkpoint schemaが変わっていないか
```

不明な場合でも、最初の実装はAP-OBSERVEに限定する。

これにより構造仕様が多少変わっても無駄実装を減らす。

---

# 25. 直感的な説明

Shared Basisを「会社の共通部署」と考える。

最初は共有可能な人たちが同じ部署を使う。

```text
共通部署
 |- A
 |- B
 |- C
 |- D
```

問題が起きたとき、すぐ部署を分けない。

最初に、

```text
机が足りない？           -> Rank不足
仕事の速度が合わない？   -> Co-adaptation問題
本当に方向が対立する？   -> Shared incompatibility
たまたまその日だけ？     -> Seed / validation noise
```

を区別する。

それでもA/Bは右へ進み、Cは継続的に左へ進みたがるなら、初めて、

```text
部署1
 |- A
 |- B

部署2
 |- C
```

をShadow Trialする。

新部署は元の部署をコピーして作るため、分けた瞬間には仕事の結果を壊さない。

FOLDで狙う最終形は、

> **できるだけ共有して小さく・速く保ち、容量・optimizer・seed差では説明できない本物の干渉だけを自動的に専門化するモデル**

である。

---

# 26. 現時点のv0.1本命

```text
Max Share
+ Virtual Dense Residual
+ Gradient Conflict
+ Co-adaptation Check
+ Multi-seed Persistence
+ Functional Gate
+ Shadow Trial
+ Static Final Grouping
```

Auto-Partitionの仕事は、単に「似たmoduleを集める」ことではない。

> **容量不足・学習不均衡・seed分散・本当の共有不適合を切り分け、必要なときだけ安全に構造を分けること。**

この原則を、今後のaccepted Cxx / APx結果に合わせて更新し続ける。