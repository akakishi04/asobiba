# PC-ALM × FOLD — Layer-Local Credit Assignment Integration Hypothesis Report

作成日: 2026-09-16  
状態: **研究仮説 / 比較実験提案。実証済み仕様ではなく、現行FOLD設計の置換決定ではない。**

関連文書:

- `fold/docs/architecture-v0.3.md`
- `fold/docs/research-plan.md`
- `fold/docs/local-training.md`
- `fold/docs/shared-basis-auto-module-partition-report.md`
- `fold/docs/shared-basis-runtime-output-impact-report.md`
- `fold/docs/multi-axis-shared-basis-hypothesis-report.md`

外部一次資料:

- Jeffrey Seely, Julian Gould, **Augmented Lagrangian Predictive Coding**, arXiv:2605.31022, 2026
- Sakana AI, **Augmented Lagrangian Predictive Coding: training 1000-layer networks without backpropagation**, 2026-09
- SakanaAI/pc-alm, official JAX reference implementation

---

## 1. 目的

本書は、Sakana AIの **PC-ALM (Augmented Lagrangian Predictive Coding)** をFOLDへそのまま移植する提案ではない。

検討対象はより限定する。

> **PC-ALMが示した「各層が近傍との制約誤差と局所dual stateだけから、global objectiveに対応するcredit signalを形成できる」という原理を、FOLDのShared Basis / module構造 / FOLD-Rを含む将来構成へ利用できるか。**

特に次を検証対象とする。

1. FOLDのdepth方向credit assignmentをglobal Backpropから部分的に分離できるか
2. Shared Basisのmodule別gradient contributionを局所creditから再構成できるか
3. Shared Basis Auto-PartitionのConflict / Residual判定に利用できるか
4. Multi-Axis Shared Basisへ拡張可能か
5. FOLD-Rの厳密なmemory semanticsを壊さず併用できるか
6. next-token language modelingと時系列stateを含む場合でも成立するか
7. GPU実時間・VRAM・同期コストを含めて導入価値があるか

本書では、**理論的に面白いこと**と**FOLDへ採用すべきこと**を分離する。

---

## 2. 先に結論

現時点の第一候補は、PC-ALMによるFOLD全体のBackprop置換ではない。

推奨する研究順序は次である。

```text
現行FOLD
  |
  |  global BP / autograd baselineを保持
  |
  +--> PC-ALM reference reproduction
          |
          v
      FOLD-shaped blocksでdepth-local credit
          |
          v
      next-token CEで成立確認
          |
          v
      Shared Basisの局所gradient contribution再構成
          |
          v
      Auto-Partitionをshadow判定
          |
          v
      FOLD-Rを含むhybrid構成
          |
          v
      temporal creditは最後に独立研究
```

第一候補の仮称を、

> **FOLD Hybrid Local Credit (FHLC)**

とする。

FHLCでは、**module内部の微分可能計算には通常のautogradを使ってよい**。ただしmodule間のdepth方向に長いglobal backward graphをそのまま通す代わりに、module境界のactivationをliftし、PC-ALM型のprimal-dual dynamicsから局所creditを得る。

これは「勾配を使わない方式」ではない。

より正確には、

> **global Backpropでcreditを運ぶ代わりに、局所dynamicsでcreditを作り、各module内部のparameter derivativeは通常の局所autogradで計算する方式**

である。

現段階でこれ以上を正規設計へ入れる根拠はない。

---

## 3. PC-ALMについて一次資料から確定していること

### 3.1 PC-ALMの中心

通常のfeed-forward networkを、hidden activationも最適化変数とする制約付き問題として扱う。

概念的には、

```text
h_i = f_i(h_{i-1}; theta_i)
```

という各layerの関係を制約とし、residualを、

```text
r_i = h_i - f_i(h_{i-1}; theta_i)
```

とする。

PC-ALMは、

```text
L_task
+ sum_i lambda_i^T r_i
+ (rho / 2) * sum_i ||r_i||^2
```

というAugmented Lagrangian型objective上で、activation `h_i` のprimal descentと、dual variable `lambda_i` のdual ascentを行う。

概念的なdual updateは、

```text
lambda_i <- lambda_i + alpha * r_i
```

である。

各layerは近傍のactivation / residualとの通信だけで更新できる。

### 3.2 linear networkでの強い結果

論文では、linear networkの平衡点でdual variableがBackpropのcredit signalへ一致することを示す。

したがってlinear caseでは、global backward passを実行せず、layer-local dynamicsだけで正確なBP gradientに対応するcreditを分散して得られる。

