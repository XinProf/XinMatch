# List (default) or archive stale reference-database backups under data/.
#
# Background: iterative COD rebuilds left ~2.5 GB of `*.bak-*.db` /
# `*.db.bak-*` copies next to the live database.  They are gitignored and
# never read at runtime, but they slow down directory scans, confuse
# "which DB is current" questions and bloat any manual data-archive step.
#
# Usage:
#   powershell -File tools/clean_data_backups.ps1              # dry run (list only)
#   powershell -File tools/clean_data_backups.ps1 -Archive     # move to data/_archive
#   powershell -File tools/clean_data_backups.ps1 -Delete      # delete permanently
#
# The live databases (cod_inorganics.db / cod_full.db / cod_full_curated.db)
# are never matched: only `.bak-` / `.bak.` suffixes are considered.

param(
    [switch]$Archive,
    [switch]$Delete
)

$ErrorActionPreference = "Stop"
$dataDir = Join-Path $PSScriptRoot "..\data" | Resolve-Path -ErrorAction SilentlyContinue

if (-not $dataDir) {
    Write-Host "data/ not found - nothing to do." -ForegroundColor Yellow
    exit 0
}

$stale = Get-ChildItem -Path $dataDir -File |
    Where-Object { $_.Name -match '\.bak-' -or $_.Name -match '\.db\.bak' } |
    Sort-Object Name

if (-not $stale) {
    Write-Host "No backup databases found under $dataDir" -ForegroundColor Green
    exit 0
}

$totalMb = [math]::Round(($stale | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Host "Found $($stale.Count) backup file(s), $totalMb MB total:" -ForegroundColor Cyan
$stale | ForEach-Object {
    "{0,-52} {1,8:N1} MB" -f $_.Name, ($_.Length / 1MB)
}

if ($Delete) {
    $stale | ForEach-Object { Remove-Item $_.FullName -Force; Write-Host "deleted $($_.Name)" }
    Write-Host "Deleted $($stale.Count) file(s), freed $totalMb MB." -ForegroundColor Green
}
elseif ($Archive) {
    $archive = Join-Path $dataDir "_archive"
    New-Item -ItemType Directory -Path $archive -Force | Out-Null
    $stale | ForEach-Object { Move-Item $_.FullName -Destination $archive -Force; Write-Host "moved $($_.Name)" }
    Write-Host "Moved $($stale.Count) file(s) to $archive." -ForegroundColor Green
}
else {
    Write-Host ""
    Write-Host "Dry run only. Re-run with -Archive (move to data/_archive) or -Delete." -ForegroundColor Yellow
}
