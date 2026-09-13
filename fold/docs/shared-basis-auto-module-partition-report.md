# Shared Basis Module Auto-Partition — 研究仮説・自動化設計・実装準備レポート

作成日: 2026-09-13  
最終更新: 2026-09-14 / C69 accepted, C70 pending  
状態: **Living Design Document / 研究仮説 + 実験追随仕様。Auto-Partition本体は未実装。**

関連文書:

- `fold/docs/experiment-ledger-and-handoff.md`
- `fold/docs/shared-basis-runtime-output-impact-report.md`（別系統commitに存在する場合あり）

---

## 0. この文書の役割

この文書は固定レポートではなく、Shared Basisのmodule grouping / auto splitに関する**実装前のliving spec**である。

accepted Cxxが以下へ影響した場合に更新する。

```text
rank / capacity
native shared-basis training
factor/common co-adaptation
seed / validation robustness
shared grouping compatibility
residual / gradient diagnostics
runtime reuse
recurrence / structure-change safety
```

最低更新対象:

```text
Evidence Ledger
Current Decision / Decision Table
Implementation Defaults
Open Questions / Next Validation
```

invalid runは科学的根拠にしない。

---

# 1. 目的

FOLDのShared Basisについて、**どのmodule群が同じBasisを共有してよいかを自動決定する方法**を作る。

基礎表現:

```text
W_module = W_base + A_module @ B_shared
```

将来のgrouping:

```text
W_module = W_base + A_module @ B_group(module)
```

意味カテゴリを人間が先に固定するのではなく、各moduleが実際に必要とする更新空間・学習干渉・容量要求を観測する。

---

# 2. Current Decision

FOLD向け第一候補:

> **Hard constraint内では最大共有から開始し、容量不足・optimizer/co-adaptation・seed分散・本物の共有干渉を順に切り分け、本当に必要な場合だけSplitする。**

初版の判断順:

```text
KEEP
 ↓
CO-ADAPTATION CHECK
 ↓
GROW_RANK
 ↓
PERSISTENCE / DIRECTIONALITY CHECK
 ↓
INTERFERENCE DIAGNOSIS
 ↓
SHADOW_SPLIT
 ↓
SPLIT
```

後段候補:

```text
SHRINK_RANK
PRIVATE_RESIDUAL
MERGE
```

## 2.1 Splitを急がない理由

C63-C69により、見かけ上の性能差には少なくとも次が混在する。

```text
rank不足
optimizer / checkpoint問題
factor/common co-adaptation不均衡
seed依存の最適化分散
validation sampling差
本当の共有干渉
```

したがって、

```text
Shared Basisで性能が落ちた
```

だけではSplit理由にならない。

## 2.2 C69後の追加原則

**複数seedで差が存在すること**と、**複数seedで同じ方向の差が再現すること**は別である。

C69では12 seedすべてに小さな差があっても勝敗は6対6だった。

よってv0.1では、

```text
multi-seed persistence
+
directional consistency
+
functional materiality
```

を構造変更候補の最低条件とする。

方向が混在し中心がほぼゼロなら、第一候補Actionは`KEEP`である。

---

# 3. Evidence Ledger — accepted experiments

## 3.1 C63 — Condition rank frontier

Post-hoc task-aware recovery:

```text
rank1 -> 不足
rank2 -> 3 seedすべてを安定してDenseへ戻せない
rank4 -> 3/3 seedでDense以上
```

rank4 routed-weight ratio:

```text
0.78125
```

### 意味

性能不足を見てすぐSplitしない。

```text
Residual high + Conflict low
-> まず GROW_RANK
```

を支持する。

---

## 3.2 C64 — Language checkpoint / rank frontier

Language rank2はseed 20260911でもstep50でDense score 1.0へ到達したが、その後0.818182へ低下した。

rank4は3 seedすべて固定最終checkpointまで1.0。

### 意味

```text
低性能 != Basis group incompatibility
```

Optimizer / checkpointをSplit判定より先に見る。

---

## 3.3 C65 — Native direct joint training

未学習状態からShared Basisを直接joint training。

```text
Composition rank2 -> 3/3 Dense一致
Condition rank4   -> ほぼ一致
Language rank4    -> 2/3 seedで大きく失敗
```

Languageではfactor lr0.002、common lr0.01。

### 意味

Native shared-basis training自体は成立するが、factor/commonの共適応速度が重要。

---

## 3.4 C66 — Language factor LR frontier

```text
factor lr 0.002 -> 失敗
factor lr 0.005 -> 1 seed未達
factor lr 0.010 -> 3/3 Dense一致
```

