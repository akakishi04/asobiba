# FOLD Experiment Conversation / Handoff Protocol

この文書は、FOLD の実験を ChatGPT / Codex / 別チャットへ継続して引き継ぐための **標準会話フォーマット** を定義する。

対象は主に `C###` 実験系列。個別実験の科学的仕様を置き換えるものではなく、`docs/experiment-ledger-and-handoff.md`、各 `experiment-ledger-addendum-*`、Gate decision、実験コードを人間と次のエージェントへ一貫して伝えるための運用規約である。

## 1. 基本原則

- 返答は「前実験の正式判定」から始める。`ACCEPTED PASS`、`ACCEPTED VALID NEGATIVE`、`INVALID EXECUTION / RETRY SAME C NUMBER`、`ACTIVE / NOT YET JUDGED` を曖昧にしない。
- 数値結果と科学的解釈を分ける。PASSでも claim scope を明記し、測っていない一般化を主張しない。
- 次実験は、前実験で残った **1つの主要制約または交絡因子** を外す形で説明する。原則として one scientific question per C number を維持する。
- 「何を変えるか」と同じくらい「何を固定するか」を明示する。比較不能な複数変更を同じC番号へ混ぜない。
- production runtimeを変更したか、diagnostic-onlyかを明記する。
- 長い実験では progress output を事前に示す。ユーザーが実行中に停止・再開・異常判定できるよう seed / phase / case / remaining を出す。
- 実行前後に protected artifact、tracked tree、prerequisite identity 等の guard / postcheck を置く。
- 有効な negative result は失敗扱いで捨てず、正式な科学的結果として ledger に残す。
- 次のC番号へ自動で進まない。原則として **結果をユーザーが貼る → 判定する → ledger/handoffを更新する → 次Cを提示する** の順序にする。
- チャットが変わっても、この文書と `experiment-ledger-and-handoff.md` を読めば同じ応答形式を再開できる状態を保つ。

## 2. 標準返答フォーマット

新しい実験を提示する返答は、原則として次の順序を使う。

### A. 前実験の正式判定

```text
C{N} — {FORMAL STATUS}
```

含めるもの:

- focused regression件数
- fresh seed数とvalidation件数
- deciding metricの主要値
- protected artifact / fixture / tracked tree の状態
- production runtime変更有無
- Gate候補か否か

例:

```text
C136 — ACCEPTED PASS
84/84 regression
3 fresh seeds × 8 held-out queries
query-address / retrieval-key / provenance / commit-once / ANSWER / evidence = 1.0
protected artifacts preserved
```

### B. 科学的に何が成立したか

実験で実際に成立した経路を、小さなASCII図で示す。

```text
input
→ learned component
→ real runtime component
→ validated evidence/state
→ output
```

その後、**claim** と **non-claim** を文章で分ける。

- claim: この実験が直接支持するもの
- non-claim: 似ているがまだ測っていないもの

「自然言語理解できた」「汎化した」などの広い表現だけで済ませない。

### C. 次実験の名前と目的

```text
## C{N+1} — {short descriptive name}
```

最初に「前実験のどの制約を外すか」を1文で書く。

次に before / after をできるだけ図示する。

```text
C{N}:
query → fixed classes

C{N+1}:
query → shared/content-addressed mechanism → live candidate set
```

### D. 変数分離

最低限、以下を明記する。

```text
Scientific question:
Changed variable:
Held constant:
Training split:
Evaluation split:
Fresh seeds:
Production code change:
Prerequisite:
```

交絡因子診断では特に、変更変数を1つに限定する。

### E. 実験の具体構造

必要に応じて以下を短いコードブロックで示す。

```text
training candidates = {n}
evaluation candidates = {m}
unseen cases = {k}
queries/entity = {q}
validation cases/seed = {v}
total validation cases = {t}
```

未知entity / held-out combination / OOD条件などは、何が unseen なのかを明示する。

### F. 制限事項 / interpretation boundary

実行前に、そのC番号だけでは主張できないことを明示する。

PASS / FAIL の双方について、次の意味を事前に固定する。

```text
PASS -> ...
FAIL -> ...
INVALID -> same C number retry
```

閾値や解釈を結果を見た後で有利に変更しない。

### G. 現在HEADと期待HEAD

```text
Current/expected branch: feat/sft-target-loss
Expected HEAD: <full or short SHA>
```

リポジトリ同期を伴う場合、ユーザーのローカルHEADと remote HEAD の関係が分かるようにする。

### H. 実行コマンド

原則として Windows PowerShell 用の **1本の再現可能ブロック** を提示する。

標準構造:

