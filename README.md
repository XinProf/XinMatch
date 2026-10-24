<div align="center">
  <img src="assets/icons/logo_256.png" alt="XinMatch logo" width="200">
</div>

# XinMatch

Open-source **powder X-ray diffraction (XRPD) phase analysis** platform — a
clean-room implementation guided by publicly documented XRD phase-analysis
workflows, published algorithms and open reference data (COD).

> ✅ **v3.0.0.** Core computation kernel + full GUI + dual-mode search-match
> (peak-list FoM / FPFM full-profile fitting (Full Pattern Fitting Match, formerly SMPF)) + true March-Dollase preferred
> orientation modeling + GSAS-II refinement pipeline + quantitative Rietveld
> (main-phase wt% < 3 on certified samples) are complete and packaged
> (Windows installer / portable). v3.0.0 replaces the last legacy reference
> formats with the single **v3 columnar `.xinDB`** layout and ships the
> **COD-Inorg** library as the built-in default:
>
> * default library = `COD-Inorg-<snapshot>.xinDB`, bundled at `data/` in the
>   portable build → **works out of the box**, no separate download needed;
> * one reader, one search path (`search_match_v3`); the v2 SQLite
>   (`cod_inorganics.db`), PolyXRD-dump and PDF-2 readers were **deleted**,
>   not deprecated;
> * still mountable from any folder (设置→参考数据库…, or
>   `xinmatch libraries --add <path>`), `.xinDB` only.
>
> See [ROADMAP_v3.md](ROADMAP_v3.md) for the full implementation plan and
> [docs/STATUS.md](docs/STATUS.md) for current progress.

## What XinMatch does

- **Qualitative phase analysis** (search-match): identify crystalline phases
  from an experimental powder diffraction pattern against a reference database.
- **Quantitative phase analysis** (RIR, internal standard, Rietveld).
- **Raw data preprocessing**: smoothing, background subtraction, Kα₂ stripping,
  zero-point / displacement correction.
- **Profile fitting & peak search**.
- **Rietveld / Le Bail refinement** (delegated to GSAS-II).
- **Powder indexing** (Treor / Dicvol).
- **Microstructure**: crystallite size (Scherrer), microstrain, crystallinity.
- **Reports & export**, **GUI** (PySide6), **CLI / batch scripting**.
- **Reference-database mounting**: besides the bundled `COD-Inorg` library, any
  other `.xinDB` library can be mounted from **any folder**
  (设置→参考数据库…, or `xinmatch libraries --add <path>`). v3 libraries are
  self-contained columnar files, so nothing is copied or converted.
- **3COD libraries are split by provenance** (`tools/split_3cod.py`):
  `COD-Inorg` (experimental, 79 k), `PCOD-Inorg` (predicted, 1.06 M),
  `TCOD-Inorg` (theoretical, 47 k). Mount all three side by side in XinMatch;
  PolyXRD only ever picks up the experimental one, because the other two ship
  without a `phases` table. See
  [docs/ACCEPTANCE-3COD-20261020.md §6](docs/ACCEPTANCE-3COD-20261020.md).
- **Reference libraries are built in the sibling repo, not here.**
  `XinMatch-DataBase` builds all six libraries (`COD` / `PCOD` / `TCOD` ×
  `Inorg` / `Full`); the CIF sources live one level up in
  `../sync-COD` (override with `XRD_DATA_ROOT`), and the built `.xinDB`
  files default to `XinMatch-DataBase/data/`. See that repo's
  [`docs/构建与验收手册.md`](../XinMatch-DataBase/docs/构建与验收手册.md) for
  the build/validate/acceptance commands.

## Design principles

1. **Clean-room**: no disassembly or decompilation of proprietary software.
   Specifications come from official documentation + published algorithms +
   black-box file-format observation for interoperability.
2. **Kernel / GUI decoupled**: everything in `xinmatch/core/` is pure
   computation (numpy arrays + dataclasses), unit-testable without a display.
   The GUI in `xinmatch/ui/` is a thin layer on top.
