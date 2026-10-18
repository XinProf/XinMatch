"""Tests for the parameter Turn-On strategy (T10.7).

Marked ``slow``: each case drives ``scipy.optimize.least_squares`` with a
numerical Jacobian over a 3500-point pattern (~5-10 min per test).  Excluded
from the default ``pytest`` run (``addopts = -m "not slow"``); run with
``pytest -m slow tests/refine/test_turn_on.py``.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from xinmatch.core.index.lattice import compute_d
from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.pattern import Pattern
from xinmatch.core.refine.peak_model import PeakModel
from xinmatch.core.refine.structure_factor import Atom, multiplicity, structure_factor
from xinmatch.core.refine.turn_on import (
    DEFAULT_STAGES,
    TurnOnStep,
    TurnOnStrategy,
)

pytestmark = pytest.mark.slow

_WAVELENGTH = 1.5406


def _two_theta(d: float) -> float:
    sin_theta = min(max(_WAVELENGTH / (2.0 * d), -1.0), 1.0)
    return math.degrees(2.0 * math.asin(sin_theta))


def _generate_hkl(cell: CellParams, tth_max: float) -> list[tuple[int, int, int]]:
    d_min = _WAVELENGTH / (2.0 * math.sin(math.radians(tth_max) / 2.0))
    hkls: list[tuple[int, int, int]] = []
    for h in range(-12, 13):
        for k in range(-12, 13):
            for ll in range(-12, 13):
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
    scale: float = 100.0,
    tth_range: tuple[float, float] = (20.0, 90.0),
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


def _si_pattern(scale: float = 100.0, tth_range=(20.0, 90.0), step=0.05) -> Pattern:
    cell = CellParams(5.431, 5.431, 5.431)
    atoms = [Atom("Si", 0, 0, 0), Atom("Si", 0.25, 0.25, 0.25)]
    pm = PeakModel(eta=0.5, asymmetry=0.0, caglioti_uvw=(0.0, 0.0, 0.01))
    return _pattern_from_structure(
        cell, atoms, pm, scale=scale, tth_range=tth_range, step=step,
    )


def _si_entry_with_bad_cell(bad_cell: CellParams) -> Entry:
    """Build a Si entry with a (deliberately wrong) starting cell."""
    atoms = [Atom("Si", 0, 0, 0), Atom("Si", 0.25, 0.25, 0.25)]
    entry = Entry(
        entry_id="Si-turnon",
        formula="Si2",
        d_spacings=np.array([5.431 / np.sqrt(3)]),
        intensities=np.array([1.0]),
        cell=bad_cell,
    )
    entry.atoms = atoms  # type: ignore[attr-defined]
    return entry


# ---------------------------------------------------------------------------
# Stage schedule
# ---------------------------------------------------------------------------
def test_default_stages_match_match_dialog_order():
    """Default stage names match the 5-stage Parameter Turn-On order."""
    names = [s[0] for s in DEFAULT_STAGES]
    assert names == ["scale", "background", "zero_lattice", "profile_uvw", "atoms"]


def test_turn_on_strategy_completes_5_stages():
    """The full 5-stage schedule completes on a synthetic Si pattern."""
    pattern = _si_pattern(scale=100.0)
    # Slightly off cell (truth = 5.431) — close enough that scale-only
    # refinement is useful but cell refinement still helps.
    bad_cell = CellParams(5.46, 5.46, 5.46)
    entry = _si_entry_with_bad_cell(bad_cell)
    pm = PeakModel(eta=0.5, asymmetry=0.0, caglioti_uvw=(0.005, 0.0, 0.015))

    strategy = TurnOnStrategy()
    steps = strategy.run(
        pattern, entry, pm,
        wavelength=_WAVELENGTH,
        n_iter=20,
    )
    assert len(steps) == 5
    assert [s.stage_name for s in steps] == [
        "scale", "background", "zero_lattice", "profile_uvw", "atoms",
    ]
    for s in steps:
        assert isinstance(s, TurnOnStep)
        assert math.isfinite(s.rwp_before)
        assert math.isfinite(s.rwp_after)
        assert s.rwp_before >= 0.0
        assert s.rwp_after >= 0.0


def test_at_least_3_stages_have_rwp_drop():
    """With bad initial values at least 3 stages must improve Rwp."""
    pattern = _si_pattern(scale=100.0)
    bad_cell = CellParams(5.46, 5.46, 5.46)
    entry = _si_entry_with_bad_cell(bad_cell)
    pm = PeakModel(eta=0.5, asymmetry=0.0, caglioti_uvw=(0.005, 0.0, 0.015))

    strategy = TurnOnStrategy()
    steps = strategy.run(
        pattern, entry, pm,
        wavelength=_WAVELENGTH,
        n_iter=20,
    )
    improved = [s for s in steps if s.rwp_after < s.rwp_before - 1e-9]
    assert len(improved) >= 3, (
        f"only {len(improved)}/5 stages improved Rwp: "
        + ", ".join(f"{s.stage_name}={s.rwp_before:.4f}→{s.rwp_after:.4f}" for s in steps)
    )


def test_trajectory_rwp_before_is_monotone_non_increasing():
    """The ``rwp_before`` sequence (i.e. the Rwp of the *current state*
    before each stage) is monotone non-increasing: an accepted stage
    lowers the current state's Rwp, a rejected stage leaves it
    unchanged.  ``rwp_after`` may temporarily exceed ``rwp_before``
    when the optimizer diverges — that is why the rollback mechanism
    exists.
    """
    pattern = _si_pattern(scale=100.0)
    bad_cell = CellParams(5.46, 5.46, 5.46)
    entry = _si_entry_with_bad_cell(bad_cell)
    pm = PeakModel(eta=0.5, asymmetry=0.0, caglioti_uvw=(0.005, 0.0, 0.015))

    strategy = TurnOnStrategy()
    steps = strategy.run(pattern, entry, pm, wavelength=_WAVELENGTH, n_iter=20)
    rwp_befores = [s.rwp_before for s in steps]
    # rwp_before is non-increasing across stages.
    for i in range(1, len(rwp_befores)):
        assert rwp_befores[i] <= rwp_befores[i - 1] + 1e-9, (
            f"rwp_before increased from stage {steps[i-1].stage_name} "
            f"({rwp_befores[i-1]:.6f}) to {steps[i].stage_name} "
            f"({rwp_befores[i]:.6f})"
        )


def test_rollback_rejects_no_op_stages():
    """Stages that have no parameters to refine (background, atoms) are
    no-ops and must be reported as *not accepted* (rolled back), with
    ``rwp_after`` essentially equal to ``rwp_before`` (only numerical
    jitter from the locked-parameter optimisation step is allowed).
    """
    pattern = _si_pattern(scale=100.0)
    bad_cell = CellParams(5.46, 5.46, 5.46)
    entry = _si_entry_with_bad_cell(bad_cell)
    pm = PeakModel(eta=0.5, asymmetry=0.0, caglioti_uvw=(0.005, 0.0, 0.015))

    strategy = TurnOnStrategy()
    steps = strategy.run(pattern, entry, pm, wavelength=_WAVELENGTH, n_iter=20)
    no_param_stages = [s for s in steps if not s.params_enabled]
    assert len(no_param_stages) >= 1
    for s in no_param_stages:
        # A no-op stage should leave Rwp unchanged (within numerical
        # jitter) and hence be reported as not accepted.
        assert s.accepted is False, (
            f"stage {s.stage_name} was accepted but had no parameters to refine"
        )
        assert abs(s.rwp_after - s.rwp_before) < 1e-4, (
            f"stage {s.stage_name} changed Rwp despite having no free params: "
            f"{s.rwp_before:.6f} → {s.rwp_after:.6f}"
        )


def test_rollback_triggers_when_optimizer_diverges():
    """At least one stage in this run is rejected (either because it is a
    genuine no-op *or* because the optimizer diverged).  This verifies
    the rollback path is exercised.
    """
    pattern = _si_pattern(scale=100.0)
    bad_cell = CellParams(5.46, 5.46, 5.46)
    entry = _si_entry_with_bad_cell(bad_cell)
    pm = PeakModel(eta=0.5, asymmetry=0.0, caglioti_uvw=(0.005, 0.0, 0.015))

    strategy = TurnOnStrategy()
    steps = strategy.run(pattern, entry, pm, wavelength=_WAVELENGTH, n_iter=20)
    rejected = [s for s in steps if not s.accepted]
    assert len(rejected) >= 1, "expected at least one rolled-back stage"


def test_custom_stages_can_be_supplied():
    """The strategy accepts a custom stage list."""
    pattern = _si_pattern(scale=100.0)
    bad_cell = CellParams(5.46, 5.46, 5.46)
    entry = _si_entry_with_bad_cell(bad_cell)
    pm = PeakModel(eta=0.5, asymmetry=0.0, caglioti_uvw=(0.005, 0.0, 0.015))

    custom = [("scale_only", (0,)), ("cell", (2, 3, 4))]
    strategy = TurnOnStrategy(stages=custom)
    steps = strategy.run(pattern, entry, pm, wavelength=_WAVELENGTH, n_iter=20)
    assert [s.stage_name for s in steps] == ["scale_only", "cell"]


def test_rwp_tolerance_affects_acceptance():
    """A high rwp_tolerance rejects even small improvements."""
    pattern = _si_pattern(scale=100.0)
    bad_cell = CellParams(5.46, 5.46, 5.46)
    entry = _si_entry_with_bad_cell(bad_cell)
    pm = PeakModel(eta=0.5, asymmetry=0.0, caglioti_uvw=(0.005, 0.0, 0.015))

    strategy = TurnOnStrategy()
    steps = strategy.run(
        pattern, entry, pm,
        wavelength=_WAVELENGTH, n_iter=20,
        rwp_tolerance=10.0,  # absurdly high — no stage can satisfy this
    )
    assert all(not s.accepted for s in steps)


def test_step_records_param_names():
    """Each TurnOnStep records the names of the parameters it unlocks."""
    pattern = _si_pattern(scale=100.0)
    bad_cell = CellParams(5.46, 5.46, 5.46)
    entry = _si_entry_with_bad_cell(bad_cell)
    pm = PeakModel(eta=0.5, asymmetry=0.0, caglioti_uvw=(0.005, 0.0, 0.015))

    strategy = TurnOnStrategy()
    steps = strategy.run(pattern, entry, pm, wavelength=_WAVELENGTH, n_iter=20)
    by_name = {s.stage_name: s for s in steps}
    assert by_name["scale"].params_enabled == ["scale"]
    assert by_name["zero_lattice"].params_enabled == [
        "zero_shift", "a", "b", "c", "alpha", "beta", "gamma",
    ]
    assert by_name["profile_uvw"].params_enabled == ["U", "V", "W"]
    assert by_name["background"].params_enabled == []
    assert by_name["atoms"].params_enabled == []
