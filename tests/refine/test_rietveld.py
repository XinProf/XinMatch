"""Tests for the Rietveld refinement skeleton (T10.4)."""

import math

import numpy as np

from xinmatch.core.index.lattice import compute_d
from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.pattern import Pattern
from xinmatch.core.refine.peak_model import PeakModel
from xinmatch.core.refine.rietveld import RietveldRefinement, RietveldResult
from xinmatch.core.refine.structure_factor import Atom, multiplicity, structure_factor

_WAVELENGTH = 1.5406  # Cu Kα1


def _two_theta(d: float) -> float:
    sin_theta = min(max(_WAVELENGTH / (2.0 * d), -1.0), 1.0)
    return math.degrees(2.0 * math.asin(sin_theta))


def _generate_hkl(cell: CellParams, tth_max: float) -> list[tuple[int, int, int]]:
    d_min = _WAVELENGTH / (2.0 * math.sin(math.radians(tth_max) / 2.0))
    hkls: list[tuple[int, int, int]] = []
    for h in range(-15, 16):
        for k in range(-15, 16):
            for ll in range(-15, 16):
                if h == 0 and k == 0 and ll == 0:
                    continue
                if (h, k, ll) > (-h, -k, -ll):
                    continue
                try:
                    d = compute_d((h, k, ll), cell)
                except ValueError:
                    continue
                if d >= d_min:
                    hkls.append((h, k, ll))
    return hkls


def _pattern_from_structure(
    cell: CellParams,
    atoms: list[Atom],
    peak_model: PeakModel,
    scale: float = 1.0,
    tth_range: tuple[float, float] = (10.0, 100.0),
    step: float = 0.02,
) -> Pattern:
    """Build a noiseless pattern from a known crystal structure."""
    tth = np.arange(tth_range[0], tth_range[1] + step, step)
    y = np.zeros_like(tth)
    for hkl in _generate_hkl(cell, tth_range[1]):
        d = compute_d(hkl, cell)
        pos = _two_theta(d)
        if pos < tth_range[0] or pos > tth_range[1]:
            continue
        f = structure_factor(hkl, atoms, cell, wavelength=_WAVELENGTH)
        f_sq = float((f * f.conjugate()).real)
        lp = (1.0 + math.cos(math.radians(2.0 * pos)) ** 2) / (
            math.sin(math.radians(pos / 2.0)) * math.cos(math.radians(pos / 2.0)) + 1e-12
        )
        m = multiplicity(hkl, "cubic")
        intensity = scale * f_sq * m * lp
        if intensity <= 0:
            continue
        fwhm = peak_model.fwhm(pos)
        y += intensity * peak_model.shape_function(tth, pos, fwhm, 1.0)
    return Pattern(two_theta=tth, intensity=y, wavelength=_WAVELENGTH, step=step)


# ---------------------------------------------------------------------------
# Tests with atomic coordinates (structure-factor path)
# ---------------------------------------------------------------------------
def test_rietveld_silicon_rwp_below_8():
    """Si diamond-cubic pattern refined from atomic coords: Rwp < 8%."""
    cell = CellParams(5.431, 5.431, 5.431)
    atoms = [Atom("Si", 0, 0, 0), Atom("Si", 0.25, 0.25, 0.25)]
    pm = PeakModel(eta=0.5, asymmetry=0.0, caglioti_uvw=(0.0, 0.0, 0.01))
    pattern = _pattern_from_structure(cell, atoms, pm, scale=100.0, tth_range=(10.0, 100.0))

    # Build an Entry carrying the atoms (Entry has no atoms field natively).
    entry = Entry(
        entry_id="Si-test",
        formula="Si2",
        d_spacings=np.array([5.431 / np.sqrt(3)]),
        intensities=np.array([1.0]),
        cell=cell,
    )
    entry.atoms = atoms  # type: ignore[attr-defined]

    refiner = RietveldRefinement(pattern, entry, pm, wavelength=_WAVELENGTH)
    result = refiner.fit(n_iter=30)

    assert isinstance(result, RietveldResult)
    assert result.rwp < 0.08, f"Rwp = {result.rwp:.4f} (expected < 0.08)"
    assert result.rp < 0.08
    assert result.chi2 > 0.0
    # Refined cell should be close to the true cell.
    assert abs(result.cell.a - 5.431) < 0.05


