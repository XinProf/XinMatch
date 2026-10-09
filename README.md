# XinMatch

Open-source **powder X-ray diffraction (XRPD) phase analysis** platform — a
clean-room implementation guided by publicly documented XRD phase-analysis
workflows, published algorithms and open reference data (COD).

> ⚠️ **Pre-alpha.** The project is in the skeleton + planning stage. See
> [ROADMAP_v3.md](ROADMAP_v3.md) for the full implementation plan and
> [docs/STATUS.md](docs/STATUS.md) for current progress.

## What XinMatch does

- **Qualitative phase analysis** (search-match): identify crystalline phases
  from an experimental powder diffraction pattern against a reference database.
- **Quantitative phase analysis** (RIR, internal standard, Rietveld).
- **Raw data preprocessing**: smoothing, background subtraction, Kα₂ stripping,
  zero-point / displacement correction.
- **Profile fitting & peak search**.
- **Rietveld / Le Bail refinement** (via GSAS-II / FullProf adapters).
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
│   ├── refine/      # Le Bail / Rietveld (+ GSAS-II, FullProf adapters)
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

## License

MIT — see [LICENSE](LICENSE).
