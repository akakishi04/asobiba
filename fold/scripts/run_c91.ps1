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
"=== FOLD C91 V5-D selected compact router large-width gate ===" | Set-Content $log -Encoding UTF8
Set-Location $repo

git pull --rebase origin feat/sft-target-loss 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "git pull failed" }
$branch = (git branch --show-current).Trim()
$head = (git rev-parse HEAD).Trim()
@("branch = $branch", "commit = $head", "stage = V5-D", "widths = 3072,5120", "router_hidden_width = 4", "fresh_seeds = 20261141,20261142,20261143", "maximum_runtime_ratio = 0.80", "maximum_router_core_persistent_ratio = 0.01", "maximum_router_vram_cost_gib = 0.05", "") | Tee-Object -FilePath $log -Append
if ($branch -ne "feat/sft-target-loss") { throw "Unexpected branch" }

$dirty = (git status --porcelain --untracked-files=no | Out-String).Trim()
if ($dirty) { throw "Tracked tree dirty:`n$dirty" }
$resultBefore = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureBefore = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
if ($resultBefore -ne $expectedResult -or $fixtureBefore -ne $expectedFixture) { throw "Protected artifact mismatch" }

$c90 = Get-ChildItem "$repo\runs" -Directory -Filter "c90-v5d-router-frontier-*" | Sort-Object LastWriteTime -Descending | Where-Object { Test-Path (Join-Path $_.FullName "summary.json") } | Select-Object -First 1
if ($null -eq $c90) { throw "C90 summary not found" }
$c90Summary = Join-Path $c90.FullName "summary.json"

"=== import preflight ===" | Tee-Object -FilePath $log -Append
& $py -c "import fold_lm.v05_benchmarks.gate_d_selected_router_large_width_runtime_vram as m; print('C91 import OK:', m.EXPERIMENT_ID, m.SEEDS)" 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C91 import failed" }

"=== focused regression ===" | Tee-Object -FilePath $log -Append
& $py -m unittest tests_lm.test_v05_controller tests_lm.test_v05_shared_basis_core -v 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C91 focused regression failed" }

$outDir = "$repo\runs\c91-v5d-large-router-$([guid]::NewGuid().ToString('N'))"
@("", "output_directory = $outDir", "=== C91 benchmark ===") | Tee-Object -FilePath $log -Append
& $py -u -m fold_lm.v05_benchmarks.gate_d_selected_router_large_width_runtime_vram --c90-summary $c90Summary --output-dir $outDir 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C91 benchmark failed" }

$s = Get-Content (Join-Path $outDir "summary.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$resultAfter = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureAfter = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
$dirtyAfter = (git status --porcelain --untracked-files=no | Out-String).Trim()
@("", "=== C91 SUMMARY ===", "status = $($s.status)", "selected_router_large_width_gate_passed = $($s.summary.selected_router_large_width_gate_passed)", "action_accuracy_min = $($s.summary.action_accuracy.min)", "class_recall_min = $($s.summary.minimum_class_recall.min)", "device_ratio_max = $($s.summary.learned_over_fixed_device.max)", "wall_ratio_max = $($s.summary.learned_over_fixed_wall.max)", "router_core_ratio_max = $($s.summary.router_over_core_persistent_ratio.max)", "router_vram_cost_gib_max = $($s.summary.router_device_free_vram_cost_gib.max)", "all_outputs_allclose = $($s.summary.all_outputs_allclose)", "C37_preserved = $($resultAfter -eq $expectedResult)", "fixture_preserved = $($fixtureAfter -eq $expectedFixture)", "repository_tracked_clean = $([string]::IsNullOrWhiteSpace($dirtyAfter))", "output_directory = $outDir", "gate_d_candidate = True", "", "=== script error, if any ===") | Tee-Object -FilePath $log -Append