def test_rietveld_compute_rwp_rp_chi2_methods():
    """compute_rwp / rp / chi2 return finite positive values."""
    cell = CellParams(5.431, 5.431, 5.431)
    atoms = [Atom("Si", 0, 0, 0), Atom("Si", 0.25, 0.25, 0.25)]
    pm = PeakModel(caglioti_uvw=(0.0, 0.0, 0.01))
    pattern = _pattern_from_structure(cell, atoms, pm, scale=50.0, tth_range=(20.0, 90.0))
    entry = Entry(
        entry_id="x", formula="Si", d_spacings=np.array([1.0]),
        intensities=np.array([1.0]), cell=cell,
    )
    entry.atoms = atoms  # type: ignore[attr-defined]
    refiner = RietveldRefinement(pattern, entry, pm, wavelength=_WAVELENGTH)

    assert math.isfinite(refiner.compute_rwp())
    assert refiner.compute_rwp() > 0.0
    assert math.isfinite(refiner.compute_rp())
    assert refiner.compute_rp() > 0.0
    assert math.isfinite(refiner.compute_chi2())


# ---------------------------------------------------------------------------
# Tests with tabulated intensities (no atoms)
# ---------------------------------------------------------------------------
def test_rietveld_tabulated_intensities_rwp_below_8():
    """Rietveld using tabulated d/I (no atoms) also fits well."""
    cell = CellParams(5.431, 5.431, 5.431)
    pm = PeakModel(eta=0.5, asymmetry=0.0, caglioti_uvw=(0.0, 0.0, 0.01))

    # Build a pattern from a known set of tabulated reflections so the
    # refiner sees exactly the peaks it is told about.
    hkl_list = [(1, 1, 1), (2, 2, 0), (3, 1, 1), (4, 0, 0), (3, 3, 1), (4, 2, 2)]
    rel_intensities = np.array([1.0, 0.6, 0.4, 0.3, 0.25, 0.2])
    d_spacings = np.array([compute_d(h, cell) for h in hkl_list])

    tth = np.arange(10.0, 100.0 + 0.02, 0.02)
    y = np.zeros_like(tth)
    for hkl, rel_i in zip(hkl_list, rel_intensities, strict=True):
        d = compute_d(hkl, cell)
        pos = _two_theta(d)
        # Tabulated intensities are peak areas (already include multiplicity).
        intensity = 1000.0 * rel_i
        fwhm = pm.fwhm(pos)
        y += intensity * pm.shape_function(tth, pos, fwhm, 1.0)
    pattern = Pattern(two_theta=tth, intensity=y, wavelength=_WAVELENGTH, step=0.02)

    entry = Entry(
        entry_id="Si-tab",
        formula="Si",
        d_spacings=d_spacings,
        intensities=rel_intensities,
        cell=cell,
        hkl=hkl_list,
    )

    refiner = RietveldRefinement(pattern, entry, pm, wavelength=_WAVELENGTH)
    result = refiner.fit(n_iter=30)
    assert result.rwp < 0.08, f"Rwp = {result.rwp:.4f}"


def test_rietveld_result_fitted_pattern_matches_grid():
    cell = CellParams(5.431, 5.431, 5.431)
    atoms = [Atom("Si", 0, 0, 0), Atom("Si", 0.25, 0.25, 0.25)]
    pm = PeakModel(caglioti_uvw=(0.0, 0.0, 0.01))
    pattern = _pattern_from_structure(cell, atoms, pm, scale=50.0, tth_range=(20.0, 90.0))
    entry = Entry(
        entry_id="x", formula="Si", d_spacings=np.array([1.0]),
        intensities=np.array([1.0]), cell=cell,
    )
    entry.atoms = atoms  # type: ignore[attr-defined]
    refiner = RietveldRefinement(pattern, entry, pm, wavelength=_WAVELENGTH)
    result = refiner.fit(n_iter=10)

    assert len(result.fitted_pattern) == len(pattern)
    np.testing.assert_allclose(result.fitted_pattern.two_theta, pattern.two_theta)
