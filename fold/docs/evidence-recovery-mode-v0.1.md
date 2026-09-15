# Evidence Recovery Mode v0.1 — 不明なまま安全に情報を回収する

更新日: 2026-09-15。
関連: `information-acquisition.md`, `development-roadmap-v0.5.md`, `architecture-v0.5.md`。

**状態: V5-E の設計決定。まだ production runtime API / 学習済み能力 / Gate E 合格を意味しない。**

## 1. 目的

FOLD が必要情報を欠いているとき、`ASK_USER` が利用不能、望ましくない、または応答待ちできない場合でも、即座に推測で埋めたり `STOP_UNRESOLVED` へ落ちたりせず、**安全な範囲で自律的に情報を回収するモード**を持つ。

このモードの一時的な目的は、元の task goal を直接進めることではなく、元の goal を妨げている `unresolved_dependency` を減らすことである。

```text
original goal
  ↓
missing / conflicting / ambiguous evidence
  ↓
normal acquisition cannot resolve immediately
  ↓
EVIDENCE_RECOVERY mode
  ↓
read / retrieve / observe / safe probe
  ↓
validated evidence
  ↓
resume original goal
```

「不明でも進む」は「分からないことを勝手に決めて進む」ことではない。**不明を減らすための行動だけを進める。**

## 2. モード名と位置付け

v0.1 名称:

```text
EVIDENCE_RECOVERY
```

これは `ANSWER / RETRIEVE / OBSERVE / ASK_USER` と同列の回答 action ではなく、runtime / controller が一定期間使う **acquisition sub-mode** とする。

元の goal / scope / revision は保持し、暫定 goal だけを次へ切り替える。

```text
mode_goal = reduce(unresolved_dependency)
```

モード中に得た情報は通常の evidence/provenance 境界を通し、内部仮説を観測事実へ昇格させない。

## 3. Entry 条件

次をすべて満たす場合に候補化する。

1. 結論または次の重要 action に影響する unresolved dependency がある。
2. 現在の evidence だけでは十分に解けない。
3. `ASK_USER` が unavailable / disallowed / too costly / latency policy 上不適切、または先に自力取得する方が合理的。
4. 実行基盤が少なくとも一つの evidence-producing action を許可している。
5. acquisition budget が残っている。
6. 許可された行動で期待される情報価値がゼロではない。

`ASK_USER` が使える場合でも、毎回質問を優先しない。自分で低コストに取得できる情報は、runtime permission と budget の範囲で先に取得してよい。

## 4. モード中の action class

### 4.1 Passive acquisition

既存の情報を読むだけのもの。

```text
READ_MEMORY
RETRIEVE
OBSERVE
INSPECT
MEASURE
```

例:

- 保存済み記憶を読む
- 文書や index を検索する
- カメラやセンサーを別角度・別解像度で見る
- UI、inventory、状態表示を読む
- 現在値を計測する

### 4.2 Active probe

見るだけでは情報が増えない場合、**低リスクで可逆な環境操作を、情報取得目的に限って許可する**。

v0.1 の概念 action:

```text
PROBE(action)
```

`PROBE` は task-completion action ではなく、action の結果を新しい evidence として観測するための操作である。

例:

- 観測可能な位置まで移動する
- 別角度へ回り込む
- UI / menu / container を開いて読む
- reversible な toggle を一時的に切り替えて状態変化を見る
- 低コストの test input を与えて出力を見る
- 安全な範囲で対象へ近づき追加センサー観測を取る

## 5. Side-effect class

PROBE 候補は runtime 側で最低限次に分類する。

```text
PURE_READ
REVERSIBLE_LOCAL
REVERSIBLE_WITH_ROLLBACK
IRREVERSIBLE_OR_HIGH_RISK
```

v0.1 の自動実行候補は原則として上3つまで。

`IRREVERSIBLE_OR_HIGH_RISK` は EVIDENCE_RECOVERY を理由に自動許可しない。

例:

- delete / destroy
- 唯一資源の消費
- 課金 / 購入 / 送金
- 外部送信 / 公開
- 権限変更
- セキュリティ境界の変更
- 復元不能な world state 変更

これらは通常の approval / policy / explicit authority の対象とする。

## 6. Runtime permission が最終 authority

モデルは候補を提案できるが、自分で安全性・権限を確定しない。

```text
model proposal
  ↓
runtime capability / permission / risk check
  ↓
allowed action mask
  ↓
execution
```

`ASK_USER` が unavailable であることは、禁止された `ACT` を自動的に許可する理由にならない。

また、`PROBE` に包めば任意 action が安全になるわけではない。実体の side effect で判定する。

## 7. State

EVIDENCE_RECOVERY 中は少なくとも概念上次を保持する。

```text
original_goal
original_scope
original_revision
unresolved_dependency
known_evidence_refs
candidate_explanations
acquisition_options
allowed_action_mask
probe_side_effect_class
expected_information_effect
acquisition_budget
observations_collected
no_progress_counter
recovery_status
```

`recovery_status` 候補:

```text
ACTIVE
RESOLVED
PARTIALLY_RESOLVED
BUDGET_EXHAUSTED
NO_SAFE_ACTION
NO_INFORMATION_GAIN
PERMISSION_REVOKED
FAILED_ACQUISITION
```

