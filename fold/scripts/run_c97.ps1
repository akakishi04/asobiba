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
"=== FOLD C97 V5-E oracle information-sufficiency baseline ===" | Set-Content $log -Encoding UTF8
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
"task = information sufficiency oracle",
"actions = ANSWER,ACQUIRE",
"example_space = exhaustive 32 rows",
"critical_rule = missing hidden condition that can change target -> ACQUIRE",
"negative_control = missing hidden condition irrelevant to target -> ANSWER",
""
) | Tee-Object -FilePath $log -Append
if ($branch -ne "feat/sft-target-loss") { throw "Unexpected branch: $branch" }

$dirty = (git status --porcelain --untracked-files=no | Out-String).Trim()
if ($dirty) { throw "Tracked working tree is not clean:`n$dirty" }

$resultBefore = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureBefore = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
if ($resultBefore -ne $expectedResult -or $fixtureBefore -ne $expectedFixture) { throw "Protected artifact mismatch before C97" }

$c96 = Get-ChildItem "$repo\runs" -Directory -Filter "c96-v5d-production-control-lane-*" | Sort-Object LastWriteTime -Descending | Where-Object { Test-Path (Join-Path $_.FullName "summary.json") } | Select-Object -First 1
if ($null -eq $c96) { throw "C96 summary not found" }
$c96Summary = Join-Path $c96.FullName "summary.json"

"=== import preflight ===" | Tee-Object -FilePath $log -Append
& $py -c "import fold_lm.v05_benchmarks.gate_e_information_sufficiency_oracle as m; print('C97 import OK:', m.EXPERIMENT_ID, m.ANSWER, m.ACQUIRE)" 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C97 import failed" }

$outDir = "$repo\runs\c97-v5e-information-sufficiency-$([guid]::NewGuid().ToString('N'))"
@("", "output_directory = $outDir", "C37_result_sha256_before = $resultBefore", "fixture_sha256_before = $fixtureBefore", "=== C97 benchmark ===") | Tee-Object -FilePath $log -Append

& $py -u -m fold_lm.v05_benchmarks.gate_e_information_sufficiency_oracle --c96-summary $c96Summary --output-dir $outDir 2>&1 | Tee-Object -FilePath $log -Append
$code = $LASTEXITCODE
if ($code -ne 0) { throw "C97 benchmark failed: $code" }

$s = Get-Content (Join-Path $outDir "summary.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$resultAfter = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureAfter = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
$dirtyAfter = (git status --porcelain --untracked-files=no | Out-String).Trim()

@(
"", "=== C97 SUMMARY ===",
"status = $($s.status)",
"information_sufficiency_oracle_gate_passed = $($s.summary.information_sufficiency_oracle_gate_passed)",
"critical_missing_pairs = $($s.summary.critical_missing_counterfactual_pair_count)",
"irrelevant_missing_pairs = $($s.summary.irrelevant_missing_counterfactual_pair_count)",
"required_acquisition_recall = $($s.summary.required_acquisition_recall)",
"unnecessary_acquisition_rate = $($s.summary.unnecessary_acquisition_rate)",
"ambiguous_direct_answer_attempt_count = $($s.summary.ambiguous_direct_answer_attempt_count)",
"direct_answerable_accuracy = $($s.summary.direct_answerable_accuracy)",
"irrelevant_missing_direct_accuracy = $($s.summary.irrelevant_missing_direct_accuracy)",
"post_policy_final_accuracy = $($s.summary.post_policy_final_accuracy)",
"direct_answer_coverage = $($s.summary.direct_answer_coverage)",
"C37_preserved = $($resultAfter -eq $expectedResult)",
"fixture_preserved = $($fixtureAfter -eq $expectedFixture)",
"repository_tracked_clean = $([string]::IsNullOrWhiteSpace($dirtyAfter))",
"output_directory = $outDir",
"production_runtime_modified = False",
"gate_e_candidate = False",
"", "=== script error, if any ==="
) | Tee-Object -FilePath $log -Append
