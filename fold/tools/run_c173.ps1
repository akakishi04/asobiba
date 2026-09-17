param(
    [Parameter(Mandatory = $true)][string]$C172Summary,
    [Parameter(Mandatory = $true)][string]$ExpectedHead
)
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
Set-Location (Split-Path -Parent $PSScriptRoot)
$python = Join-Path (Get-Location) ".venv-py31315\Scripts\python.exe"
$before = @{}
$executionError = $null
$postcheckOk = $false
$report = $null
$commit = $null
function Assert-NativeExit([string]$Context) {
    if ($LASTEXITCODE -ne 0) { throw "$Context failed; exit code = $LASTEXITCODE" }
}
try {
    Write-Output "=== FOLD C173 V5-E bounded acquisition lifecycle ==="
    $branch = git branch --show-current
    Assert-NativeExit "Reading branch"
    $commit = git rev-parse HEAD
    Assert-NativeExit "Reading HEAD"
    if ($branch -ne "feat/sft-target-loss" -or $commit -ne $ExpectedHead) { throw "Unexpected branch/HEAD" }
    $dirty = @(git status --porcelain --untracked-files=no)
    Assert-NativeExit "Checking tracked tree"
    if ($dirty.Count -gt 0) { throw "Tracked working tree is not clean" }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Python environment missing" }
    $required = @{}
    $required[$C172Summary] = "B1698509FA5AB384B86731662092568E9348FE907AB9F4707ED0EA802709E943"
    $required["runs\chatgpt-last-result.json"] = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
    $required["runs\fixtures\v05-c-composition-20260921.pt"] = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"
    foreach ($path in $required.Keys) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing protected input: $path" }
        $before[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        if ($before[$path] -ne $required[$path]) { throw "Protected input hash mismatch: $path" }
    }
    & $python -c "from pathlib import Path; import sys; from fold_lm.v05_benchmarks import gate_e_c173_acquisition_lifecycle as b; b.protect_sources(Path.cwd(),b.validate_parent(Path(sys.argv[1])))" $C172Summary
    Assert-NativeExit "Source precheck"
    Write-Output "source_precheck = PASS"
    Write-Output "branch = $branch"
    Write-Output "commit = $commit"
    Write-Output "stage = V5-E-BOUNDED-ACQUISITION-LIFECYCLE"
    Write-Output "scenarios = 122; groups = 8; scripted action calls = 236; dispatch calls = 143"
    Write-Output "provider calls = 98; file read attempts = 95; admitted facts = 24; supplied-proof answers = 12"
    Write-Output "reservations = 122; internal units = 417; verifier calls = 18; checked steps = 36"
    Write-Output "OBSERVE and ASK_USER are LOCAL FILE SIMULATIONS; network/user messaging = 0"
    Write-Output "learned policy/training/fresh seeds = 0; production runtime modified = False; Gate_E = NOT_PASSED"
    Write-Output "expected_focused_tests = 921 (885 existing + 36 new)"
    $testsJson = & $python -c "import json; from pathlib import Path; from fold_lm.v05_benchmarks import gate_e_c173_acquisition_lifecycle as b; print(json.dumps(b.regression_modules(Path.cwd())))"
    Assert-NativeExit "Reading regression list"
    $tests = @($testsJson | ConvertFrom-Json)
    if ($tests.Count -ne 57) { throw "Expected 57 focused modules" }
    $count = & $python -c "import sys,unittest; print(unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:]).countTestCases())" @tests
    Assert-NativeExit "Counting focused tests"
    if ($count -ne "921") { throw "Expected 921 focused tests, got $count" }
    Write-Output "=== focused regression ==="
    & $python -m unittest @tests -v
    Assert-NativeExit "C173 focused regression"
    $out = Join-Path "runs" ("c173-v5e-acquisition-lifecycle-" + [guid]::NewGuid().ToString("N"))
    & $python -u -m fold_lm.v05_benchmarks.gate_e_c173_acquisition_lifecycle `
        --c172-summary $C172Summary --output-dir $out --expected-head $ExpectedHead
    Assert-NativeExit "C173 execution"
    $summary = Join-Path $out "summary.json"
    $report = Get-Content -LiteralPath $summary -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($report.experiment_id -ne "C173-v5e-bounded-acquisition-lifecycle" -or $report.stage -ne "V5-E-BOUNDED-ACQUISITION-LIFECYCLE" -or $report.commit_sha -ne $commit) { throw "Wrong experiment identity" }
    if ($report.status -notin @("PASS", "FAIL") -or $report.diagnostic_execution_valid -ne $true -or $report.gate_e_candidate -ne $false -or $report.production_runtime_modified -ne $false) { throw "Invalid result controls" }
    & $python -c "import json,sys; from pathlib import Path; from fold_lm.v05_benchmarks import gate_e_c173_acquisition_lifecycle as b; p=Path(sys.argv[1]); r=json.loads(p.read_text(encoding='utf-8')); assert (r['status']=='PASS')==b.gate(r['summary']); assert all(r[k]==0 for k in ('learned_forward_calls','training_steps','fresh_seed_count','network_calls','core_evidence_writes')); assert r['records']['file']=='acquisition-results.json' and r['plan']['file']=='acquisition-plan.json'; d=p.parent/r['records']['file']; assert b.sha(d)==r['records']['sha256'] and d.stat().st_size==r['records']['serialized_bytes']; assert len(json.loads(d.read_text(encoding='utf-8')))==r['records']['rows']==122; assert b.sha(p.parent/r['plan']['file'])==r['plan']['sha256']; assert all(b.sha(Path(x))==h for x,h in r['input_sha256'].items()); b.protect_sources(Path.cwd(),b.validate_parent(Path(sys.argv[2])))" $summary $C172Summary
    Assert-NativeExit "Result consistency and artifact checks"
    Write-Output "summary = $summary"
    Write-Output "summary_sha256 = $((Get-FileHash -LiteralPath $summary -Algorithm SHA256).Hash)"
    Write-Output "scientific_status = $($report.status)"
} catch {
    $executionError = $_
    Write-Output "=== C173 execution error ==="
    Write-Output $_
} finally {
    try {
        foreach ($path in $before.Keys) {
            if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $before[$path]) { throw "Protected input changed: $path" }
        }
        $headAfter = git rev-parse HEAD
        Assert-NativeExit "Postcheck HEAD"
        $dirtyAfter = @(git status --porcelain --untracked-files=no)
        Assert-NativeExit "Postcheck tracked tree"
        if ($headAfter -ne $commit -or $dirtyAfter.Count -gt 0) { throw "HEAD/tree changed" }
        $postcheckOk = $true
        Write-Output "=== C173 POSTCHECK ==="
        Write-Output "protected_inputs = preserved; tracked_tree = clean; execution_HEAD = preserved"
    } catch {
        if ($null -eq $executionError) { $executionError = $_ }
        Write-Output "=== C173 postcheck error ==="
        Write-Output $_
    }
    $valid = $null -eq $executionError -and $postcheckOk -and $null -ne $report
    Write-Output "run_execution_valid = $valid"
}
if ($null -ne $executionError) { throw $executionError }