### 3.3 nonlinear networkでは経験的結果

nonlinear caseで「常にexact BPになる」という理論結果ではない。

論文は最大128層のnonlinear networkでBPに近い性能を報告し、1000-layer residual MLPのMNIST実験でもPCより大幅に安定したcredit propagationを示している。

### 3.4 1000層結果の範囲

「1000層をBackpropなしで学習」は重要だが、FOLDへ直接一般化してはいけない。

1000-layer実験は、

- MNIST
- residual MLP
- deep / narrow regime
- 単純なclassification setup

である。

LLM、autoregressive language modeling、FOLD-R、長期stateful recurrenceを1000層で検証した結果ではない。

### 3.5 inference budget

公式referenceは代表実験で、

```text
T = 2L
```

を使用する。

32層なら64 inference stepである。

PC-ALMはglobal backward passを消す一方、weight update前に反復dynamicsを実行する。

したがって、

> Backpropを使わない = GPUで速い

とはならない。

### 3.6 公式referenceの学習objective

公式JAX reference implementationのsupervised training lossはMSEである。

Cross Entropyはevaluation metricとして記録されているが、referenceのweight gradient生成objectiveはMSEである。

したがって、**next-token Cross Entropyを中心とするlanguage modelでの有効性は別途検証が必要**である。

### 3.7 temporal creditは未解決領域

Sakana AI自身がfuture workとして、

- temporal tasks / temporal credit assignment
- self-supervised losses
- larger networks / harder tasks

を挙げている。

これはFOLDにとって重要である。

FOLDは単なる深いfeed-forward MLPではなく、将来的にFOLD-R state、chunk、memory update、長期系列を含むため、PC-ALMの成功をそのまま時系列方向へ拡張してはいけない。

---

## 4. FOLD側の前提

本仮説は、現在FOLDで検討している次の構造を前提にする。

### 4.1 Shared Basis

概念的に、module `m` の更新を、

```text
Delta W_m = A_m @ B_g
```

とする。

`A_m` はmodule固有、`B_g` はBasis Groupで共有する。

目的は、moduleごとに巨大な独立parameterを持つ代わりに、共通の低次元更新空間を再利用することである。

### 4.2 Auto-Partition

現行仮説では、最大共有から開始し、

- Subspace Residual
- Gradient Conflict
- Functional Interference
- Runtime Reuse

を観測し、必要な場合だけ、

```text
Rank Increase
Split
Private Residual
Merge
```

を行う。

### 4.3 Multi-Axis Shared Basis

将来候補として、Task / Stage / Role等を独立軸として因子化し、組合せ数の増加とparameter countを直接比例させない構造を検討している。

### 4.4 FOLD-R

FOLD-Rは、response capsuleとCapability Contractを持つ長期memory経路である。

数値kernelの正確性と、SUPPORTED / OUT_OF_SCOPE等の意味論を、学習上の都合で曖昧にしない。

PC-ALM導入によってFOLD-Rのauthoritative semanticsを変更してはならない。

---

## 5. 中心仮説 H1 — FOLDのdepth方向creditを局所化できる

FOLD moduleを、

```text
h_m = f_m(h_{m-1}, s_m; theta_m)
```

とする。

ここで、

- `h_m`: module出力activation
- `s_m`: module内部stateまたは明示的補助入力
- `theta_m`: module parameter

である。

module境界ごとにlifted activation `h_m` を持ち、

```text
r_m = h_m - f_m(h_{m-1}, s_m; theta_m)
```

を定義する。

FOLD向け最小Augmented Lagrangian候補は、

```text
L_FHLC
  = L_task(h_M)
  + sum_m <lambda_m, r_m>
  + (rho / 2) * sum_m ||r_m||^2
```

とする。

局所inferenceは、

```text
h_m      <- h_m - eta_h * dL_FHLC / dh_m
lambda_m <- lambda_m + alpha * r_m
```

を一定budgetだけ反復する。

その後、`h` と `lambda` をglobal graphからdetachした状態で、各moduleの局所parameter updateを求める。

### 仮説

> FOLDのmodule境界が十分滑らかな微分可能写像であれば、PC-ALM型dual stateはdepth方向にglobal lossのcreditを運び、global BP gradientと高いalignmentを持つ局所parameter updateを生成できる。

### 重要な限定

これは、

> FOLD全体のBackpropを今すぐ削除できる

という仮説ではない。

最初に検証するのは、

```text
BP gradient
vs
FHLC local gradient
```

の一致度だけである。

---

## 6. 中心仮説 H2 — Shared Basisのgradientを局所寄与から再構成できる

