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
"=== FOLD C98 V5-E supervised information-sufficiency router ===" | Set-Content $log -Encoding UTF8
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
"task = supervised information sufficiency",
"actions = ANSWER,ACQUIRE",
"fresh_seeds = 20261171,20261172,20261173",
"train_bases = 0,1,2",
"validation_base = 3 (unseen)",
"router = production ControlLaneActionRouter",
"control_width = 4",
"hidden_width = 4",
"training_steps = 320",
"hidden_or_target_input_leakage = false",
""
) | Tee-Object -FilePath $log -Append
if ($branch -ne "feat/sft-target-loss") { throw "Unexpected branch: $branch" }

$dirty = (git status --porcelain --untracked-files=no | Out-String).Trim()
if ($dirty) { throw "Tracked working tree is not clean:`n$dirty" }

$resultBefore = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureBefore = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
if ($resultBefore -ne $expectedResult -or $fixtureBefore -ne $expectedFixture) { throw "Protected artifact mismatch before C98" }

$c97 = Get-ChildItem "$repo\runs" -Directory -Filter "c97-v5e-information-sufficiency-*" | Sort-Object LastWriteTime -Descending | Where-Object { Test-Path (Join-Path $_.FullName "summary.json") } | Select-Object -First 1
if ($null -eq $c97) { throw "C97 summary not found" }
$c97Summary = Join-Path $c97.FullName "summary.json"

"=== import preflight ===" | Tee-Object -FilePath $log -Append
& $py -c "import fold_lm.v05_benchmarks.gate_e_supervised_information_sufficiency_router as m; print('C98 import OK:', m.EXPERIMENT_ID, m.SEEDS, m.TRAIN_BASES, m.VALIDATION_BASES)" 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C98 import failed" }

"=== focused regression ===" | Tee-Object -FilePath $log -Append
& $py -m unittest tests_lm.test_v05_controller -v 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C98 focused regression failed" }

$outDir = "$repo\runs\c98-v5e-supervised-sufficiency-$([guid]::NewGuid().ToString('N'))"
@("", "output_directory = $outDir", "C37_result_sha256_before = $resultBefore", "fixture_sha256_before = $fixtureBefore", "=== C98 benchmark ===") | Tee-Object -FilePath $log -Append

& $py -u -m fold_lm.v05_benchmarks.gate_e_supervised_information_sufficiency_router --c97-summary $c97Summary --output-dir $outDir 2>&1 | Tee-Object -FilePath $log -Append
$code = $LASTEXITCODE
if ($code -ne 0) { throw "C98 benchmark failed: $code" }

$s = Get-Content (Join-Path $outDir "summary.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$resultAfter = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureAfter = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
$dirtyAfter = (git status --porcelain --untracked-files=no | Out-String).Trim()

@(
"", "=== C98 SUMMARY ===",
"status = $($s.status)",
"supervised_information_sufficiency_gate_passed = $($s.summary.supervised_information_sufficiency_gate_passed)",
"validation_action_accuracy_min = $($s.summary.validation_action_accuracy.min)",
"validation_required_acquisition_recall_min = $($s.summary.validation_required_acquisition_recall.min)",
"validation_unnecessary_acquisition_rate_max = $($s.summary.validation_unnecessary_acquisition_rate.max)",
"validation_action_flip_count_sum = $($s.summary.validation_action_flip_count.sum)",
"validation_post_policy_final_accuracy_min = $($s.summary.validation_post_policy_final_accuracy.min)",
"hidden_or_target_input_leakage = $($s.summary.hidden_or_target_input_leakage)",
"C37_preserved = $($resultAfter -eq $expectedResult)",
"fixture_preserved = $($fixtureAfter -eq $expectedFixture)",
"repository_tracked_clean = $([string]::IsNullOrWhiteSpace($dirtyAfter))",
"output_directory = $outDir",
"production_runtime_modified = False",
"gate_e_candidate = False",
"", "=== script error, if any ==="
) | Tee-Object -FilePath $log -Append