3. **Open data first**: the reference database is built from the
   [COD](https://www.crystallography.net/cod/) (CC0) public dump.
4. **Small, verifiable steps**: every task ships with pytest acceptance
   criteria so an AI agent can build, test, and debug independently.

## Project layout

```
xinmatch/
├── core/            # pure computation kernel (no GUI)
│   ├── model/       # Pattern, Peak, Entry, Phase, Restraints, Project
│   ├── io/          # 33 diffraction formats + CIF + exporters
│   ├── preprocess/  # smoothing, background, Kα2, zero point, ...
│   ├── peak/        # peak search, profile fitting, shapes
│   ├── db/          # SQLite reference database (COD) + user DB
│   ├── search/      # FoM search-match, PFSM, restraints
│   ├── index/       # Treor / Dicvol indexing
│   ├── refine/      # Le Bail / Rietveld (delegated to GSAS-II)
│   ├── quant/       # RIR, internal standard, Rietveld quant
│   ├── micro/       # crystallite size, microstrain, DOC
│   └── report/      # report data model + rendering
├── ui/              # PySide6 GUI
├── cli/             # command-line / batch interface
├── utils/           # registration + build variant (stdlib only, no Qt)
tests/               # pytest suite + fixtures + reference baseline
docs/                # analysis docs (reference help retained externally)
tools/               # helper scripts (doc extraction, baseline building)
```

## Getting started

```powershell
# (optional) create a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# install in editable mode with dev + gui extras
pip install -e ".[dev,gui]"

# run the test suite (fast subset; the ``slow`` marker is excluded by default)
pytest

# include the numerically heavy suite (turn-on least squares, GSAS-II
# subprocesses, L3 acceptance curve_fit) — tens of minutes
pytest -m slow

# full local CI (ruff + mypy + tests), mirrors .github/workflows/ci.yml
powershell -File tools/ci.ps1
```

> The reference libraries (`*.xinDB`, ~110 MB–1.7 GB) are not in the repository;
> the source checkout resolves them from `../XinMatch-DataBase/data`
> (`XINMATCH_XINDB_DIR` overrides).  Tests that need them skip themselves.

### Run the working tree without building / 免打包直接运行

`run_dev.bat` starts the code in the working tree in place — no PyInstaller
build and no install step, so what you see is always the latest source.
Without arguments it opens the GUI; any other arguments are forwarded to the
CLI (`python -m xinmatch.cli.main`):

```bat
run_dev.bat                                  :: GUI
run_dev.bat search pat.txt --db ..\XinMatch-DataBase\data\COD-Inorg-20261020.xinDB --top-n 5 --json
run_dev.bat libraries --json                 :: list available .xinDB libraries
```

The interpreter is resolved in this order and echoed on startup:
`%XINMATCH_DEV_PYTHON%` → `.venv\Scripts\python.exe` →
`venv\Scripts\python.exe` → `D:\Project\XRD\python310\python.exe` →
`python` on `PATH`. Because the batch file `cd`s to the repository root,
`python -m` loads the local `xinmatch/` package even when a different
copy is installed in site-packages.

## Builds & registration / 构建版本与注册

v1.7.0 起同时产出两个二进制。**v3.0.0 起两个版本都内置默认库** `COD-Inorg-<snapshot>.xinDB`
（解压/安装即可检索；位置 `<程序目录>\data\`，可自行替换或再挂载其他 `.xinDB`）：

| 构建 | 产物 | 注册机制 | 状态栏最右端 |
|---|---|---|---|
| **正式版**（release） | `XinMatch-Setup-<v>.exe`（安装时可选择安装位置） | **有**：每次启动检查注册状态 | `已注册：<单位部门名称>` / `未注册` |
| **内部评估版**（internal） | `XinMatch-Internal-<v>.zip`（免安装，自用） | **无** | **红色加粗** `内部评估版本` |

**v3.0.0 发布产物**（[Release v3.0.0](https://github.com/PolyXRD/XinMatch/releases/tag/v3.0.0)）：

| 附件 | 体积 | SHA-256（前 16 位） |
|---|---|---|
| `XinMatch-Setup-3.0.0.exe`（正式版安装包，内置 COD-Inorg 库） | 244.5 MiB | `de567ddbbb8cafed…` |
| `XinMatch-Internal-3.0.0.zip`（便携包 = 内部评估版，红字标识，内置 COD-Inorg 库） | 340.0 MiB | `b252249956477d16…` |
| `XinMatch-Databases-COD-Inorg-3.0.0.zip`（COD 无机物库独立包 `*.xinDB`） | 86.9 MiB | `9c1f6f982033634f…` |
| `SHA256SUMS.txt` | — | — |

正式版未注册时，每次启动弹出提示：

> 本软件未注册，版权所有，禁止用于商业用途。
> 如需注册请联系 sshztx@outlook.com

点「**确定**」关闭提示、软件照常使用（下次启动仍会提示）；点「**输入注册码**」粘贴注册码，
校验通过后即完成注册，此后不再提示。也可随时通过 **帮助 → 输入注册码(&R)…** 注册。

注册码由开发方根据用户提供的「单位部门名称」生成：`PXRD1-XXXX-XXXX-…`（Base32 载荷
`UTF8(单位名) + HMAC-SHA256[:8]`），软件端重新校验并可还原单位名用于状态栏展示；
无需联网、无需机器码，同一单位可在多台电脑使用。算法与 PolyXRD 家族统一
（复用 `D:\Project\XRD\PolyXRD-Reg`，本仓副本 `xinmatch/utils/registration.py`）。

## License / 授权许可

本软件采用**双许可**模式（学术许可 + 商业许可），与上游 PolyXRD 项目一致。
This software is distributed under a **dual license** (Academic + Commercial), consistent with the upstream PolyXRD project.

- **English（英文）**: [LICENSE](LICENSE)
- **中文（简体）**: [LICENSE-CN](LICENSE-CN)

学术用途可依据【学术许可】免费使用；任何商业用途须事先联系版权持有人取得独立书面【商业授权】（详见许可证正文）。
Academic use is free under the Academic License; any commercial use requires a separate written Commercial License from the copyright holder (see license text).