### 意味

共有干渉に見える現象が、optimizer imbalanceで説明できる場合がある。

Decision cascadeへ必ずco-adaptation checkを入れる。

---

## 3.5 C67 — aligned factor/common LR

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

### 意味

小さいvalidation差を構造差と扱わない。

---

## 3.6 C68 — Condition exhaustive held-out

学習256例を除く32,512例を3 seedで全評価。

```text
20260911: Direct - Dense = +0.00249135
20260912: Direct - Dense = -0.00639760
20260913: Direct - Dense = +0.00658220
```

平均:

```text
+0.00089198
```

paired total:

```text
Dense-only  = 533
Direct-only = 620
Net Direct  = +87
```

### 意味

Condition rank4が構造的にDenseより弱いとは言えず、seed varianceが有力だった。

---

## 3.7 C69 — Condition 12-seed exhaustive robustness

Accepted commit:

`632469b400e1cf325882d8c7aaf0d8f509357aab`

固定条件:

```text
Condition rank4
factor/common lr0.01
260 steps
12 seeds: 20260911..20260922
各seed exhaustive held-out 32,512
```

結果:

```text
Direct win seeds = 6
Dense win seeds  = 6
Tie              = 0
sign test p      = 1.0
mean delta       = -0.00025117894
median delta     = -0.00006151199
min              = -0.00639760494
max              = +0.00658220053
Dense-only total = 1446
Direct-only total= 1348
Net Direct       = -98
```

12 seed × 32,512 = 390,144 held-out trajectoriesに対し、pooled差は98例。

### Auto-Partitionへの意味

C69はSeed / Persistence Gateを強く更新する。

1. **複数seedで差が出るだけでは構造変更理由にならない。**
2. 勝敗方向が6対6なら、persistent directional deficitではない。
3. mean/medianがほぼゼロ中心で符号混在なら、rank-grow / splitよりKEEPを優先する。
4. 単一seedの大きめな差を全体傾向として扱わない。
5. 現Condition rank4に対し、追加rankやSplitを正当化する証拠はない。

### Supports

- Seed False Positive対策
- Multi-seed Persistence
- Directionality Gate
- Max-share維持

### Still unknown

- より大規模・自然なtaskで同じ傾向か
- shared group同士の本当のgradient conflict
- runtime-native実行でrecurrence差が出ないか

---

# 4. 中心仮説

## H1 — 最適Groupingは意味分類より更新部分空間で決まる

module名や分野名より、各moduleが必要とするeffective weight-updateの低ランク部分空間の類似性でgroupingを決める。

状態: **未実証だが整合的。**

C63-C69は容量・optimizer・seed varianceを切り分けたが、groupingそのものはまだ未検証。

---

## H2 — ResidualとConflictで容量不足と共有不適合を区別できる

主因候補:

```text
A. rank / capacity不足
B. module同士が異なる更新方向を必要とする共有不適合
```

状態: **部分支持。**

C63はrank増加だけで解決するケースを示した。Residual / Conflictセンサー自体は未検証。

---

## H3 — Function-preserving Splitで安全に専門化できる

```text
B_child_0 = B_parent
B_child_1 = B_parent
```

`A_module`を維持すればSplit直後のeffective weightを保存できる。

AdamW optimizer stateも候補としてcloneする。

```text
exp_avg
exp_avg_sq
step
```

状態: **理論上妥当 / 未実験。**

---

## H4 — Runtime ReuseはGroupingの補助価値

同じBasis・activation・実行点ならprojectionを共有できる可能性がある。

優先順位:

```text
Quality compatibility
> Training stability
> Runtime reuse
> Storage reuse
```

Runtime Reuseはv0.1では主判定にしない。

C70以降でruntime-native formの数値・再帰安全性を確認する。

---

# 5. 観測信号

## 5.1 Virtual Dense Effective-Weight Gradient Residual

第一候補:

```text
G_m = dL / dW_eff,m
W_eff,m = W_base + A_m @ B_g
```

Basis row-space射影:

```text
P_B = B_g^T (B_g B_g^T)^+ B_g
```

Residual:

```text
R_m = ||G_m - G_m P_B||_F^2 / max(||G_m||_F^2, eps)
```

注意:

- Up / Down roleは別々に測る。
- rank deficient時はpseudo-inverseまたはorthonormal basis。
- full dense weightの永続保存は不要。
- diagnostic window中だけ取得する。

---

## 5.2 Gradient Conflict

Shared-parameter conflict:

