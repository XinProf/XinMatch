# Local mirror of .github/workflows/ci.yml (Windows / PowerShell).
#
# Usage:
#   powershell -File tools/ci.ps1            # ruff + mypy + fast tests (default)
#   powershell -File tools/ci.ps1 -Slow      # include the ``slow`` marker suite
#   powershell -File tools/ci.ps1 -SkipTests # lint + types only
#
# The reference databases are not in the repository; tests that need them
# skip themselves.  Slow tests (turn-on least squares, GSAS-II subprocesses,
# L3 acceptance curve_fit) take tens of minutes.

param(
    [switch]$Slow,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$env:QT_QPA_PLATFORM = "offscreen"

Write-Host "== ruff" -ForegroundColor Cyan
python -m ruff check xinmatch tools tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== mypy" -ForegroundColor Cyan
python -m mypy
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $SkipTests) {
    $marker = if ($Slow) { "slow" } else { "not slow" }
    Write-Host "== pytest (-m `"$marker`")" -ForegroundColor Cyan
    python -m pytest -m $marker -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "CI OK" -ForegroundColor Green