## 8. Budget

探索を無限化しない。用途に応じて複数の上限を持てる。

```text
max_recovery_steps
max_observations
max_probe_actions
max_wall_clock
max_distance / movement_cost
max_resource_cost
max_tool_calls
max_repeated_equivalent_observation
```

同じ観測を繰り返して evidence が増えない場合は `no_progress_counter` を進める。

budget 切れは「答えが存在しない」証明ではない。

## 9. Evidence semantics

EVIDENCE_RECOVERY 中も次を分離する。

```text
OBSERVED_FACT
RETRIEVED_EVIDENCE
USER_ASSERTION
DERIVED_RESULT
HYPOTHESIS
UNKNOWN
```

特に、probe 前の予想と probe 後の観測を混同しない。

例:

```text
HYPOTHESIS: door may be locked
PROBE: try safe open interaction
OBSERVED: open action rejected with LOCKED state
FACT candidate: current door state reports locked
```

`door may be locked` 自体を観測前に事実 commit しない。

probe が失敗した場合も、失敗の種類を evidence として扱えるが、取得不能を対象不存在へ変換しない。

## 10. Exit 条件

次のいずれかで EVIDENCE_RECOVERY を終了する。

### Resume original goal

unresolved dependency が十分に解消され、元の action / answer を再評価できる。

```text
EVIDENCE_RECOVERY
  → evidence sufficient
  → exit mode
  → re-evaluate original goal
```

### Partial resume

一部だけ解けた場合、解けた範囲だけ進める。残りは unknown として保持する。

### Stop unresolved

次の場合は根拠なく進めない。

- safe action がない
- permission がない
- budget を使い切った
- 同等観測を繰り返しても情報が増えない
- 残る行動が高リスク / 不可逆のみ
- evidence conflict を解消できない

この場合は `STOP_UNRESOLVED` / blocked state へ移る。

## 11. Low-risk provisional progress との境界

EVIDENCE_RECOVERY は「何でも慎重に試してよい mode」ではない。

元の task を直接進める provisional action を許す場合は、別途次を満たす必要がある。

```text
low consequence
AND reversible
AND bounded cost
AND failure observable
AND runtime permitted
```

その action が情報取得にもなる場合は PROBE として扱える。

ただし、単に成功するかもしれないという理由で task action を PROBE と再ラベルしない。

## 12. Example — 自律エージェント

### 不明だが観測で回収できる

```text
Goal: target object を回収する
Unknown: target が container A / B のどちらにあるか不明
ASK_USER: unavailable

EVIDENCE_RECOVERY:
  inspect A
  → no target
  inspect B
  → target observed

exit EVIDENCE_RECOVERY
resume original goal
collect target
```

### 移動して観測する必要がある

```text
Unknown: route ahead が通行可能か
current camera では見えない

PROBE:
  move to safe observation point
  observe route

if passable:
  resume goal
else:
  replan
```

### 不明なまま止めるべき

```text
Unknown: destructive action が許可されているか
ASK_USER: unavailable
safe evidence source: none
remaining action: irreversible deletion only

EVIDENCE_RECOVERY -> NO_SAFE_ACTION
STOP_UNRESOLVED
```

## 13. Learning / evaluation

将来の V5-E data には次を含める。

- ASK 不可でも RETRIEVE / OBSERVE で自力解決できるケース
- 観測地点へ移動しないと情報が得られないケース
- reversible probe でのみ候補を区別できるケース
- probe が情報を増やさない negative control
- irreversible action しか残らず停止すべきケース
- 一部だけ解消して partial progress できるケース
- tool failure / stale evidence / conflicting evidence
- budget exhaustion

評価軸:

```text
resolution_rate
useful_information_gain
unsafe_probe_rate
irreversible_action_without_authority_rate
unnecessary_ask_rate
unnecessary_stop_rate
no_progress_loop_rate
budget_compliance
fact_hypothesis_confusion_rate
resume_original_goal_success
```

特に、単純な「停止率低下」を成功にしない。停止を減らす代わりに危険行動や架空事実が増えた場合は失敗とする。

## 14. V5-E Gate への追加候補

既存 Gate E に、将来次を追加評価する。

1. `ASK_USER` unavailable 条件でも、安全な取得手段がある場合は一定率で自律解決できる。
2. 情報回収のために必要な reversible probe を利用できる。
3. 高リスク / 不可逆 action を、情報不足の解消目的だけで自動実行しない。
4. probe 前の仮説を観測事実として commit しない。
5. budget / no-progress 条件で探索loopを停止できる。
6. 十分な evidence を得た後、original goal へ復帰できる。
7. 取得不能時は unknown を保持し、もっともらしい値で穴埋めしない。

## 15. C143 との関係

この設計追加は、現在 active な C143 の科学的仕様を変更しない。

C143 は frozen ranking audit であり、EVIDENCE_RECOVERY mode の実装・学習・Gate 判定を含まない。

EVIDENCE_RECOVERY の実装実験は、C143 の正式判定後に V5-E の残課題として別 C 番号で preregister する。現在の C143 の PASS / FAIL / INVALID 基準を後から変更しない。
