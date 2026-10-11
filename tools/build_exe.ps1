<#
.SYNOPSIS
    Build the XinMatch onedir Windows distribution with PyInstaller.

.DESCRIPTION
    1. Runs `pyinstaller xinmatch.spec` (onedir).  Exe icon comes from the
       committed assets/icons/logo.ico; version resource (1.0.0 + contact
       sshztx@outlook.com) is embedded by the spec.
    2. Relocates the bundled COD DB from <dist>/_internal/data/ to <dist>/data/
       (next to the exes) so users can find / copy it easily.

    Output: dist/xinmatch-1.0.0/
        XinMatch.exe          single entry (CLI subcommands / GUI dispatcher)
        data/cod_inorganics.db reference DB
        _internal/           Qt / Python / gems

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools/build_exe.ps1

.NOTES
    Requires Python 3.10 at D:\Project\XRD\python310\python.exe (override with
    env: XINMATCH_PYTHON). PyInstaller must be installed in that interpreter.
#>

[CmdletBinding()]
param(
    [string]$Version = "1.2.0"
)

$ErrorActionPreference = "Stop"

# ---- Resolve paths --------------------------------------------------------
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$root = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $root

$pyExe = if ($env:XINMATCH_PYTHON) { $env:XINMATCH_PYTHON } else { "D:\Project\XRD\python310\python.exe" }
if (-not (Test-Path $pyExe)) {
    throw "Python not found at $pyExe (set XINMATCH_PYTHON to override)."
}

$buildDir = Join-Path $root "build"
$distDir  = Join-Path $root "dist"
$outDir   = Join-Path $distDir "xinmatch-$Version"

Write-Host "==> Project root : $root"
Write-Host "==> Python       : $pyExe"
Write-Host "==> Output       : $outDir"

# ---- 1. Icon / version resource -----------------------------------------
# Exe icon comes from the committed assets/icons/logo.ico; version resource
# (1.0.0 + contact sshztx@outlook.com) is embedded by xinmatch.spec.

# ---- 2. Run PyInstaller ---------------------------------------------------
Write-Host "==> Running PyInstaller (clean build)"
& $pyExe -m PyInstaller --noconfirm --clean (Join-Path $root "xinmatch.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed (exit $LASTEXITCODE)." }

# ---- 3. Relocate COD DB to top-level data/ next to the exes ---------------
$bundledDb = Join-Path $outDir "_internal\data\cod_inorganics.db"
$shipDbDir = Join-Path $outDir "data"
$shipDb    = Join-Path $shipDbDir "cod_inorganics.db"
if (Test-Path $bundledDb) {
    New-Item -ItemType Directory -Force -Path $shipDbDir | Out-Null
    Move-Item -Force $bundledDb $shipDb
    Write-Host "==> Relocated DB -> $shipDb"
} else {
    Write-Warning "Bundled DB not found at $bundledDb (spec datas may have changed)."
}

# ---- Summary --------------------------------------------------------------
Write-Host ""
Write-Host "==> Build complete. Contents of $outDir :"
Get-ChildItem $outDir | Select-Object Mode, Length, Name | Format-Table -AutoSize

$guiExe = Join-Path $outDir "XinMatch.exe"
foreach ($f in @($guiExe, $shipDb)) {
    if (Test-Path $f) {
        $sz = [math]::Round((Get-Item $f).Length / 1MB, 1)
        Write-Host ("    {0,8} MB  {1}" -f $sz, $f)
    } else {
        Write-Warning "MISSING: $f"
    }
}

$totalMB = [math]::Round(((Get-ChildItem $outDir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 0)
Write-Host ""
Write-Host "==> Total bundle size: $totalMB MB"
