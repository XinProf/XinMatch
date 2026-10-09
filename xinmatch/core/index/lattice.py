"""Crystallographic d-spacing formulas and indexing data structures (T9.1).

Implements the closed-form d-spacing formulas for the seven crystal
systems, the reciprocal-lattice conversion, and the
:class:`LatticeSolution` dataclass that is the standard carrier for a
candidate indexing result throughout the indexing engine.

These are the building blocks used by :mod:`xinmatch.core.index.treor`
and :mod:`xinmatch.core.index.dicvol`.  The d-spacing formulas are the
textbook conventions (e.g. International Tables for Crystallography A,
``Kluwer 2006``); the metric-tensor approach used here reduces to the
familiar closed forms for the high-symmetry systems (cubic, tetragonal,
orthorhombic, hexagonal) and handles the general triclinic case as the
fallback.  See Werner (1985) §2 and Boultif & Louër (2004) §2 for the
context in which these formulas are used by the indexing programs.

References
----------
* International Tables for Crystallography Vol. A (2006), §2.1.
* P.-E. Werner, L. Eriksson, M. Westdahl, "Treor", J. Appl. Cryst. 18
  (1985), 367-370.
* A. Boultif, D. Louër, J. Appl. Cryst. 37 (2004), 724-731.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from xinmatch.core.model.entry import CellParams

# All seven crystal systems supported by the d-spacing engine.
CRYSTAL_SYSTEMS: tuple[str, ...] = (
    "triclinic",
    "monoclinic",
    "orthorhombic",
    "tetragonal",
    "trigonal",
    "hexagonal",
    "cubic",
)

_DEG2RAD: float = math.pi / 180.0


def _validate_crystal_system(name: str) -> None:
    """Raise ``ValueError`` if *name* is not a supported crystal system."""
    if name not in CRYSTAL_SYSTEMS:
        raise ValueError(
            f"unknown crystal system {name!r}; expected one of {CRYSTAL_SYSTEMS}"
        )


def _rad(deg: float) -> float:
    return deg * _DEG2RAD


# --------------------------------------------------------------------- #
# Cell volume + reciprocal cell
# --------------------------------------------------------------------- #


def cell_volume(cell: CellParams) -> float:
    """Compute the unit-cell volume in Å³.

    Uses the general triclinic metric formula::

        V = a·b·c · √(1 − cos²α − cos²β − cos²γ + 2·cosα·cosβ·cosγ)

    which reduces to the textbook ``a·b·c`` for orthorhombic and higher
    symmetries.  Raises ``ValueError`` for degenerate (non-physical)
    cells whose squared volume is non-positive.
    """
    alpha, beta, gamma = _rad(cell.alpha), _rad(cell.beta), _rad(cell.gamma)
    ca, cb, cg = math.cos(alpha), math.cos(beta), math.cos(gamma)
    vol_sq = 1.0 - ca * ca - cb * cb - cg * cg + 2.0 * ca * cb * cg
    if vol_sq <= 0.0:
        raise ValueError(
            f"degenerate unit cell — volume² = {vol_sq:.6g} ≤ 0; "
            f"check angles (α, β, γ) = {cell.alpha}, {cell.beta}, {cell.gamma}"
        )
    return cell.a * cell.b * cell.c * math.sqrt(vol_sq)


def reciprocal_cell(cell: CellParams) -> tuple[float, float, float, float, float, float]:
    """Compute the reciprocal cell parameters ``(a*, b*, c*, α*, β*, γ*)``.

    Returns the three reciprocal axes in Å⁻¹ and the three reciprocal
    angles in degrees.  Derived from the standard direct→reciprocal
    relations (e.g. International Tables A §2.1):

    .. math::

        a^* = \\frac{b\\,c\\,\\sin\\alpha}{V},
        \\quad b^* = \\frac{c\\,a\\,\\sin\\beta}{V},
        \\quad c^* = \\frac{a\\,b\\,\\sin\\gamma}{V}

        \\cos\\alpha^* = \\frac{\\cos\\beta\\,\\cos\\gamma - \\cos\\alpha}
                                {\\sin\\beta\\,\\sin\\gamma}, \\;\\ldots
    """
    alpha, beta, gamma = _rad(cell.alpha), _rad(cell.beta), _rad(cell.gamma)
    ca, cb, cg = math.cos(alpha), math.cos(beta), math.cos(gamma)
    sa, sb, sg = math.sin(alpha), math.sin(beta), math.sin(gamma)
    if min(sa, sb, sg) <= 0.0:
        raise ValueError(
            f"degenerate unit cell — sin(α/β/γ) ≤ 0; "
            f"angles = {cell.alpha}, {cell.beta}, {cell.gamma}"
        )
    vol = cell_volume(cell)
    a_star = cell.b * cell.c * sa / vol
    b_star = cell.c * cell.a * sb / vol
    c_star = cell.a * cell.b * sg / vol

    cos_alpha_star = (cb * cg - ca) / (sb * sg)
    cos_beta_star = (cg * ca - cb) / (sg * sa)
    cos_gamma_star = (ca * cb - cg) / (sa * sb)

    def _acos_clamped(x: float) -> float:
        return math.degrees(math.acos(max(-1.0, min(1.0, x))))

    return (
        a_star,
        b_star,
        c_star,
        _acos_clamped(cos_alpha_star),
        _acos_clamped(cos_beta_star),
        _acos_clamped(cos_gamma_star),
    )


# --------------------------------------------------------------------- #
# d-spacing computation
# --------------------------------------------------------------------- #


def compute_d(hkl: tuple[int, int, int], cell: CellParams) -> float:
    """Compute the d-spacing for the given Miller indices and unit cell.

    Uses the general metric-tensor formula

    .. math::

        \\frac{1}{d^2} = h^2 a^{*2} + k^2 b^{*2} + l^2 c^{*2}
            + 2 h k\\, a^* b^* \\cos\\gamma^*
            + 2 k l\\, b^* c^* \\cos\\alpha^*
            + 2 l h\\, c^* a^* \\cos\\beta^*

    which is exact for all 7 crystal systems.  For high-symmetry systems
    the result reduces to the familiar closed forms; for performance the
    closed-form helpers :func:`compute_d_cubic`,
    :func:`compute_d_tetragonal`, :func:`compute_d_orthorhombic`,
    :func:`compute_d_hexagonal` are exposed below and used internally
    by the indexing engines whenever the symmetry permits.
    """
    a_star, b_star, c_star, alpha_s, beta_s, gamma_s = reciprocal_cell(cell)
    hh, kk, ll = hkl
    cos_a_s = math.cos(_rad(alpha_s))
    cos_b_s = math.cos(_rad(beta_s))
    cos_g_s = math.cos(_rad(gamma_s))

    inv_d_sq = (
        hh * hh * a_star * a_star
        + kk * kk * b_star * b_star
        + ll * ll * c_star * c_star
        + 2.0 * hh * kk * a_star * b_star * cos_g_s
        + 2.0 * kk * ll * b_star * c_star * cos_a_s
        + 2.0 * ll * hh * c_star * a_star * cos_b_s
    )
    if inv_d_sq <= 0.0:
        raise ValueError(
            f"non-positive 1/d² = {inv_d_sq} for hkl={hkl}, cell={cell!r}"
        )
    return 1.0 / math.sqrt(inv_d_sq)


def compute_d_cubic(hkl: tuple[int, int, int], a: float) -> float:
    """Cubic d-spacing: ``d = a / √(h² + k² + l²)``."""
    hh, kk, ll = hkl
    n2 = hh * hh + kk * kk + ll * ll
    if n2 == 0:
        raise ValueError("hkl = (0,0,0) is not a valid reflection")
    return a / math.sqrt(n2)


def compute_d_tetragonal(hkl: tuple[int, int, int], a: float, c: float) -> float:
    """Tetragonal d-spacing: ``1/d² = (h² + k²)/a² + l²/c²``."""
    hh, kk, ll = hkl
    inv = (hh * hh + kk * kk) / (a * a) + (ll * ll) / (c * c)
    if inv <= 0.0:
        raise ValueError("hkl has zero magnitude in ab-plane and l=0")
    return 1.0 / math.sqrt(inv)


def compute_d_orthorhombic(
    hkl: tuple[int, int, int], a: float, b: float, c: float
) -> float:
    """Orthorhombic d-spacing: ``1/d² = h²/a² + k²/b² + l²/c²``."""
    hh, kk, ll = hkl
    inv = (hh * hh) / (a * a) + (kk * kk) / (b * b) + (ll * ll) / (c * c)
    if inv <= 0.0:
        raise ValueError("hkl = (0,0,0) is not a valid reflection")
    return 1.0 / math.sqrt(inv)


def compute_d_hexagonal(hkl: tuple[int, int, int], a: float, c: float) -> float:
    """Hexagonal d-spacing (4-axis Miller-Bravais ``(h, k, l)`` reduced
    to the 3-index form): ``1/d² = (4/3)(h² + hk + k²)/a² + l²/c²``."""
    hh, kk, ll = hkl
    inv = (4.0 / 3.0) * (hh * hh + hh * kk + kk * kk) / (a * a) + (ll * ll) / (c * c)
    if inv <= 0.0:
        raise ValueError("hkl has zero magnitude in basal plane and l=0")
    return 1.0 / math.sqrt(inv)


def compute_d_for_system(
    hkl: tuple[int, int, int], cell: CellParams, crystal_system: str
) -> float:
    """Dispatch to the closed-form d-spacing formula for *crystal_system*.

    Falls back to the general metric-tensor formula
    :func:`compute_d` for monoclinic, trigonal and triclinic.
    """
    _validate_crystal_system(crystal_system)
    if crystal_system == "cubic":
        return compute_d_cubic(hkl, cell.a)
    if crystal_system == "tetragonal":
        return compute_d_tetragonal(hkl, cell.a, cell.c)
    if crystal_system == "orthorhombic":
        return compute_d_orthorhombic(hkl, cell.a, cell.b, cell.c)
    if crystal_system == "hexagonal":
        return compute_d_hexagonal(hkl, cell.a, cell.c)
    return compute_d(hkl, cell)


# --------------------------------------------------------------------- #
# d → reciprocal lattice (single-peak inversion)
# --------------------------------------------------------------------- #


def d_to_reciprocal_lattice(
    d: float, hkl: tuple[int, int, int], crystal_system: str
) -> tuple[float, ...]:
    """Solve for the reciprocal-cell parameters that can be **fully**
    determined from a single ``(d, hkl)`` pair under the symmetry of
    *crystal_system*.

    Returns a tuple of reciprocal axes (in Å⁻¹) — **not** all six
    reciprocal-cell parameters, only those uniquely determined by this
    one peak.  Cases:

    ============  ====================  =================
    system        condition             returns
    ============  ====================  =================
    cubic         any (hkl) ≠ (0,0,0)   ``(a*,)``
    tetragonal    l = 0                 ``(a*,)``
    tetragonal    h = k = 0             ``(c*,)``
    hexagonal     l = 0                 ``(a*,)``
    hexagonal     h = k = 0             ``(c*,)``
    orthorhombic  axis-aligned          ``(a*,)``/``(b*,)``/``(c*,)``
    others        —                     raises
    ============  ====================  =================

    The Treor engine uses this routine to obtain initial estimates of
    the reciprocal axes from the assumed low-index base lines (Werner
    1985 §3.1).

    Parameters
    ----------
    d:
        Measured d-spacing in Å.
    hkl:
        Miller indices ``(h, k, l)`` assigned to this peak.
    crystal_system:
        One of :data:`CRYSTAL_SYSTEMS`.

    Returns
    -------
    tuple[float, ...]
        Reciprocal-cell parameter(s) in Å⁻¹ (length depends on the
        solvable quantity as listed above).

    Raises
    ------
    ValueError
        If *d* is non-positive, *crystal_system* is unknown, or the
        ``(hkl)`` is such that no unique reciprocal-cell parameter can be
        obtained from a single peak for that symmetry (e.g. tetragonal
        with both ``(h,k) ≠ 0`` and ``l ≠ 0``).
    """
    _validate_crystal_system(crystal_system)
    if d <= 0.0:
        raise ValueError(f"d-spacing must be positive, got {d}")
    hh, kk, ll = hkl

    if crystal_system == "cubic":
        n2 = hh * hh + kk * kk + ll * ll
        if n2 == 0:
            raise ValueError("hkl=(0,0,0) is invalid")
        # 1/d² = N²/a² → a = N·d → a* = 1/(N·d)
        return (1.0 / (math.sqrt(n2) * d),)

    if crystal_system in ("tetragonal", "hexagonal"):
        if hh == 0 and kk == 0:
            if ll == 0:
                raise ValueError("hkl=(0,0,0) is invalid")
            # 1/d² = l²/c² → c = |l|·d → c* = 1/(|l|·d)
            return (1.0 / (abs(ll) * d),)
        if ll == 0:
            if crystal_system == "tetragonal":
                # 1/d² = (h²+k²)/a² → a = sqrt(h²+k²)·d → a* = 1/(sqrt(h²+k²)·d)
                return (1.0 / (math.sqrt(hh * hh + kk * kk) * d),)
            # hexagonal: 1/d² = (4/3)(h²+hk+k²)/a²
            # → a = (2/sqrt(3))·sqrt(h²+hk+k²)·d → a* = sqrt(3)/(2·sqrt(h²+hk+k²)·d)
            n_ab = hh * hh + hh * kk + kk * kk
            if n_ab == 0:
                raise ValueError("hkl has zero magnitude in basal plane")
            return (math.sqrt(3.0) / (2.0 * math.sqrt(n_ab) * d),)
        raise ValueError(
            "tetragonal/hexagonal with both (h,k)≠0 and l≠0 cannot be "
            "solved from a single (d, hkl) pair; use a list of peaks"
        )

    if crystal_system == "orthorhombic":
        if hh != 0 and kk == 0 and ll == 0:
            # 1/d² = h²/a² → a = |h|·d → a* = 1/(|h|·d)
            return (1.0 / (abs(hh) * d),)
        if kk != 0 and hh == 0 and ll == 0:
            return (1.0 / (abs(kk) * d),)
        if ll != 0 and hh == 0 and kk == 0:
            return (1.0 / (abs(ll) * d),)
        raise ValueError(
            "orthorhombic single-peak inversion requires axis-aligned hkl "
            "(h,0,0)/(0,k,0)/(0,0,l)"
        )

    raise ValueError(
        f"single-peak reciprocal-cell inversion is not implemented for "
        f"crystal system {crystal_system!r}; use solve_reciprocal_lattice"
    )


def solve_reciprocal_lattice(
    peaks_d: list[float],
    hkl_list: list[tuple[int, int, int]],
    crystal_system: str,
) -> tuple[float, ...]:
    """Least-squares solve for reciprocal-cell parameters from a list of
    ``(d, hkl)`` assignments under the symmetry of *crystal_system*.

    The unknown parameter sets per crystal system are:

    * cubic — ``(a*,)`` (1 unknown)
    * tetragonal / hexagonal — ``(a*, c*)`` (2 unknowns)
    * orthorhombic — ``(a*, b*, c*)`` (3 unknowns)

    Monoclinic / trigonal / triclinic are out of scope for the
    simplified indexing engine and raise ``NotImplementedError``.

    Parameters
    ----------
    peaks_d:
        Observed d-spacings in Å.
    hkl_list:
        Miller indices assigned to each peak (same length as *peaks_d*).
    crystal_system:
        One of :data:`CRYSTAL_SYSTEMS`.

    Returns
    -------
    tuple[float, ...]
        Best-fit reciprocal-cell parameters in Å⁻¹.  Length matches the
        number of unknowns for the requested symmetry.

    Raises
    ------
    ValueError
        For length mismatch, unsupported crystal system, or
        under-determined systems (fewer peaks than unknowns).
    """
    _validate_crystal_system(crystal_system)
    if len(peaks_d) != len(hkl_list):
        raise ValueError(
            f"peaks_d and hkl_list must have the same length: "
            f"{len(peaks_d)} vs {len(hkl_list)}"
        )

    if crystal_system == "cubic":
        # Model: 1/d² = N²·a*² where N² = h²+k²+l².
        # Linear LSQ: a*² = Σ(N²·(1/d²)) / Σ(N⁴) = Σ(N²/d²) / Σ(N⁴)
        num, den = 0.0, 0.0
        for d, (hh, kk, ll) in zip(peaks_d, hkl_list, strict=True):
            n2 = hh * hh + kk * kk + ll * ll
            if n2 == 0 or d <= 0:
                raise ValueError("invalid (d, hkl) pair in input")
            num += n2 / (d * d)  # Σ(N²·(1/d²))
            den += n2 * n2       # Σ(N⁴)
        if den <= 0.0:
            raise ValueError("degenerate LSQ — all N²=0?")
        a_star_sq = num / den
        if a_star_sq <= 0.0:
            raise ValueError(f"non-positive a*² = {a_star_sq}")
        return (math.sqrt(a_star_sq),)

    if crystal_system in ("tetragonal", "hexagonal"):
        # 1/d² = X · a*² + Y · c*²
        # where X = h²+k² (tetr) or (4/3)(h²+hk+k²) (hex),
        #       Y = l²
        # Solve LSQ for (a*², c*²) from the linear system.
        def _x_term(h: int, k: int) -> float:
            if crystal_system == "tetragonal":
                return float(h * h + k * k)
            return (4.0 / 3.0) * (h * h + h * k + k * k)

        # Normal equations: [ΣX²  ΣX·Y ; ΣX·Y  ΣY²] · [a*²; c*²] = [ΣX·inv_d²; ΣY·inv_d²]
        sxx = sxy = syy = 0.0
        sx_inv = sy_inv = 0.0
        for d, (hh, kk, ll) in zip(peaks_d, hkl_list, strict=True):
            if d <= 0:
                raise ValueError("non-positive d")
            x = _x_term(hh, kk)
            y = float(ll * ll)
            inv_d2 = 1.0 / (d * d)
            sxx += x * x
            sxy += x * y
            syy += y * y
            sx_inv += x * inv_d2
            sy_inv += y * inv_d2
        det = sxx * syy - sxy * sxy
        if det <= 0.0:
            raise ValueError(
                f"degenerate LSQ (det={det}); need peaks with both "
                f"l=0 and l≠0 (or (h,k)=(0,0))"
            )
        a_star_sq = (syy * sx_inv - sxy * sy_inv) / det
        c_star_sq = (sxx * sy_inv - sxy * sx_inv) / det
        if a_star_sq <= 0.0 or c_star_sq <= 0.0:
            raise ValueError(
                f"non-positive reciprocal axis squared: "
                f"a*²={a_star_sq}, c*²={c_star_sq}"
            )
        return (math.sqrt(a_star_sq), math.sqrt(c_star_sq))

    if crystal_system == "orthorhombic":
        # 1/d² = h²·a*² + k²·b*² + l²·c*²
        # Diagonal system, decouples — LSQ each axis independently.
        sx_a = sx_b = sx_c = 0.0
        sy_a = sy_b = sy_c = 0.0
        for d, (hh, kk, ll) in zip(peaks_d, hkl_list, strict=True):
            if d <= 0:
                raise ValueError("non-positive d")
            inv_d2 = 1.0 / (d * d)
            sx_a += hh * hh
            sy_a += hh * hh * inv_d2
            sx_b += kk * kk
            sy_b += kk * kk * inv_d2
            sx_c += ll * ll
            sy_c += ll * ll * inv_d2
        if min(sx_a, sx_b, sx_c) <= 0.0:
            raise ValueError(
                "orthorhombic LSQ requires peaks with each of (h,k,l)≠0 "
                "represented"
            )
        return (
            math.sqrt(sy_a / sx_a),
            math.sqrt(sy_b / sx_b),
            math.sqrt(sy_c / sx_c),
        )

    raise NotImplementedError(
        f"solve_reciprocal_lattice for {crystal_system!r} is not implemented; "
        f"only cubic/tetragonal/hexagonal/orthorhombic are supported"
    )


# --------------------------------------------------------------------- #
# Candidate-solution dataclass
# --------------------------------------------------------------------- #


@dataclass
class LatticeSolution:
    """A candidate indexing solution (one unit cell + its hkl assignments).

    Used as the standard carrier throughout :mod:`xinmatch.core.index.treor`,
    :mod:`xinmatch.core.index.dicvol` and
    :mod:`xinmatch.core.index.solutions`.  Matches the *solution list*
    row in the reference software's indexing results dialog (``docs/indexing_solutions.md``).

    Attributes
    ----------
    cell:
        Unit cell parameters ``(a, b, c, α, β, γ)``.
    crystal_system:
        Crystal system under which this solution was obtained.
    fom:
        Figure-of-merit (e.g. de Wolff ``M(20)`` or Smith-Snyder ``F_N``).
        Higher is better.
    hkl_assignments:
        Miller indices ``(h, k, l)`` for each input peak, in the same
        order as the input ``peaks_d`` list.  ``None`` entries are
        unindexed peaks.
    n_indexed:
        Number of indexed peaks (number of non-``None`` assignments).
    program:
        Source program name (``"treor"`` or ``"dicvol"``).
    """

    cell: CellParams
    crystal_system: str
    fom: float
    hkl_assignments: list[tuple[int, int, int] | None] = field(default_factory=list)
    n_indexed: int = 0
    program: str = "treor"

    def __post_init__(self) -> None:
        _validate_crystal_system(self.crystal_system)
        # If n_indexed was not supplied, derive it from hkl_assignments
        if self.n_indexed == 0 and self.hkl_assignments:
            self.n_indexed = sum(1 for hkl in self.hkl_assignments if hkl is not None)

    @property
    def n_total(self) -> int:
        """Total number of peaks in the assignment list."""
        return len(self.hkl_assignments)

    @property
    def volume(self) -> float:
        """Unit-cell volume in Å³ (computed via :func:`cell_volume`)."""
        return cell_volume(self.cell)

    @property
    def n_unindexed(self) -> int:
        """Number of peaks not indexed by this solution."""
        return self.n_total - self.n_indexed
