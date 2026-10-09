"""Reader for Jade/MDI ``.mdi`` fixed-width intensity files.

Structure (verified on the 4-1.mdi sample):

* line 1: date + sample label
* line 2: ``start  step  <scale>  <anode>  <wavelength>  stop  <count>``
* following lines: fixed-width integer intensities (8 per line)

Known pitfall handled here (mirrors the PolyXRD loader): some files declare
``count = n`` yet carry a scan range whose span is ``n-1`` steps — i.e. the
conversion dropped the first channel.  If ``start + step*(n-1)`` does not
match the header ``stop``, the axis is rebuilt backwards from ``stop`` so
peak positions align with the sibling ``.dat``/``.txt``/``.xy`` exports.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from xinmatch.core.model import Pattern

_ANODE_WAVELENGTHS: dict[str, float] = {
    "CU": 1.5406,
    "CO": 1.78897,
    "CR": 2.28970,
    "FE": 1.93604,
    "MN": 2.10314,
    "NI": 1.65791,
    "MO": 0.70930,
    "AG": 0.55941,
}


def read_mdi(path: str | Path) -> Pattern:
    """Read a Jade/MDI fixed-width intensity file.

    Parameters
    ----------
    path:
        Path to the ``.mdi`` file.

    Returns
    -------
    Pattern
        Parsed diffraction pattern.

    Raises
    ------
    ValueError
        If the header cannot be parsed or no intensity data is found.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig", errors="ignore")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        raise ValueError(f"MDI file content too short: {p}")

    head_nums: list[float] = []
    for tok in lines[1].split():
        try:
            head_nums.append(float(tok))
        except ValueError:
            continue
    if len(head_nums) < 2:
        raise ValueError(f"MDI header has no start/step: {p}")
    start, step = head_nums[0], head_nums[1]
    if not (step > 0 and np.isfinite(start)):
        raise ValueError(f"MDI header start/step invalid: {p}")

    values: list[float] = []
    for ln in lines[2:]:
        for tok in ln.split():
            try:
                values.append(float(tok))
            except ValueError:
                continue
    if len(values) < 2:
        raise ValueError(f"MDI file has no intensity data: {p}")
    intensity = np.asarray(values, dtype=np.float64)
    n = len(intensity)

    # lost-first-channel correction: rebuild the axis from the header stop
    # when ``start + step*(n-1)`` misses it by more than half a step
    if len(head_nums) >= 3:
        want = start + step * (n - 1)
        span = step * max(n - 1, 1)
        cands = [c for c in head_nums[2:] if abs(c - want) <= 0.05 * span]
        if cands:
            stop = min(cands, key=lambda c: abs(c - want))
            if abs(start + step * (n - 1) - stop) > step / 2:
                start = stop - step * (n - 1)

    two_theta = start + step * np.arange(n, dtype=np.float64)

    wavelength = 1.5406
    anode: str | None = None
    for tok in lines[1].split():
        if tok.isalpha() and len(tok) <= 2:
            anode = tok
            break
    if anode:
        wl = _ANODE_WAVELENGTHS.get(anode.upper())
        if wl is not None:
            wavelength = wl

    return Pattern(
        two_theta=two_theta,
        intensity=intensity,
        wavelength=wavelength,
        step=float(step),
        metadata={"format": "mdi", "vendor": "MDI/Jade", "anode": anode},
    )
