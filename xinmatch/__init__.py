"""XinMatch — Open-source powder XRD phase analysis platform.

Clean-room reimplementation of Match!-style workflows using publicly documented
algorithms and open reference data (COD). No reverse engineering of proprietary
software is performed; see docs/00_TECH_STACK_ANALYSIS.md for the compliance
boundary.

The package is split into:

- :mod:`xinmatch.core` — pure computation kernel (no GUI dependency)
- :mod:`xinmatch.ui`   — PySide6 graphical interface
- :mod:`xinmatch.cli`  — command-line / batch interface
"""

__version__ = "0.1.0"
