$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repo = "M:\asobiba\fold"
$py = "$repo\.venv-py31315\Scripts\python.exe"
$log = "$repo\runs\chatgpt-last.log"
$resultPath = "$repo\runs\chatgpt-last-result.json"
$fixturePath = "$repo\runs\fixtures\v05-c-composition-20260921.pt"
$expectedResult = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
$expectedFixture = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"

New-Item -ItemType Directory -Force "$repo\runs" | Out-Null
"=== FOLD C100 V5-E acquisition failure oracle ===" | Set-Content $log -Encoding UTF8
Set-Location $repo

"=== syncing repository ===" | Tee-Object -FilePath $log -Append
git pull --rebase origin feat/sft-target-loss 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "git pull failed" }

$branch = (git branch --show-current).Trim()
$head = (git rev-parse HEAD).Trim()
@(
"branch = $branch",
"commit = $head",
"stage = V5-E",
"task = acquisition failure oracle",
"actions = ANSWER,ACQUIRE,STOP_UNRESOLVED",
"outcomes = SUCCESS,UNAVAILABLE,DENIED,INVALID",
"acquisition_budget = 1",
"authority = model proposes; runtime owns outcome and evidence mutation",
"failure_rule = failed/untrusted acquisition never commits evidence and terminates unresolved",
""
) | Tee-Object -FilePath $log -Append
if ($branch -ne "feat/sft-target-loss") { throw "Unexpected branch: $branch" }

$dirty = (git status --porcelain --untracked-files=no | Out-String).Trim()
if ($dirty) { throw "Tracked working tree is not clean:`n$dirty" }

$resultBefore = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureBefore = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
if ($resultBefore -ne $expectedResult -or $fixtureBefore -ne $expectedFixture) { throw "Protected artifact mismatch before C100" }

$c99 = Get-ChildItem "$repo\runs" -Directory -Filter "c99-v5e-acquire-cycle-*" | Sort-Object LastWriteTime -Descending | Where-Object { Test-Path (Join-Path $_.FullName "summary.json") } | Select-Object -First 1
if ($null -eq $c99) { throw "C99 summary not found" }
$c99Summary = Join-Path $c99.FullName "summary.json"

"=== import preflight ===" | Tee-Object -FilePath $log -Append
& $py -c "import fold_lm.v05_benchmarks.gate_e_acquisition_failure_oracle as m; print('C100 import OK:', m.EXPERIMENT_ID, m.OUTCOMES, m.STOP_UNRESOLVED)" 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C100 import failed" }

$outDir = "$repo\runs\c100-v5e-acquisition-failure-$([guid]::NewGuid().ToString('N'))"
@("", "output_directory = $outDir", "C37_result_sha256_before = $resultBefore", "fixture_sha256_before = $fixtureBefore", "=== C100 benchmark ===") | Tee-Object -FilePath $log -Append

& $py -u -m fold_lm.v05_benchmarks.gate_e_acquisition_failure_oracle --c99-summary $c99Summary --output-dir $outDir 2>&1 | Tee-Object -FilePath $log -Append
$code = $LASTEXITCODE
if ($code -ne 0) { throw "C100 benchmark failed: $code" }

$s = Get-Content (Join-Path $outDir "summary.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$resultAfter = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureAfter = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
$dirtyAfter = (git status --porcelain --untracked-files=no | Out-String).Trim()

@(
"", "=== C100 SUMMARY ===",
"status = $($s.status)",
"acquisition_failure_oracle_gate_passed = $($s.summary.acquisition_failure_oracle_gate_passed)",
"answerable_zero_acquisition_rate = $($s.summary.answerable_zero_acquisition_rate)",
"success_post_acquisition_answer_rate = $($s.summary.success_post_acquisition_answer_rate)",
"success_final_accuracy = $($s.summary.success_final_accuracy)",
"success_evidence_commit_rate = $($s.summary.success_evidence_commit_rate)",
"failure_stop_unresolved_rate = $($s.summary.failure_stop_unresolved_rate)",
"failure_no_evidence_commit_rate = $($s.summary.failure_no_evidence_commit_rate)",
"failure_no_guessed_answer_rate = $($s.summary.failure_no_guessed_answer_rate)",
"repeat_acquisition_count = $($s.summary.repeat_acquisition_count)",
"budget_violation_count = $($s.summary.budget_violation_count)",
"C37_preserved = $($resultAfter -eq $expectedResult)",
"fixture_preserved = $($fixtureAfter -eq $expectedFixture)",
"repository_tracked_clean = $([string]::IsNullOrWhiteSpace($dirtyAfter))",
"output_directory = $outDir",
"production_runtime_modified = False",
"gate_e_candidate = False",
"", "=== script error, if any ==="
) | Tee-Object -FilePath $log -Append