```text
g_m^shared = dL_m / dB_g
cos(g_i^shared, g_j^shared)
```

Effective-gradient conflict:

```text
cos(vec(G_i), vec(G_j))
```

単一batchのnegative cosineではSplitしない。

```text
EMA
window statistics
独立validation slice
multi-seed directionality
```

を要求する。

---

## 5.3 Functional Interference — 最終Gate

内部センサーは候補生成のみ。

最終採否:

- validation loss / NLL
- task score
- calibration
- negative transfer
- failure correlation

---

## 5.4 Co-Adaptation Signal

最低候補:

```text
factor lr / common lr ratio
factor gradient norm
shared/common gradient norm
factor update norm
shared/common update norm
validation response
```

目的:

```text
共有不適合
vs
optimizer imbalance
```

の切り分け。

---

## 5.5 Seed / Directionality Signal

C69を受けて独立signalとして明示する。

最低記録:

```text
per-seed functional delta
win/loss/tie count
mean / median delta
paired failure counts
sign consistency
```

単純な「平均が負」だけで構造変更しない。

---

## 5.6 Runtime Reuse — cost signal

品質判定へ直接混ぜない。

同じBasis / activation / 実行点でprojectionを共有できる場合のみ利益として計上。

---

# 6. Current Decision Table

| Residual | Conflict | Co-adaptation | Seed direction | Functional | 第一候補Action |
|---|---|---|---|---|---|
| 低 | 低 | 安定 | 混在/問題なし | 問題なし | KEEP |
| 高 | 低 | 安定 | 一貫 | 不足 | GROW_RANK |
| 任意 | 任意 | 不安定 | 任意 | 不足 | OPTIMIZER / LR診断 |
| 任意 | 任意 | 安定 | 符号混在・中心≈0 | 小差 | KEEP / 観測継続 |
| 高 | 高 | 安定 | 一貫 | 干渉あり | SHADOW_SPLIT |
| 低 | 高 | 安定 | 不明 | 干渉なし | KEEPして観測継続 |
| 低 | 高 | 安定 | 一貫 | 干渉あり | SHADOW_SPLIT |
| 特定moduleのみ高 | 任意 | 安定 | 一貫 | 局所不足 | rank / singleton / private residual候補 |

**SPLITは直接Actionにしない。**

必ずShadow Trialで、

```text
KEEP
GROW_RANK
SPLIT
OPTIMIZER_ADJUST
```

を同checkpointから比較する。

---

# 7. Basis Partition Controller

推奨phase:

```text
MAX-SHARE INIT
↓
WARMUP
↓
OBSERVE
↓
DIAGNOSE
↓
PERSISTENCE / DIRECTIONALITY GATE
↓
SHADOW TRIAL
↓
COMMIT / REVERT
↓
SPECIALIZE
↓
(optional) MERGE
```

## 7.1 Hard Bucket

形状・接続点・roleなどの物理制約で共有可能bucketを作る。

bucket内では最大共有から開始する。

## 7.2 Warmup

初期gradient noiseやC66型co-adaptation false positiveを避けるため、一定stepは構造変更しない。

## 7.3 Observation Window

```text
virtual-dense residual
shared/effective gradient cosine
factor/common update norm ratio
per-module functional contribution
group rank utilization
per-seed directionality
runtime reuse potential
```

## 7.4 Candidate Detection

```text
Residual high + Conflict low
-> rank-grow candidate

Residual high + persistent directional Conflict
-> shadow-split candidate

Conflict high + co-adaptation unstable
-> optimizer diagnostic first

Functional delta mixed-sign across seeds + center near zero
-> KEEP
```

## 7.5 Shadow Trial

同一checkpointから短期間:

```text
A. KEEP
B. GROW_RANK
C. SPLIT
D. optimizer/co-adaptation adjustment
```

比較:

```text
quality
NLL
negative transfer
parameter bytes
resident bytes
runtime
training/inference FLOPs
structure complexity
```

## 7.6 Commit / Revert

Split採用最低条件:

```text
persistent directional quality benefit
AND
non-target regression acceptable
AND
rank-grow / optimizer / checkpoint / seed varianceでは説明できない
AND
cost increase acceptable
```

---

# 8. Function-Preserving Split

親Basisを子へcloneする。

```text
B_G1 = clone(B_G0)
B_G2 = clone(B_G0)
```

`A_module`は維持。

Optimizer stateも第一候補としてcloneする。

Split直後のforwardだけでなく、次step以降の学習軌道保存も検証対象。

---

# 9. Adaptive Rank

