# XinMatch

Open-source **powder X-ray diffraction (XRPD) phase analysis** platform — a
clean-room implementation guided by publicly documented XRD phase-analysis
workflows, published algorithms and open reference data (COD).

> ✅ **v1.4.0.** Core computation kernel + full GUI + dual-mode search-match
> (peak-list FoM / SMPF full-profile fitting) + GSAS-II refinement pipeline +
> quantitative Rietveld (main-phase wt% < 3 on certified samples) are complete
> and packaged (Windows onedir). See [ROADMAP_v3.md](ROADMAP_v3.md)
> for the full implementation plan and [docs/STATUS.md](docs/STATUS.md) for
> current progress.

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

# run the test suite
pytest
```

## Compliance

XinMatch is **not** a fork of, and contains no code or proprietary database
files from, any commercial powder XRD analysis software. See [docs/00_TECH_STACK_ANALYSIS.md](docs/00_TECH_STACK_ANALYSIS.md)
for the detailed compliance boundary.

## License / 授权许可

本软件采用**双许可**模式（学术许可 + 商业许可），与上游 PolyXRD 项目一致。
This software is distributed under a **dual license** (Academic + Commercial), consistent with the upstream PolyXRD project.

- **English（英文）**: [LICENSE](LICENSE)
- **中文（简体）**: [LICENSE-CN](LICENSE-CN)

学术用途可依据【学术许可】免费使用；任何商业用途须事先联系版权持有人取得独立书面【商业授权】（详见许可证正文）。
Academic use is free under the Academic License; any commercial use requires a separate written Commercial License from the copyright holder (see license text).
