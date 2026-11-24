<#
=============================================================================
 Windows runner: the complete Nodeon test stack INCLUDING the Windows-only
 Reqnroll + FlaUI suite (black-box via UI Automation).

   powershell -ExecutionPolicy Bypass -File test_automation\tools\run_all.ps1
   ... -SkipDotnet      Python suites only
   ... -DotnetOnly      only Reqnroll + FlaUI

 Needs: Python 3.10+ (python.exe on PATH, not only the "py" launcher),
        .NET 8 SDK, an interactive desktop session (UI Automation needs a
        real, unlocked desktop - NOT a Windows service session).
=============================================================================
#>
param([switch]$SkipDotnet, [switch]$DotnetOnly)
$ErrorActionPreference = "Continue"
$TA = Split-Path -Parent $PSScriptRoot           # test_automation\
$Project = Split-Path -Parent $TA
Set-Location $TA
$env:PYTHONDONTWRITEBYTECODE = "1"
if (Test-Path reports) { Remove-Item reports -Recurse -Force }
New-Item -ItemType Directory reports\behave, reports\reqnroll | Out-Null
$failed = $false
function Step($text) { Write-Host "`n==== $text" -ForegroundColor Cyan }
function Run([scriptblock]$cmd) { & $cmd; if ($LASTEXITCODE -ne 0) { $script:failed = $true } }

if (-not $DotnetOnly) {
    Step "0 Static check of the C# step bindings"
    Run { python tools\check_csharp_bindings.py }
    Step "1 Developer unit + GUI tests"
    Push-Location $Project
    Run { python -m pytest tests -q -p no:cacheprovider --junitxml="$TA\reports\junit-dev.xml" }
    Pop-Location
    Step "2 System tests (pytest)"
    Run { python -m pytest python\system_tests -q --junitxml=reports\junit-system.xml }
    Step "3 BDD with pytest-bdd"
    Run { python -m pytest python\bdd_pytest -q --junitxml=reports\junit-pytest-bdd.xml }
    Step "4 BDD with Behave"
    Run { python -m behave features --junit --junit-directory reports\behave -f progress }
}
if (-not $SkipDotnet) {
    Step "5 The same BDD scenarios on Windows: Reqnroll + FlaUI (black-box)"
    Run { dotnet test dotnet\Nodeon.SystemTests --filter "Category!=python_only" `
            --logger "trx;LogFileName=reqnroll.trx" --results-directory reports\reqnroll }
}
if (-not $DotnetOnly) {
    Step "6 Documents, Playwright test of the report, quality gate"
    python tools\generate_docs.py > reports\generate_1.json
    Run { python -m pytest python\web_tests -q --junitxml=reports\junit-playwright.xml }
    Run { python tools\generate_docs.py --require-pass }
}
if ($failed) { Write-Host "RESULT: FAILURES" -ForegroundColor Red; exit 1 }
Write-Host "RESULT: ALL GREEN" -ForegroundColor Green; exit 0
