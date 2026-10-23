"""Environment self-check for the v3.0.0 ``.xinDB`` rebuild (M0 / S0.1).

What it checks
--------------
1. **Runtime** — the third-party packages the build and search path need
   (``numpy`` / ``scipy`` / ``gemmi`` / ``lmfit`` / ``pyyaml``) and the
   Python version floor.
2. **CIF sources** — that the two input archives named in the rebuild plan
   exist and how many ``.cif`` files each holds.
3. **Optional inputs** — the old databases that the v3 plan deliberately does
   *not* depend on.  They are reported for reference only; a missing file
   there is not an error.

Usage
-----
::

    python -m tools._env_check
    python -m tools._env_check --cif-root D:\\...\\COD --inorg-root D:\\...\\inorg_cif\\COD

Exit code is ``0`` when every *required* check passes, ``1`` otherwise, so
the script can gate an automated build pipeline.
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
from pathlib import Path

#: Minimum Python the project supports (``pyproject.toml`` targets py310).
MIN_PYTHON = (3, 10)

#: Third-party packages the rebuild path imports, with the reason each is needed.
REQUIRED_PACKAGES: tuple[tuple[str, str], ...] = (
    ("numpy", "columnar packing / vectorised prescreen"),
    ("scipy", "refinement and correlation maths"),
    ("gemmi", "CIF parsing and powder-pattern calculation"),
    ("lmfit", "least-squares refinement"),
    ("yaml", "configuration files (PyYAML)"),
)

#: 共享数据根（2026-10-23 起在仓库外，PolyXRD / XinMatch 两库共用）。
DATA_ROOT = Path(os.environ.get("XRD_DATA_ROOT") or r"D:\Project\XRD\sync-COD")

#: Default COD CIF archive (full library) — the primary v3 build input.
DEFAULT_COD_ROOT = DATA_ROOT / "COD"

#: Default COD CIF archive (inorganic subset) — the default interactive library.
DEFAULT_INORG_ROOT = DATA_ROOT / "inorg_cif" / "COD"

#: Legacy databases the v3 plan does **not** depend on (reported for reference).
LEGACY_REFERENCE_FILES: tuple[Path, ...] = (
    Path(r"D:\Project\XRD\PolyXRD\cod_data\cod_index.sqlite"),
    Path(r"D:\Project\XRD\PolyXRD\cod_data\COD_inorganics.sqlite"),
)


def _check_runtime() -> list[str]:
    """Return a list of human-readable failures (empty = all good)."""
    problems: list[str] = []

    if sys.version_info < MIN_PYTHON:
        problems.append(
            f"Python {platform.python_version()} is older than the required "
            f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
        )

    for module_name, purpose in REQUIRED_PACKAGES:
        try:
            module = __import__(module_name)
        except ImportError:
            problems.append(f"missing package '{module_name}' (needed for {purpose})")
            continue
        version = getattr(module, "__version__", "unknown")
        print(f"  [ok] {module_name:<8} {version:<12} ({purpose})")

    return problems


def _count_cif_files(root: Path) -> int:
    """Count ``*.cif`` files under *root*, skipping the ``dictionaries`` folder.

    The COD archive ships a ``dictionaries/`` folder next to the numbered data
    directories; those files are diffraction dictionaries, not phases, so they
    must never be counted as build inputs.
    """
    if not root.is_dir():
        return -1
    total = 0
    for dirpath, dirnames, filenames in _walk(root):
        dirnames[:] = [d for d in dirnames if d != "dictionaries"]
        total += sum(1 for name in filenames if name.endswith(".cif"))
        del dirpath
    return total


def _walk(root: Path):
    """Yield ``(dirpath, dirnames, filenames)`` without following symlinks."""
    import os

    yield from os.walk(root, followlinks=False)


def _report_sources(cif_root: Path, inorg_root: Path) -> list[str]:
    """Report the CIF input archives; return failures."""
    problems: list[str] = []

    for label, root, expected in (
        ("COD full", cif_root, 535_166),
        ("COD inorg", inorg_root, 79_198),
    ):
        if not root.is_dir():
            problems.append(f"{label} CIF root not found: {root}")
            print(f"  [FAIL] {label:<10} missing: {root}")
            continue
        count = _count_cif_files(root)
        status = "ok" if count == expected else "WARN"
        if count != expected:
            problems.append(
                f"{label} CIF count is {count}, expected {expected} "
                f"(source may have been re-synced)"
            )
        print(
            f"  [{status}] {label:<10} {count:>7} cif   {root}"
        )

    return problems


def _report_legacy(files: tuple[Path, ...]) -> None:
    """Report legacy inputs (reference only — v3 does not use them)."""
    print("  legacy inputs (NOT used by the v3 build, reference only):")
    for path in files:
        if path.is_file():
            size_mb = path.stat().st_size / 1e6
            print(f"    present  {size_mb:>9.1f} MB  {path}")
        else:
            print(f"    absent            --  {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cif-root", type=Path, default=DEFAULT_COD_ROOT)
    parser.add_argument("--inorg-root", type=Path, default=DEFAULT_INORG_ROOT)
    args = parser.parse_args(argv)

    print("== runtime ==")
    print(f"  python   {platform.python_version()}  ({platform.platform()})")
    problems = _check_runtime()

    print("\n== CIF sources ==")
    problems += _report_sources(args.cif_root, args.inorg_root)

    print("\n== legacy inputs ==")
    _report_legacy(LEGACY_REFERENCE_FILES)

    print()
    if problems:
        print(f"FAILED ({len(problems)} problem(s)):")
        for item in problems:
            print(f"  - {item}")
        return 1
    print("OK — environment ready for the v3 .xinDB build.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