```powershell
Set-Location M:\asobiba\fold

$log = "M:\asobiba\fold\runs\chatgpt-last.log"
$protected = "..."
$fixture = "..."

& {
    Write-Output "=== FOLD C{N} ... ==="
    Write-Output "=== syncing repository ==="

    git pull --rebase origin feat/sft-target-loss

    $branch = git branch --show-current
    $commit = git rev-parse HEAD

    Write-Output "branch = $branch"
    Write-Output "commit = $commit"
    Write-Output "stage = ..."
    Write-Output "fresh_seeds = ..."

    if ($branch -ne "feat/sft-target-loss") {
        throw "Unexpected branch: $branch"
    }

    $dirtyBefore = git status --porcelain --untracked-files=no
    if ($dirtyBefore) {
        throw "Tracked working tree is not clean before C{N}"
    }

    # protected hashes / prerequisite guards

    Write-Output "=== focused regression ==="
    # exact unittest list

    Write-Output "=== C{N} benchmark ==="
    # exact benchmark module

    # protected hashes / tracked-tree postcheck

    Write-Output "=== C{N} POSTCHECK ==="
    Write-Output "..."
    Write-Output "=== script error, if any ==="

} *>&1 | Tee-Object -FilePath $log
```

ルール:

- Python環境名は現在の authoritative environment を使う。推測で `.venv` と `.venv-py31315` を入れ替えない。
- focused regression は「想定件数」も併記する。
- benchmarkは `-u` 等、進捗が即時表示される形を優先する。
- production runtime modified の表示は実際の変更有無と一致させる。
- protected hash は handoff の authoritative value を使用する。

### I. 期待される進捗表示

長いbenchmarkでは例を出す。

```text
C{N} prerequisite_summary = ...
[C{N}] seed 1/3 ... start
[C{N}] seed 1/3 ... done
[C{N}] seed 1/3 case 1/12 ... remaining=11
...
```

これは厳密な全文一致ではなく、実行中に正常進行を判断するための目印。

### J. ログ回収

通常はPC用とスマホ/Termius用を両方付ける。

PC:

```powershell
$log = "M:\asobiba\fold\runs\chatgpt-last.log"
Get-Content -LiteralPath $log -Raw -Encoding UTF8 -ErrorAction Stop | Set-Clipboard
```

スマホ / Termius (OSC 52):

```powershell
$log = "M:\asobiba\fold\runs\chatgpt-last.log"
$text = Get-Content -LiteralPath $log -Raw -Encoding UTF8 -ErrorAction Stop
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($text))
[Console]::Write("$([char]27)]52;c;$b64$([char]7)")
```

### K. 停止条件

返答末尾で、その実験が終わるまで次へ進まないことを明記する。

```text
C{N}の結果を判定するまではC{N+1}へ進まない。
結果ログを貼ってもらったら、formal status / scientific interpretation / ledger update / next experiment の順で続ける。
```

## 3. 結果ログを受け取ったときの標準返答

ユーザーが実験ログを貼った場合は次の順序にする。

1. **Formal verdict** — PASS / VALID NEGATIVE / INVALID を最初に明示。
2. **Execution validity** — regression、seed、artifact hashes、tree cleanliness、prerequisite、runtime modificationを確認。
3. **Metric summary** — deciding metricsだけを表または短い箇条書きで整理。
4. **Scientific interpretation** — 何が支持され、何が否定・未確定か。
5. **Confound audit** — 異常なerror patternやfront-end/runtime confoundがないか確認。
6. **Repository update** — ledger addendum と authoritative handoff を更新。
7. **Next C design** — one scientific questionとして次実験を提示。
8. **Execution block** — 上記標準フォーマットH〜Jを付ける。
9. **Stop condition** — 次結果待ちで止める。

有効なFAILでは、すぐにモデル容量・hidden width・学習時間を増やさない。まず表現、データsplit、collision、OOV、leakage、metric、runtime path等の交絡を切り分ける。

## 4. Handoff更新ルール

各C番号の判定後:

- 詳細履歴は `docs/experiment-ledger-addendum-c{N}-c{N+1}.md` 等へ残す。
- `docs/experiment-ledger-and-handoff.md` は長大な履歴ではなく、**最新のaccepted evidence、現在のactive experiment、次のinterpretation boundary** を保持する。
- handoffには branch、environment、protected hashes、Gate status、active architecture/path を残す。
- 古いC番号の詳細がhandoffを圧迫したらaddendumへ退避するが、accepted chainを追える参照は維持する。
- 新しいチャットはまず `AGENTS.md`、このprotocol、`experiment-ledger-and-handoff.md` を読み、active C番号から再開する。

## 5. 会話上の省略ルール

標準フォーマットは一貫性を優先するが、毎回同じ説明を冗長に繰り返さない。

- 単純な途中質問への回答ではフルテンプレート不要。
- **新C番号を提示するとき**、**実験結果を正式判定するとき**、**別チャットへ引き継ぐとき**はフルまたは準フル形式を使う。
- 既知の環境情報は再質問しない。
- 実験コードに既に埋め込まれている値でも、ユーザーが実行時に確認すべき seed / candidate count / expected regression count / branch / protected hashes は返答に出す。
- 実際のrepository stateと食い違うサンプルコマンドを出さない。必要なら先にremote branchを確認する。

このprotocolの目的は、個々の実験説明をきれいに見せることではなく、**どのチャット・どのエージェントからでも、科学的claim scopeと実行再現性を失わずに次の1実験へ継続できること**である。
