<#
.SYNOPSIS
    Build the XinMatch onedir Windows distribution with PyInstaller.

.DESCRIPTION
    1. Runs `pyinstaller xinmatch.spec` (onedir).  Exe icon comes from the
       committed assets/icons/logo.ico; version resource (3.3.0 + contact
       sshztx@outlook.com) is embedded by the spec.
    2. Since v3.0.0 the **default reference library** `COD-Inorg-*.xinDB`
       (v3 columnar) IS bundled: the spec collects it into `data/` and this
       script moves it out of `_internal/` to `<exe-dir>\data\`, so the
       portable package searches out of the box.  Override the source file
       with the env var `XINMATCH_BUNDLE_XINDB`.

    构建变体（v1.7.0 起）：
      -Variant release  (默认) 正式版：含注册机制，启动时检查注册；
                        输出 dist/xinmatch-<Version>/，用于 Inno Setup 安装包。
      -Variant internal          内部评估版：不接入注册机制，状态栏右端用
                        红色加粗字显示「内部评估版本」；
                        输出 dist/xinmatch-internal-<Version>/。

    Output: dist/xinmatch-<Version>/   (或 dist/xinmatch-internal-<Version>/)
        XinMatch.exe     single entry (CLI subcommands / GUI dispatcher)
        _internal/       Qt / Python / gems + variant.txt
        data/            COD-Inorg-<snapshot>.xinDB  ← 默认参考库（可替换）

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools/build_exe.ps1
    powershell -ExecutionPolicy Bypass -File tools/build_exe.ps1 -Variant internal

.NOTES
    Requires Python 3.10 at D:\Project\XRD\python310\python.exe (override with
    env: XINMATCH_PYTHON). PyInstaller must be installed in that interpreter.
#>

[CmdletBinding()]
param(
    [string]$Version = "3.3.0",
    [ValidateSet("release", "internal")]
    [string]$Variant = "release"
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
$outDir   = if ($Variant -eq "internal") {
    Join-Path $distDir "xinmatch-internal-$Version"
} else {
    Join-Path $distDir "xinmatch-$Version"
}

# 变体通过环境变量传给 xinmatch.spec（spec 把 variant.txt 打进产物）。
$env:XINMATCH_BUILD_VARIANT = $Variant

# 构建前断言：变体必须确定性地传到 spec。
# 为什么必要：spec 用 BUNDLE_NAME 决定 COLLECT 的输出目录。若变体在这个
# 进程里读错，internal 构建会算出 release 的名字，PyInstaller 的 COLLECT
# 会先删掉 dist\xinmatch-<Version>\ —— 也就是**把另一个已建好的变体清掉**。
# 实测环境变量在部分嵌套调用链上会丢（v2.0.0 构建时踩到过），所以额外写
# 一份 build\variant.request 给 spec 读（文件优先于环境变量），并在此校验收
# 到的内容，动手前就失败。
$reqFile = Join-Path $buildDir "variant.request"
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
Set-Content -Path $reqFile -Value $Variant -Encoding ASCII -NoNewline
$reqVal = (Get-Content $reqFile -Raw).Trim()
if ($reqVal -ne $Variant) {
    throw "variant.request mismatch: wrote '$Variant', read back '$reqVal'. Nothing was built."
}
$envVal = "$($env:XINMATCH_BUILD_VARIANT)".Trim()
Write-Host "==> Variant request OK : file='$reqVal' env='$envVal' (file wins in spec)"

Write-Host "==> Project root : $root"
Write-Host "==> Python       : $pyExe"
Write-Host "==> Variant      : $Variant"
Write-Host "==> Output       : $outDir"

# ---- 1. Icon / version resource -----------------------------------------
# Exe icon comes from the committed assets/icons/logo.ico; version resource
# (1.6.1 + contact sshztx@outlook.com) is embedded by xinmatch.spec.

# ---- 2. Run PyInstaller ---------------------------------------------------
Write-Host "==> Running PyInstaller (clean build)"
& $pyExe -m PyInstaller --noconfirm --clean (Join-Path $root "xinmatch.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed (exit $LASTEXITCODE)." }

# ---- 2b. Variant marker sanity check --------------------------------------
# 漏放/错放 variant.txt 会让内部版退化成强制注册版（或反之），构建即校验。
$marker = $null
foreach ($p in @((Join-Path $outDir "variant.txt"), (Join-Path $outDir "_internal\variant.txt"))) {
    if (Test-Path $p) { $marker = $p; break }
}
if (-not $marker) { throw "variant.txt missing in $outDir (build variant would silently fall back to release)." }
$markerText = (Get-Content $marker -Raw).Trim()
if ($markerText -ne $Variant) {
    throw "variant.txt content '$markerText' != requested variant '$Variant' ($marker)."
}
Write-Host "==> Variant marker OK : $marker = $markerText"

# ---- 3. Default reference library -> <outDir>\data -------------------------
# PyInstaller 6 把 datas 收进 _internal/，但便携包要求库就在 exe 旁边的
# data\ 里（用户可自行替换/追加 .xinDB 而不用碰 _internal）。
$bundledData = Join-Path $outDir "_internal\data"
$exposedData = Join-Path $outDir "data"
if (Test-Path $bundledData) {
    New-Item -ItemType Directory -Force -Path $exposedData | Out-Null
    Get-ChildItem $bundledData -File | ForEach-Object {
        Move-Item -Path $_.FullName -Destination (Join-Path $exposedData $_.Name) -Force
    }
    Remove-Item $bundledData -Recurse -Force -ErrorAction SilentlyContinue
}
$lib = Get-ChildItem $exposedData -Filter "*.xinDB" -ErrorAction SilentlyContinue |
    Sort-Object Name | Select-Object -Last 1
if ($lib) {
    $libMB = [math]::Round($lib.Length / 1MB, 0)
    Write-Host "==> Bundled library OK : data\$($lib.Name) ($libMB MB)"
} else {
    Write-Warning "No .xinDB under $exposedData — the portable build will not search out of the box."
}

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
if ($lib) {
    Write-Host "==> Default reference library: data\$($lib.Name) (解压即可检索)"
} else {
    Write-Host "==> Remember: no .xinDB was bundled — mount one via 设置→参考数据库…"
}