Auto-PartitionとAdaptive Rankは連携する。

ただし一律rank ruleは使わない。

現在の証拠:

```text
Composition: rank2でrobust
Language:    rank2 capacityはあるがrank4が固定scheduleに安定
Condition:   rank4が選択点。12-seed exhaustiveでDenseとの差はゼロ中心に近い
```

C69後、Condition rankを追加で増やすことは優先しない。

---

# 10. Private Residual

将来候補:

```text
Delta W_m = A_m @ B_group + P_m
```

v0.1では入れない。

Auto-Partition / Rank / Private Residualを同時導入すると原因切り分けが困難になるため。

---

# 11. 生のA/B重みクラスタリングを主判定にしない

低ランク分解には座標自由度がある。

```text
A B = (A Q)(Q^-1 B)
```

優先するもの:

```text
effective update space
virtual-dense gradient residual
gradient interaction
functional behavior
```

---

# 12. Seed / Persistence / Directionality Gate

C67-C69により必須。

単一seed・単一validation sliceで構造変更しない。

v0.1原則:

```text
異常が複数windowで継続
AND
複数seed / 独立validation sliceで再現
AND
改善/悪化の方向が十分一貫
AND
functional差が構造変更に値する
```

### C69による具体化

次のケースは構造変更しない。

```text
12 seedで6勝6敗
mean / medianがほぼ0
sign-testが方向性を示さない
```

これは`KEEP / observe`。

まだ固定しないもの:

```text
必要seed数
方向一致率threshold
functional equivalence margin
minimum gain
```

C69自体はformal equivalence marginを定義していないため、ここで数値thresholdを捏造しない。

---

# 13. 初版でDynamic Routerを使わない

module grouping自動化と推論時dynamic routingは別問題。

v0.1では最終的に静的mapへ固定する。

```text
module_0 -> basis_group_0
module_1 -> basis_group_0
module_2 -> basis_group_2
```

理由:

- inference graph単純化
- batching/cache容易化
- FLOPs予測可能
- deterministic evaluation
- Shared Basis効果とRouter効果を分離

---

# 14. Auto-Partition v0.1 scope

## 入れる

```text
Hard bucket
Max-share initialization
Warmup
Virtual-dense residual observer
Gradient conflict observer
Co-adaptation observer
Seed/directionality observer
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

# 15. Split採用Gate

## Quality Gate

Split後に対象module群のvalidation性能が改善。

## Non-target Regression Gate

非対象moduleを許容範囲以上に悪化させない。

## Alternative Explanation Gate

次で同等以上に解決できないこと。

```text
optimizer / LR adjustment
rank grow
checkpoint policy
seed / validation variance
```

## Stability / Directionality Gate

複数window / seed / validation sliceで同じ方向が再現。

## Cost Gate

serialized bytes / resident bytes / FLOPs / memory増加に対する利益が妥当。

## Determinism Gate

同checkpoint・seed・data orderなら同じ候補判定を再現。

---

# 16. 評価Baseline

最低限:

```text
A. Independent Basis per module
B. One Shared Basis per hard bucket
C. Fixed manual grouping
D. Auto-partition Shared Basis
E. Shared Basis + adaptive rank only
F. Auto-partition + adaptive rank
```

Pareto評価:

```text
task score / NLL / calibration
parameter count
serialized / resident bytes
peak train/inference memory
train/inference FLOPs
negative transfer
failure correlation
group count / rank distribution
structure-search overhead
```

---

# 17. 主な失敗パターン

## Split Explosion

対策: persistence / minimum gain / complexity penalty / merge。

## Rank Growthで全部解決

失敗ではない。Adaptive Rankだけで十分なら単純な設計を選ぶ。

## Early Split Lock-in

対策: warmup / EMA / reversible shadow trial。

## Co-adaptation False Positive

C66型。対策: update norm / LR ratio診断をSplitより先に行う。

## Seed False Positive

C67-C69型。

対策:

```text
larger validation
exhaustive evaluation when possible
multi-seed
win/loss directionality
```

## Group Oscillation

対策: hysteresis / cooldown / split-merge threshold分離。

---

# 18. Auto-Partition専用の実験順序

Gate C shared-basis候補のruntime/recurrence基礎が確定した後に開始する。

## AP1 — Virtual Dense Residual Sensor validation

Basis内方向だけ必要なmoduleとBasis外方向を必要とするmoduleを人工taskで作り、Residualが区別できるか。

## AP2 — Rank不足 vs Split必要性

同checkpointから`GROW_RANK`と`SPLIT`を比較。

## AP3 — Co-adaptation false-positive

C66型LR mismatchでControllerがSplitではなくoptimizer問題を返せるか。

## AP4 — Function-preserving Split

forward / logits / state digest一致とoptimizer state migration。

## AP5 — Shadow Trial predictiveness

短期trial選択が長期結果と一致するか。

## AP6 — Merge

過剰Splitから安全に統合できるか。

## AP7 — Runtime reuse

同品質Grouping候補で実latency / throughput / memory比較。

---

# 19. Implementation Defaults

## 19.1 現在固定してよいもの

```text
Grouping principle: max-share within hard bucket
Inference mapping: static
Primary residual: virtual dense effective-weight gradient
Split mechanism: function-preserving basis clone
Split adoption: shadow trial required
Training default on current tasks: factor_lr = common_lr
Seed policy: multi-seed + directionality required before structural action
Mixed-sign / near-zero-center result: KEEP, not split/rank-grow
Runtime reuse: secondary cost signal
Dynamic router: out of v0.1
Private residual: out of v0.1
```

## 19.2 まだ固定しないもの

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
Required seed count
Directionality threshold
Functional equivalence margin
```