Shared Basisを、

```text
Delta W_m = A_m @ B_g
```

とする。

module `m` がPC-ALM local objectiveから得るeffective weight gradientを、

```text
G_m = dL_local_m / d(Delta W_m)
```

とする。

すると、chain ruleから、

```text
dL / dA_m = G_m @ B_g^T
```

である。

shared parameter `B_g` への寄与は、

```text
dL_m / dB_g = A_m^T @ G_m
```

となる。

同じBasis Group `g` の全moduleを集約すると、

```text
dL / dB_g
  = sum_{m in g} A_m^T @ G_m
```

となる。

### 仮説

> PC-ALMがmodule-localに十分良い `G_m` を与えられるなら、Shared Basisのglobal backward graphを通さなくても、各moduleから送られる小さいgradient contributionをGroup単位でreduceすることで、BPに近い `dL/dB_g` を再構成できる。

これはFOLDとの接点としてかなり重要である。

### ただし完全局所ではない

Shared Basisは複数moduleが同一parameterを持つため、

```text
sum_{m in g}
```

という集約が必要である。

したがってPC-ALMを使っても、

> Shared Basisを含むFOLD全体が完全に独立・非同期な局所学習器になる

とは言えない。

正確には、

```text
credit generation       = module-local化できる可能性
shared parameter update = Basis Group内reduceが必要
```

である。

このreduceはBackprop graphとは異なるが、optimizer step時の同期境界として残る。

---

## 7. 中心仮説 H3 — Auto-PartitionのGradient ConflictをPC-ALMで近似できる

現在のAuto-Partition案では、同じBasis Groupを共有するmodule `m` のgradient contribution、

```text
g_m = dL_m / dB_g
```

を使い、

```text
cos(g_i, g_j)
```

からGradient Conflictを評価する。

FHLCでは、これを、

```text
hat_g_m = A_m^T @ G_m_PC-ALM
```

で近似できる可能性がある。

### 仮説

> PC-ALM local creditがBP gradientそのものと完全一致しなくても、module間の「同方向 / 無関係 / 競合」という相対構造を保存できれば、Auto-Partition controllerには十分使える。

これは単なるgradient cosineより実用的な評価になる。

比較すべきものは、

```text
BP conflict matrix
vs
PC-ALM conflict matrix
```

である。

具体的には、

- pairwise cosine correlation
- conflict sign agreement
- cluster assignment agreement
- Rank Increase / Split候補の一致率
- 実際にSplitした後のvalidation改善予測

を測る。

### 重要な禁止事項

`lambda_m` のnormが大きいことだけをSplit理由にしてはいけない。

大きなdual normは、

- 本当に難しいmodule
- 深さによるcredit集中
- activity step size不適合
- finite-Tで未収束
- scale差
- 一時的training transient

でも生じ得る。

したがってdual statisticsは、Auto-Partitionの**補助診断信号**として扱う。

現行の、

```text
Subspace Residual
Gradient Conflict
Functional Interference
```

を置き換えない。

---

## 8. 中心仮説 H4 — Dual stateは「構造的負荷」の診断に使える可能性がある

PC-ALMは各module境界に `lambda_m` と residual `r_m` を持つ。

これにより、通常のBackpropでは直接見えにくい、

> どの境界がglobal objectiveを満たすために強く修正要求され続けているか

を時間発展として観測できる可能性がある。

候補統計として、

```text
normalized_dual_m
  = EMA(||lambda_m|| / sqrt(dim_m))

residual_decay_m
  = ||r_m(T)|| / (||r_m(1)|| + eps)

constraint_debt_m
  = EMA(||r_m(T)||)
```

等を考えられる。

### 仮説

> Persistentなdual/residual異常は、Shared Basisのrank不足、module境界の表現不足、step-size不安定性、あるいは本質的な共有不適合の候補検出に使える。

ただし、**原因判定には使わない**。

原因判定は既存Controllerと同様、

```text
Rank Increase
vs
Split
vs
optimizer / step-size修正
```

をshadow ablationして決める。

---

## 9. 中心仮説 H5 — Multi-Axis Shared Basisとも数理的には両立する

Multi-Axis案を、

```text
Delta W(t,s,r)
  = sum_k gamma_k(t,s,r) * A_k @ B_g
```

とする。

module-localにeffective update gradient `G` が得られれば、各componentやaxis coefficientに対するgradientはchain ruleで局所的に計算できる。

例えば、

```text
dL / dgamma_k
  = <G, A_k @ B_g>
```

である。

したがって、

