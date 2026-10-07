"""Indexing engine (Phase 9 / T9.1-T9.4).

GUI-free implementation of Match!'s *Tools → Indexing* command
(``docs/indexing.md``).  Given a set of experimental peak d-spacings,
the engine derives candidate unit-cell parameters and Miller indices
for each peak by either trial-and-error (Treor) or successive
dichotomy (Dicvol), then ranks and de-duplicates the candidate
solutions by figure-of-merit (de Wolff M(20) or Smith-Snyder F_N).

Submodules
----------
lattice
    d-spacing formulas for the 7 crystal systems + the
    :class:`LatticeSolution` carrier dataclass.
treor
    Treor90-style trial-and-error indexing (Werner 1964, 1985).
dicvol
    Dicvol06-style successive-dichotomy indexing (Boultif & Louër
    2004).
solutions
    Solution ranking, deduplication and figure-of-merit computation.
"""

from .dicvol import index_dicvol
from .lattice import (
    CRYSTAL_SYSTEMS,
    LatticeSolution,
    cell_volume,
    compute_d,
    compute_d_cubic,
    compute_d_for_system,
    compute_d_hexagonal,
    compute_d_orthorhombic,
    compute_d_tetragonal,
    d_to_reciprocal_lattice,
    reciprocal_cell,
    solve_reciprocal_lattice,
)
from .solutions import (
    deduplicate,
    rank_solutions,
    smith_snyder_fom,
    wolff_fom,
)
from .treor import index_treor

__all__ = [
    # lattice
    "CRYSTAL_SYSTEMS",
    "LatticeSolution",
    "cell_volume",
    "compute_d",
    "compute_d_cubic",
    "compute_d_for_system",
    "compute_d_hexagonal",
    "compute_d_orthorhombic",
    "compute_d_tetragonal",
    "d_to_reciprocal_lattice",
    "reciprocal_cell",
    "solve_reciprocal_lattice",
    # treor
    "index_treor",
    # dicvol
    "index_dicvol",
    # solutions
    "rank_solutions",
    "deduplicate",
    "smith_snyder_fom",
    "wolff_fom",
]
