param(
    [Parameter(Mandatory = $true)][string]$C173Summary,
    [Parameter(Mandatory = $true)][string]$ExpectedHead
)
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
Set-StrictMode -Version Latest
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
$Python = Join-Path $Root ".venv-py31315\Scripts\python.exe"
$C173Summary = (Resolve-Path -LiteralPath $C173Summary).Path
$Protected = @(
    @{Path = (Join-Path $Root "runs\chatgpt-last-result.json"); Hash = "fd4a8da897bdaea9d103a252e30212c7ff842d23300d7c837333e146dee51931"},
    @{Path = (Join-Path $Root "runs\fixtures\v05-c-composition-20260921.pt"); Hash = "a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e"},
    @{Path = $C173Summary; Hash = "3c4759bbc14b4ab9849d482d2f330cbf1038c1473e2deab2aaf40f9637e635aa"}
)
function Confirm-Repository {
    $Branch = & git branch --show-current
    if ($LASTEXITCODE -ne 0 -or $Branch -ne "feat/sft-target-loss") { throw "Unexpected branch: $Branch" }
    $Head = & git rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or $Head -ne $ExpectedHead) { throw "Unexpected HEAD: $Head" }
    $Dirty = @(& git status --porcelain --untracked-files=no)
    if ($LASTEXITCODE -ne 0 -or $Dirty.Count -ne 0) { throw "Tracked tree must be clean" }
    foreach ($Item in $Protected) {
        $Actual = (Get-FileHash -LiteralPath $Item.Path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($Actual -ne $Item.Hash) { throw "Protected hash mismatch: $($Item.Path)" }
    }
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "Authoritative Python is missing" }
Confirm-Repository
Write-Output "=== FOLD C174 V5-E learned necessity syntax ablation ==="
Write-Output "branch = feat/sft-target-loss; commit = $ExpectedHead"
Write-Output "training = CPU float32, threads2; seeds174001/174002/174003; two paired input arms"
Write-Output "MLP parameters = 26114; each model = 2000 Adam updates, batch256; final checkpoint only"
Write-Output "train = 42444 rows / 36 semantic groups; pilot eval = 9396 rows / 4 groups"
Write-Output "pilot predictions = 56376; actual acquisitions/proof checker/evidence writes = 0"
Write-Output "expected_focused_tests = 953 (921 existing + 32 new); Gate_E = NOT_PASSED"
$Precheck = @'
from pathlib import Path
import sys
from fold_lm.v05_benchmarks import gate_e_c174_learned_necessity as b
p=b.validate_parent(sys.argv[1]);b.protect_sources(Path.cwd(),p)
print('source_precheck = PASS',flush=True)
'@
& $Python -u -c $Precheck $C173Summary
if ($LASTEXITCODE -ne 0) { throw "C174 source precheck failed" }
$Regression = @'
from pathlib import Path
import sys,unittest
from fold_lm.v05_benchmarks import gate_e_c174_learned_necessity as b
names=b.regression_modules(Path.cwd())
assert len(names)==58 and len(set(names))==58
suite=unittest.defaultTestLoader.loadTestsFromNames(names)
assert suite.countTestCases()==953, f'Expected953 tests, got{suite.countTestCases()}'
r=unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if r.wasSuccessful() else 1)
'@
$Out = Join-Path $Root ("runs\c174-v5e-learned-necessity-" + [guid]::NewGuid().ToString("N"))
$Completed = $false
try {
    Write-Output "=== focused regression ==="
    & $Python -u -c $Regression
    if ($LASTEXITCODE -ne 0) { throw "C174 regression failed; do not start benchmark" }
    Confirm-Repository
    & $Python -u -m fold_lm.v05_benchmarks.gate_e_c174_learned_necessity `
        --c173-summary $C173Summary --output-dir $Out --expected-head $ExpectedHead
    if ($LASTEXITCODE -ne 0) { throw "C174 execution failed; preserve its invalid report" }
    $Postcheck = @'
from pathlib import Path
import json,sys
from fold_lm.v05_benchmarks import gate_e_c174_learned_necessity as b
root=Path.cwd();out=Path(sys.argv[1]);parent=b.validate_parent(sys.argv[2]);b.protect_sources(root,parent)
p=json.loads((out/'summary.json').read_text(encoding='utf-8'))
assert p['experiment_id']==b.EXPERIMENT_ID and p['commit_sha']==sys.argv[3]
assert p['diagnostic_execution_valid'] is True and p['status'] in ('PASS','FAIL')
assert p['data_profile']==b.EXPECTED_DATA and p['trained_models']==6 and p['pilot_predictions']==56376
assert p['training_steps_total']==12000 and p['training_examples_drawn']==3072000
for name,want in p['input_sha256'].items(): assert b.sha(name)==want,name
for a in p['artifacts']:
    assert Path(a['file']).name==a['file'],'unsafe artifact name'
    f=out/a['file'];assert b.sha(f)==a['sha256'] and f.stat().st_size==a['serialized_bytes'],str(f)
assert ('PASS' if b.gate(p['pairs'],p['baselines']['missing_fact_rule']) else 'FAIL')==p['status']
print('summary =',out/'summary.json')
print('summary_sha256 =',b.sha(out/'summary.json'))
print('scientific_status =',p['status'])
'@
    & $Python -u -c $Postcheck $Out $C173Summary $ExpectedHead
    if ($LASTEXITCODE -ne 0) { throw "C174 artifact postcheck failed" }
    $Completed = $true
}
finally {
    Write-Output "=== C174 POSTCHECK ==="
    Confirm-Repository
    Write-Output "protected_inputs = preserved; tracked_tree = clean; execution_HEAD = preserved"
    Write-Output "run_execution_valid = $Completed"
}