> PC-ALM local credit
> -> effective update gradient
> -> component / axis coefficient gradient

という経路は構成可能である。

### 仮説

> Multi-Axis因子化に必要なgradient directionの相対構造がPC-ALMでも保たれるなら、Task / Stage / Roleのfactorizationを維持したままdepth-local creditへ移行できる。

ただし、Shared Basisと同様に、共有component `A_k / B_g` へのupdateは複数座標からのreduceを必要とする。

よってこれも完全非同期化ではない。

### 実験順序

Multi-Axisとの同時導入はしない。

順序は、

```text
PC-ALM単体
 -> Shared Basis
 -> Auto-Partition
 -> Multi-Axis
```

とする。

複数の新機構を同時投入すると、成功・失敗原因を切り分けられない。

---

## 10. 中心仮説 H6 — FOLD-Rの内部数学は変更せず、境界だけPC-ALM化する

FOLD-Rは、

- response capsule
- exact / bounded numerical semantics
- Capability Contract
- correction / query semantics

を持つ。

PC-ALMのために、FOLD-Rの数値kernelをprediction error networkへ作り替えるべきではない。

第一候補は、FOLD-Rを、

> **内部はそのままの微分可能operator**

として扱うことである。

```text
Module m
  |
  +-- local mixer
  +-- Writer
  +-- FOLD-R kernel
  +-- Reader
  |
  v
h_m
```

PC-ALMでliftするのは、原則としてmodule境界の `h_m` である。

FOLD-R内部のauthoritative state transitionは、その既存contractに従う。

### 仮説

> FOLD-Rを内部からPC-ALM化しなくても、その前後のmodule境界creditを局所化するだけで、Writer / Reader / Fusionの学習creditを十分近似できる。

これが成立しなければ、次にどの内部境界をliftすべきかを検討する。

最初から、

```text
Q/U
J/eta
capsule update
Capability status
```

までdual state化してはならない。

---

## 11. 中心仮説 H7 — temporal creditはdepth creditと分離すべきである

FOLDの小型LM実装では、training block内のchunk間でgradientを切らない構成が存在する。

つまり、depthだけでなくstate / sequence方向のcreditも考慮する必要がある。

PC-ALM論文は、temporal credit assignmentをfuture workとしている。

したがって最初のFHLCは、

```text
Depth boundary:
  PC-ALM local credit候補

Module内部 / short temporal state:
  通常autogradを維持
```

とする。

### 第一段階の具体像

```text
sequence / chunk
      |
      v
+--------------------+
| Module 0           |
| internal autograd  |
+--------------------+
      || lifted boundary h0
      \/
+--------------------+
| Module 1           |
| internal autograd  |
+--------------------+
      || lifted boundary h1
      \/
+--------------------+
| Module 2           |
| internal autograd  |
+--------------------+
```

PC-ALMはmodule間のcredit distributionだけを担当する。

### 仮説

> temporal recurrenceを同時に局所化しなくても、depth側だけをPC-ALM化することで、global backward graph長・activation dependencyを部分的に減らせる可能性がある。

この仮説が成立してから、temporal edgeへ拡張する。

---

## 12. 中心仮説 H8 — deep-narrow化とShared Basisの組合せで価値が増える可能性がある

PC-ALMの強みは特にdeep / narrow networkで顕著である。

これはFOLDにとって興味深い。

FOLDは、Shared Basisによって、

> parameter countを大きく増やさずmodule / stage / depthを増やす

方向を検討している。

もしShared Basisが成功し、

```text
独立parameterを大量に増やさず
処理stageを深くする
```

ことが可能になれば、FOLDはPC-ALMが得意とするdeep-narrow regimeへ近づく可能性がある。

### 仮説

> Shared Basisがparameter scalingを抑え、PC-ALMがdeep credit decayを抑えるなら、「狭い共有表現 + 多段処理」という組合せが、parameter効率と深さの両方を利用できる可能性がある。

ただし、これは二つの未実証仮説の積である。

Shared Basis単体とPC-ALM単体を通過するまで、この相乗効果をFOLDの中心主張にしてはいけない。

---

## 13. 中心仮説 H9 — next-token Cross Entropyでも成立するかは未検証である

公式referenceはMSE supervised lossを使う。

FOLDのLMでは、主objectiveはnext-token NLL / Cross Entropyである。

Augmented Lagrangianの枠組み自体は一般のtask lossと組み合わせられるが、

> 理論上書ける

ことと、

> finite-TのPC-ALM dynamicsで安定して高品質なlanguage modelを学習できる

ことは別である。