---

# 20. 実装開始時の最小コード構成

## Pass AP-OBSERVE — read-only

候補:

```text
fold_lm/v05/partitioning.py

PartitionObserver
PartitionStatsWindow
ModuleGradientStats
GroupStats
PartitionRecommendation
```

責務:

```text
canonical module/group key
virtual dense gradient residual
gradient cosine
update norm / co-adaptation
seed/directionality summary
JSON artifact
```

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
- observer無効時runtime regressionなし
- artifactがseed再現可能

## Pass AP-DECIDE — recommendation only

```text
KEEP
GROW_RANK
SHADOW_SPLIT
OPTIMIZER_DIAGNOSTIC
```

## Pass AP-SHADOW

checkpoint cloneからkeep / rank-grow / split / optimizer-adjustを比較。

## Pass AP-MUTATE

初めてGroup Split / optimizer state migration / checkpoint serialization / deterministic group IDを実装。

## Pass AP-MERGE

後段。

---

# 21. Open Questions / Next Validation

Gate-C直近:

1. **C70:** GEMM-native shared-basis実行がmaterialized effective-weight実行と、task outputおよび64-step recurrenceで等価か。
2. C70通過後、production-like latency / resident-memoryをselected rank構成で測る。
3. その後、長期recurrence / production integration boundaryを確定する。

Auto-Partition開始前:

1. moduleの厳密単位
2. hard bucket条件
3. Up/Downを同じgroup decisionにするか
4. virtual dense gradient取得コスト
5. residual正規化
6. shared-gradient vs effective-gradient conflictの主指標
7. observation window / warmup
8. residual/conflict thresholds
9. rank grow step
10. shadow trial長
11. functional score aggregation
12. optimizer state split/merge
13. deterministic group ID / checkpoint schema
14. merge criterion
15. runtime reuse estimator
16. structure-search overhead budget
17. distributed training時の統計集約
18. formal functional equivalence margin
19. seed count / directionality threshold

---

# 22. C70との関係

C70はAuto-Partitionそのものを試さない。

目的は、Auto-Partitionが将来操作するShared Basis表現について、

```text
materialized reference execution
vs
GEMM-native runtime execution
```

がrecurrenceを含めて同じ意味を保てるか確認すること。

ここが崩れる場合、runtime arithmetic差をgrouping signalと誤認する危険があるため、AP-OBSERVEより先に解決する。

---

# 23. 直感的な説明

Shared Basisを会社の共通部署と考える。

問題が起きてもすぐ部署を分けない。

```text
机が足りない？            -> Rank不足
仕事の速度が合わない？    -> Co-adaptation
本当に方向が対立する？    -> Shared incompatibility
特定seedだけ？             -> Seed variance
12人中6人ずつ勝敗が逆？   -> Directionなし、KEEP
```

それでも継続的・一方向に干渉が再現する場合だけShadow Splitする。

---

# 24. 現時点のv0.1本命

```text
Max Share
+ Adaptive Rank
+ Virtual Dense Residual
+ Gradient Conflict
+ Co-adaptation Check
+ Multi-seed Directionality Gate
+ Functional Gate
+ Shadow Trial
+ Static Final Grouping
```

Auto-Partitionの仕事は、単に似たmoduleを集めることではない。

> **容量不足・学習不均衡・seed分散・runtime数値差・本当の共有不適合を切り分け、必要なときだけ安全に構造を分けること。**
