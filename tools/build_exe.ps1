<#
.SYNOPSIS
    Build the XinMatch onedir Windows distribution with PyInstaller.

.DESCRIPTION
    1. Runs `pyinstaller xinmatch.spec` (onedir).  Exe icon comes from the
       committed assets/icons/logo.ico; version resource (1.6.1 + contact
       sshztx@outlook.com) is embedded by the spec.
    2. The COD reference DB is NOT bundled (since v1.6.0 it ships as a
       separate archive; mount it at <exe-dir>/data/cod_inorganics.db —
       auto-resolved by multi_db.default_db_path() when frozen).

    Output: dist/xinmatch-1.6.1/
        XinMatch.exe     single entry (CLI subcommands / GUI dispatcher)
        _internal/       Qt / Python / gems
        data/            (created only when the user mounts the DB archive)

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools/build_exe.ps1

.NOTES
    Requires Python 3.10 at D:\Project\XRD\python310\python.exe (override with
    env: XINMATCH_PYTHON). PyInstaller must be installed in that interpreter.
#>

[CmdletBinding()]
param(
    [string]$Version = "1.6.1"
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
# (1.6.1 + contact sshztx@outlook.com) is embedded by xinmatch.spec.

# ---- 2. Run PyInstaller ---------------------------------------------------
Write-Host "==> Running PyInstaller (clean build)"
& $pyExe -m PyInstaller --noconfirm --clean (Join-Path $root "xinmatch.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed (exit $LASTEXITCODE)." }

# ---- 3. DB note (not bundled since v1.6.0) --------------------------------
# The reference DB (~512 MB) ships separately.  Mount by extracting the DB
# archive into this directory so it lands at data/cod_inorganics.db.

# ---- Summary --------------------------------------------------------------
Write-Host ""
Write-Host "==> Build complete. Contents of $outDir :"
Get-ChildItem $outDir | Select-Object Mode, Length, Name | Format-Table -AutoSize

$guiExe = Join-Path $outDir "XinMatch.exe"
if (Test-Path $guiExe) {
    $sz = [math]::Round((Get-Item $guiExe).Length / 1MB, 1)
    Write-Host ("    {0,8} MB  {1}" -f $sz, $guiExe)
} else {
    Write-Warning "MISSING: $guiExe"
}

$totalMB = [math]::Round(((Get-ChildItem $outDir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 0)
Write-Host ""
Write-Host "==> Total bundle size: $totalMB MB"
Write-Host "==> Remember: mount the DB archive (data/cod_inorganics.db) for search to work."