### 仮説

> output側だけをCross Entropyに変更しても、hidden constraint dynamicsが安定し、BP gradientとの高いalignmentを維持できる範囲が存在する。

これを独立Gateにする。

CEで失敗した場合、MNIST再現が成功していてもFOLDへ採用しない。

---

## 14. 中心仮説 H10 — GPU高速化は初期成功条件にしない

PC-ALMは、weight updateの前に複数回のstate inferenceを行う。

一般的GPUでは、

- repeated kernel launch
- recurrent synchronization
- activation / dual state traffic
- finite-T iteration

が増える可能性がある。

一方で、global backward graphを持たないことは、

- pipeline / model parallel
- local accelerator
- neuromorphic hardware
- distributed module execution

では別の価値を持つ可能性がある。

### 仮説

> 初期の単一GPU FOLDではPC-ALMがwall-clockでBPより遅い可能性が高いが、credit locality、activation lifetime、communication topologyの違いが将来のhardware / distributed executionで利点になる可能性がある。

したがって初期評価は、

```text
accuracyだけ
```

でも、

```text
speedだけ
```

でも判定しない。

必ずParetoで比較する。

---

## 15. FHLCで想定する最小計算モデル

第一候補の概念処理を示す。

```text
1. Normal forward initialization

   h_0 -> h_1 -> ... -> h_M

2. Lift hidden module-boundary activations

   h_1 ... h_{M-1} をoptimization stateとして扱う

3. Initialize duals

   lambda_m = 0

4. Local primal-dual inferenceをT回

   each module communicates only adjacent boundary state

5. Freeze / detach settled h and lambda

6. Compute module-local parameter gradient

7. Shared Basisの場合

   module-local contributionをBasis Group単位でreduce

8. Optimizer step
```

重要なのは、step 6でmodule内部の微分を禁止しないことである。

例えばlocal attention、FFN、Writer、Reader内部のJacobian計算はautogradでよい。

禁止する候補は、

> **全moduleを貫通する一つのglobal backward dependency**

である。

---

## 16. Shared Basisを含む場合のlocality境界

FHLC採用時のlocalityを明確に分類する。

| 処理 | localか | 備考 |
|---|---|---|
| activation primal update | 近傍local | adjacent module boundary |
| dual update | local | `lambda_m <- lambda_m + alpha r_m` |
| module固有 `A_m` gradient | local | module内autograd可 |
| shared `B_g` contribution | local生成 | 各moduleで生成 |
| shared `B_g` final gradient | Group reduce必要 | 完全localではない |
| optimizer state for `B_g` | Group authority | 同期境界 |
| Auto-Partition statistics | 集約必要 | training graphとは独立に可能 |

したがって、FOLDで目指す場合の正確な表現は、

> **layer/module-local credit generation + group-local parameter reduction**

である。

---

## 17. PC-ALMをそのまま採用しない理由

### 17.1 LLM実証がない

1000-layer headlineはMNIST residual MLPであり、language modeling結果ではない。

### 17.2 official referenceはMSE

next-token CEでのfinite-T stabilityは未検証。

### 17.3 temporal creditが未解決

FOLD-Rやchunk stateへ直接一般化できない。

### 17.4 `T = O(L)` の反復費用

非常に深いFOLDで、`T=2L`をそのまま使うと計算量が大きい。

### 17.5 step-size sensitivity

PC-ALMには、

- primal activity step
- dual step `alpha`
- penalty `rho`
- inference budget `T`

がある。

公式referenceでもactivity stepはnetwork条件に合わせて設定される。

FOLDで安定領域を自動的に得られる保証はない。

### 17.6 oscillatory dynamics

PC-ALMのdual feedbackはdamped oscillationを生む。

適切な範囲ではcredit propagationへ寄与するが、強すぎるdual stepは不安定化し得る。

### 17.7 Shared parameterは局所性を弱める

Shared BasisにはGroup reduceが残る。

---

## 18. 提案する実験Gate

PC-ALM関連は既存Gate C等と混ぜず、仮に `PA` 系列として独立管理する。

```text
PA-0 Reference Reproduction
PA-1 FOLD-shaped Depth Credit
PA-2 Next-token CE
PA-3 Shared Basis Credit Reconstruction
PA-4 Auto-Partition Shadow Controller
PA-5 FOLD-R Hybrid
PA-6 Temporal Local Credit Research
```

---

## 19. PA-0 — Reference Reproduction

### 目的

まずFOLD独自要素を一切入れず、公式PC-ALMの特徴を再現できるか確認する。

### 最小比較

