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
"=== FOLD C88 V5-D learned sparse wall-clock runtime ===" | Set-Content $log -Encoding UTF8
Set-Location $repo

git pull --rebase origin feat/sft-target-loss 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "git pull failed" }

$branch = (git branch --show-current).Trim()
$head = (git rev-parse HEAD).Trim()
@(
"branch = $branch",
"commit = $head",
"stage = V5-D",
"task = composition",
"runtime_comparison = learned_sparse_end_to_end vs fixed_max_2step",
"c87_seeds_reused_for_runtime_measurement = 20261121,20261122,20261123",
"maximum_runtime_ratio = 0.95",
"minimum_required_speedup = 0.05",
""
) | Tee-Object -FilePath $log -Append

if ($branch -ne "feat/sft-target-loss") { throw "Unexpected branch: $branch" }
$dirty = (git status --porcelain --untracked-files=no | Out-String).Trim()
if ($dirty) { throw "Tracked working tree is not clean:`n$dirty" }

$resultBefore = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureBefore = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
if ($resultBefore -ne $expectedResult -or $fixtureBefore -ne $expectedFixture) { throw "Protected artifact mismatch before C88" }

$c87 = Get-ChildItem "$repo\runs" -Directory -Filter "c87-v5d-variable-router-*" | Sort-Object LastWriteTime -Descending | Where-Object { Test-Path (Join-Path $_.FullName "summary.json") } | Select-Object -First 1
if ($null -eq $c87) { throw "C87 summary not found" }
$c87Summary = Join-Path $c87.FullName "summary.json"

"=== import preflight ===" | Tee-Object -FilePath $log -Append
& $py -c "import fold_lm.v05_benchmarks.gate_d_composition_sparse_wallclock_runtime as m; print('C88 import OK:', m.EXPERIMENT_ID, m.SEEDS, m.MAX_RUNTIME_RATIO)" 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C88 import failed" }

"=== focused regression ===" | Tee-Object -FilePath $log -Append
& $py -m unittest tests_lm.test_v05_controller tests_lm.test_v05_composition_task tests_lm.test_v05_shared_basis_core -v 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C88 focused regression failed" }

$outDir = "$repo\runs\c88-v5d-wallclock-$([guid]::NewGuid().ToString('N'))"
@("", "output_directory = $outDir", "C37_result_sha256_before = $resultBefore", "fixture_sha256_before = $fixtureBefore", "=== C88 benchmark ===") | Tee-Object -FilePath $log -Append

& $py -u -m fold_lm.v05_benchmarks.gate_d_composition_sparse_wallclock_runtime --c87-summary $c87Summary --output-dir $outDir 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { throw "C88 benchmark failed" }

$s = Get-Content (Join-Path $outDir "summary.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$resultAfter = (Get-FileHash $resultPath -Algorithm SHA256).Hash
$fixtureAfter = (Get-FileHash $fixturePath -Algorithm SHA256).Hash
$dirtyAfter = (git status --porcelain --untracked-files=no | Out-String).Trim()

@(
"", "=== C88 SUMMARY ===",
"status = $($s.status)",
"learned_sparse_wallclock_gate_passed = $($s.summary.learned_sparse_wallclock_gate_passed)",
"all_outputs_allclose = $($s.summary.all_outputs_allclose)",
"logical_compute_reduction_mean = $($s.summary.logical_compute_reduction_vs_fixed_max.mean)",
"device_ratio_mean = $($s.summary.adaptive_over_fixed_device_latency.mean)",
"device_ratio_max = $($s.summary.adaptive_over_fixed_device_latency.max)",
"wall_ratio_mean = $($s.summary.adaptive_over_fixed_wall_latency.mean)",
"wall_ratio_max = $($s.summary.adaptive_over_fixed_wall_latency.max)",
"C37_preserved = $($resultAfter -eq $expectedResult)",
"fixture_preserved = $($fixtureAfter -eq $expectedFixture)",
"repository_tracked_clean = $([string]::IsNullOrWhiteSpace($dirtyAfter))",
"output_directory = $outDir",
"production_runtime_modified = False",
"gate_d_candidate = False",
"", "=== script error, if any ==="
) | Tee-Object -FilePath $log -Append