```text
Dataset: Fashion-MNIST
Architecture: residual MLP
Width: 32
Depth: 32
Activation: ReLU
Methods: BP / PC / PC-ALM
Budget: T = 2L
Seeds: >= 3
```

### 公式referenceの代表値

公式READMEのseed 0 referenceでは、

```text
BP      test acc 78.66%, grad cosine 1.000
PC      test acc 68.13%, grad cosine 0.604
PC-ALM  test acc 77.75%, grad cosine 0.909
```

を示している。

### Gate条件

絶対値完全一致ではなく、最低限、

```text
PC-ALM accuracy > PC accuracy
PC-ALM grad cosine > PC grad cosine
PC-ALMがBPへ明確に近づく
```

ことを複数seedで確認する。

これを再現できない状態でFOLDへ移植しない。

---

## 20. PA-1 — FOLD-shaped Depth Credit

### 目的

FOLDに近いmodule形状で、depth-local credit自体が成立するか確認する。

### 構成

まだFOLD-RもShared Basisも入れない。

```text
Input
 -> Local/FOLD-like Block
 -> Block
 -> Block
 -> ...
 -> Head
```

各Blockは、将来FOLDで使う予定の、

- normalization
- residual
- mixer
- FFN

程度に留める。

### 比較

```text
BP
PC
PC-ALM/FHLC
```

### sweep

```text
Depth: 4 / 8 / 16 / 32
Width: 32 / 64 / 128
```

### 必須計測

- final quality
- per-module gradient cosine to BP
- total gradient cosine
- residual norm by depth
- dual norm by depth
- credit wavefront speed
- inference steps to threshold
- wall-clock/update
- peak VRAM/RAM
- state bytes

### 失敗判定

浅い4〜8 moduleでもBP gradient alignmentが低い場合、FOLD採用候補から一旦外す。

---

## 21. PA-2 — Next-token Cross Entropy

### 目的

PC-ALMがFOLDの実際のLM objectiveへ移れるか確認する。

### 構成

まずFOLD-Rを外し、

```text
byte/token embedding
fixed-window local mixer
residual blocks
LM head
next-token CE
```

だけにする。

### 比較

同一、

- tokenizer
- dataset
- parameter budget
- batch
- sequence length
- optimizer

で、BPとFHLCを比較する。

### 必須計測

- train NLL
- val NLL
- token accuracy補助値
- gradient cosine
- per-layer credit norm
- convergence per token
- convergence per wall-clock
- peak VRAM
- total state bytes

### Gate条件

PC-ALM reference再現が成功していても、next-token CEで継続的に崩れるなら、FOLDの標準学習方式にはしない。

---

## 22. PA-3 — Shared Basis Credit Reconstruction

### 目的

FOLD固有の最重要接点を検証する。

### 構成

固定されたBasis Groupで、

```text
Delta W_m = A_m @ B_g
```

を導入する。

Auto Splitはまだ無効。

### 比較するgradient

各moduleで、

```text
BP:
  g_m_BP = dL_m / dB_g

FHLC:
  g_m_PC = A_m^T @ G_m_PC
```

を記録する。

Group aggregateでも、

```text
g_group_BP
vs
g_group_PC
```

を比較する。

### 必須計測

- per-module cosine
- group gradient cosine
- gradient magnitude ratio
- pairwise conflict matrix correlation
- optimizer trajectory distance
- final quality
- Shared Basis rank utilization

### 中心Gate

単にfinal lossが近いだけでは不十分。

**Auto-Partitionが必要とするmodule別gradient構造を保存しているか**を見る。

---

## 23. PA-4 — Auto-Partition Shadow Controller

### 目的

PC-ALM由来signalで、Shared Basis構造探索を安全に駆動できるか確認する。

### Shadow mode

実際の構造変更authorityはBP baseline側に置いたまま、FHLC signalから、

```text
Share
Rank Increase
Split
Private Residual
Merge
```

の候補だけを出す。

### 比較

```text
Decision from BP statistics
vs
Decision from FHLC statistics
```

を比較する。

さらに、両者が提案したSplitをshadow branchで実際に試し、

```text
validation改善
parameter増加
runtime増加
```

を測る。

### 仮説が支持される条件

FHLC gradientがBPと完全一致しなくても、

- conflict sign
- clustering
- beneficial split予測

が安定して一致すれば、Auto-Partition用途には価値がある。

---

## 24. PA-5 — FOLD-R Hybrid

### 目的

FOLD-Rを含む本来のFOLD構成へ接続する。

### 固定するもの

FOLD-R内部の、

- capsule update semantics
- Capability Contract
- numerical safety
- correction semantics

は変更しない。

### PC-ALM化するもの

第一段階では、FOLD-Rを含むmoduleの**外側boundary activationだけ**をliftする。

### 比較

- FOLD-R on + BP
- FOLD-R on + FHLC
- FOLD-R off + BP
- FOLD-R off + FHLC

### 必須評価

既存research-planと同様、

- next-token NLL
- structured query accuracy
- correction-chain accuracy
- OUT_OF_SCOPE calibration
- state / memory bytes
- peak VRAM
- wall-clock

を記録する。

FOLD-Rの意味論を弱めてlossだけ改善する方式は不採用とする。

---

## 25. PA-6 — Temporal Local Credit Research

これは初期採用条件ではない。

PA-0〜PA-5の結果が十分良い場合のみ、

```text
chunk state
recurrent memory edge
long sequence
```

のtemporal creditをlocal dynamicsへ移せるか検討する。

候補としては、

- temporal edgeにもdual variableを置く
- finite temporal windowだけliftする
- chunk boundaryだけdual化する
- depth PC-ALM + truncated temporal BP

等がある。

ただし、これらはPC-ALM論文そのものの結果ではなく、**FOLD独自の新規研究仮説**として扱う。

---

## 26. 評価指標

PC-ALM/FHLCの評価は、精度だけで決めない。

### Quality

- NLL / CE
- accuracy
- structured task score
- correction accuracy
- calibration

### Credit fidelity

- total gradient cosine to BP
- per-module gradient cosine
- Shared Basis contribution cosine
- pairwise conflict matrix correlation
- gradient norm ratio

### Dynamics

- residual decay
- dual norm distribution
- oscillation amplitude
- convergence steps
- wavefront propagation speed
- NaN / divergence count

### Cost

- wall-clock/update
- tokens/s
- total training time
- peak VRAM
- activation bytes
- dual-state bytes
- optimizer-state bytes
- kernel launch count
- synchronization count

### Structure

- Basis rank
- Basis Group count
- Split / Merge count
- private residual bytes
- decision agreement with BP controller

---

## 27. 成功条件はParetoで見る

PC-ALMを、

> BPよりaccuracyが1点高い / 低い

だけで採否しない。

FOLDにとって価値があるのは、例えば次のどれかを実証した場合である。

### Case A — Quality維持 + training locality改善

```text
quality ~= BP
credit locality >> BP
```

### Case B — Shared Basis構造探索が容易になる

```text
Auto-Partition prediction quality改善
+ global backward dependency減少
```

### Case C — memory / communication trade-off改善

```text
wall-clockはやや悪化
peak memoryまたはdistributed communicationが大幅改善
```

### Case D — deep-narrow FOLDでBPより安定

```text
浅い構成: BP有利
深いShared Basis構成: FHLC有利
```

逆に、

```text
quality低下
+ wall-clock悪化
+ memory悪化
+ structure signal改善なし
```

なら不採用でよい。

---

## 28. 予想される失敗モード

### F1 — CEでcredit alignmentが崩れる

MSE classificationでは成功してもLM lossで崩れる可能性。

### F2 — Tが大きすぎる

深さに比例するinference budgetが実用コストを支配する可能性。

### F3 — Shared Basisでdual signalが混線する

共有parameterによる相互依存でmodule-local creditが不安定になる可能性。

### F4 — finite-T bias

平衡点では良くても、実用的な少ないTではgradientがずれる可能性。

### F5 — activity / dual oscillation

`alpha`, `rho`, `eta_h`の組合せで不安定になる可能性。

### F6 — FOLD-R stateとの相互作用

memory stateがmodule boundaryだけでは十分に表現できず、lift対象不足になる可能性。

### F7 — GPUで極端に遅い

局所性があってもiterative dynamicsがGPU実行に不利な可能性。

### F8 — Auto-Partition signalとして役に立たない

gradient cosineは高くても、module間conflict rankingが崩れる可能性。

### F9 — local objective最適化がglobal generalizationを悪化させる

training lossは近くてもheld-out性能が落ちる可能性。

---

## 29. 現時点で採用しない拡張

以下は面白いが、初期実験へ入れない。

- dual leak
- learned `alpha / rho`
- tokenごとのadaptive inference budget
- dual stateのbatch間persistent化
- temporal dual memory
- PC-ALMとMulti-Axisを同時導入
- PC-ALMとAuto-Splitを最初からauthoritativeに接続
- neuromorphic専用kernel
- fully asynchronous Shared Basis optimizer

まずstandard PC-ALMに近い構成で原因分離可能なbaselineを作る。

---

## 30. FOLDにとって最も面白い新しい仮説

PC-ALMの価値を単に、

> Backpropの代替

として見ると狭い。

FOLDでは、より重要な可能性がある。

```text
Shared Basis
  -> parameterを共有して容量を圧縮

PC-ALM dual credit
  -> creditをmodule-localに分散

Auto-Partition
  -> sharingが壊れた場所だけ構造を分裂
```

この三つを組み合わせると、将来的に、

> **parameter共有は最大化するが、creditは局所化し、共有による干渉だけを観測して構造を自動分裂するネットワーク**

という方向が考えられる。

概念図:

```text
                 Shared Basis G0
                      ^
             local gradient reduce
          /           |           \
         /            |            \
      M0 <-> M1 <-> M2 <-> M3 <-> M4
      |      |      |      |      |
     λ0     λ1     λ2     λ3     λ4
      |      |      |      |      |
      +------ local credit --------+

Conflict / Residual observed
            |
            v
   Basis Partition Controller
            |
      +-----+-----+
      |           |
    G0-A         G0-B
```

ここで、

- `lambda` はSplit authorityではない
- SplitはFunctional評価を通す
- Shared Basis reduceは残る
- temporal creditは別問題

という境界を維持する。

この構造が成立すれば、Shared Basisは単なるparameter compressionではなく、

> **局所creditで訓練され、必要な場所だけ専門化する可塑的な共有構造**

へ発展する可能性がある。

これは本書で最も重要なFOLD独自仮説である。

---

## 31. 現時点の推奨判断

### 採用するもの

研究対象として、次を正式に追跡する価値がある。

1. PC-ALM reference reproduction
2. FOLD-shaped blockへのdepth-local credit
3. Shared Basis gradient contribution再構成
4. Auto-Partition用diagnostic signal
5. FOLD-R外側boundaryでのhybrid化

### まだ採用しないもの

1. FOLD標準trainingのBackprop完全撤廃
2. temporal creditのPC-ALM化
3. PC-ALMを理由とした1000-layer FOLD化
4. dual normによる自動Split
5. GPU高速化の主張
6. PC-ALMとMulti-Axisの同時実装

---

## 32. 優先順位

現時点の研究優先度は、

```text
High:
  PA-0 reference reproduction
  PA-1 FOLD-shaped gradient alignment
  PA-3 Shared Basis gradient reconstruction

Medium:
  PA-2 next-token CE
  PA-4 Auto-Partition shadow controller

Later:
  PA-5 FOLD-R hybrid
  PA-6 temporal local credit
```

ただし実行順序は、番号順を維持する。

`PA-3`が研究上特に重要でも、`PA-2`のCE検証を飛ばしてはいけない。

---

## 33. 最終仮説

本書の中心仮説を一文にまとめる。

> **FOLDでは、PC-ALMをBackpropの全面代替として使うより、Shared Basisでparameterを共有するmodule群へlayer-local dual creditを与え、moduleごとの局所gradient contributionをBasis Group単位で集約し、その同じ局所統計をAuto-Partitionの構造診断へ再利用する方が、FOLD固有の設計と高い整合性を持つ可能性がある。**

さらに長期仮説として、

> **Shared parameter / Local credit / Automatic specialization の三者を分離して設計できれば、parameter数を抑えながら深さと専門化を増やす、新しいFOLD training architectureへ発展する可能性がある。**

ただし現時点では、これは研究仮説である。

最初の仕事はPC-ALMをFOLDへ組み込むことではなく、**PA-0〜PA-3で、この仮説が測定可能な形で成立するかを潰すこと**である。

---

## 参考資料

### 外部一次資料

1. Seely, J., Gould, J. (2026). *Augmented Lagrangian Predictive Coding*. arXiv:2605.31022.  
   https://arxiv.org/abs/2605.31022

2. Sakana AI (2026). *Augmented Lagrangian Predictive Coding: training 1000-layer networks without backpropagation*.  
   https://pub.sakana.ai/pc-alm/

3. SakanaAI/pc-alm — official JAX reference implementation.  
   https://github.com/SakanaAI/pc-alm

### FOLD内部資料

- `fold/docs/architecture-v0.3.md`
- `fold/docs/research-plan.md`
- `fold/docs/local-training.md`
- `fold/docs/shared-basis-auto-module-partition-report.md`
- `fold/docs/shared-basis-runtime-output-impact-report.md`
- `fold/docs/multi-axis-shared-basis-hypothesis-report.md`
