"""Reverse-engineering framework for the Match! FoM P-value definitions (T0.8).

The FoM *weights* have already been reverse-engineered (see
``FOM_MODEL.md`` §2, R² = 0.9913) but the **definition of each individual
P value** (peakpos / intensity / npeaks / ncorr) and the *I_scale*
normalisation is still the "working" placeholder in
:mod:`xinmatch.core.search.fom_criteria`.

This module provides a reusable pipeline that consumes Match!'s exported
candidate-list CSV (semicolon-delimited, European format) and pairs each
candidate row with our own re-computed P values, then sweeps a set of
candidate P-value definitions (Gaussian / Lorentzian / Linear / Cosine
penalty kernels) to find the one that best reproduces Match!'s value.

Usage
-----
Place one or more Match! candidate-list exports under
``tests/baseline/`` (one ``*.csv`` per sample) and run::

    python -m tools.build_baseline

The script will:

1. Parse every CSV (see :func:`parse_match4_csv`).
2. Re-compute our P values for each candidate row using the
   XinMatch pipeline (the caller must supply a ``.our_p_values``
   side-channel per row, see :func:`reverse_engineer_p_defs`).
3. For each P value, try several kernel families and pick the
   best-fitting one (R²).  Return a structured report.

The framework is designed to be data-driven: as the user exports more
CSV files from Match!, the reverse-engineering becomes statistically
meaningful.  With only a single row (the lab6 / LaB6 sample shipped
with Match!) no firm conclusion can be drawn — see the Part-1 report
in the T0.8 task description.

This module is intentionally pure-Python and side-effect-free; **no
GUI / matplotlib / network access required**.
"""

from __future__ import annotations

import csv
import math
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------- #

# Header used by Match! 4.3 Build 360 when exporting the candidate list
# via ``export_candidatelist(..., CSV)`` (European CSV format: ``;``-sep).
MATCH4_CSV_HEADER: tuple[str, ...] = (
    "Entry",
    "Qual.",
    "Formula sum",
    "Name",
    "P(peakpos.)",
    "P(I/I0)",
    "P(#peaks)",
    "P(#corr.)",
    "I scale fct.",
    "FoM",
)

# Map Match! column names to the keys used by ``compute_p_values``.
P_KEY_MAP: dict[str, str] = {
    "P(peakpos.)": "peakpos",
    "P(I/I0)": "intensity",
    "P(#peaks)": "npeaks",
    "P(#corr.)": "ncorr",
    "I scale fct.": "i_scale",
}


# --------------------------------------------------------------------- #
# CSV parsing
# --------------------------------------------------------------------- #


def parse_match4_csv(csv_path: str | Path) -> list[dict[str, str | float]]:
    """Parse a Match!-exported candidate-list CSV.

    The file is semicolon-separated (European CSV convention) with the
    fixed header :data:`MATCH4_CSV_HEADER`.  Numeric fields are cast to
    ``float``; text fields (Entry / Qual. / Formula sum / Name) are kept
    as ``str``.

    Parameters
    ----------
    csv_path:
        Path to the exported CSV.

    Returns
    -------
    list[dict[str, str | float]]
        One dict per candidate row, keys = header names.  Numeric P
        values are accessible via the same column names as in the CSV
        (e.g. ``row["P(peakpos.)"]``).

    Raises
    ------
    FileNotFoundError
        If *csv_path* does not exist.
    ValueError
        If the file does not look like a Match! candidate-list CSV
        (header mismatch).
    """
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(p)

    # Match! CSV is European format: ``;``-sep, ``,`` decimal point.
    with p.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)
    if not rows:
        raise ValueError(f"Empty CSV: {p}")

    header = [c.strip() for c in rows[0]]
    # Validate header — every required column must be present (extra
    # trailing columns are tolerated, e.g. a stray empty field from a
    # trailing ``;``).
    missing = [c for c in MATCH4_CSV_HEADER if c not in header]
    if missing:
        raise ValueError(
            f"CSV {p} header does not match Match! candidate-list "
            f"format. Missing columns: {missing}. Found: {header}"
        )

    # Build column index lookup once.
    col_idx = {name: header.index(name) for name in header}

    # Numeric columns: the four P values, I scale fct., FoM.
    numeric_cols = [
        "P(peakpos.)",
        "P(I/I0)",
        "P(#peaks)",
        "P(#corr.)",
        "I scale fct.",
        "FoM",
    ]

    out: list[dict[str, str | float]] = []
    for raw in rows[1:]:
        if not raw or all(not c.strip() for c in raw):
            continue  # skip blank lines
        if len(raw) < len(header):
            # Pad short rows to avoid IndexError.
            raw = raw + [""] * (len(header) - len(raw))
        rec: dict[str, str | float] = {}
        for name, idx in col_idx.items():
            val = raw[idx].strip() if idx < len(raw) else ""
            if name in numeric_cols:
                # European decimal: replace comma with dot.
                try:
                    rec[name] = float(val.replace(",", ".")) if val else 0.0
                except ValueError:
                    rec[name] = 0.0
            else:
                rec[name] = val
        out.append(rec)
    return out


# --------------------------------------------------------------------- #
# Reverse engineering
# --------------------------------------------------------------------- #


@dataclass
class KernelFit:
    """Result of fitting one P-value kernel to the data."""

    name: str           # kernel family name (gaussian/lorentzian/...)
    formula: str       # human-readable formula
    best_param: float  # best-fit kernel parameter (sigma / width / etc.)
    r_squared: float   # coefficient of determination vs Match! P
    rmse: float        # root-mean-square error
    n: int             # number of data points used


@dataclass
class ReverseEngineerReport:
    """Structured report for one P value across all candidates."""

    p_key: str               # "peakpos" / "intensity" / ...
    csv_key: str             # original Match! column name
    best_kernel: KernelFit
    all_kernels: list[KernelFit] = field(default_factory=list)
    n_samples: int = 0


# --------------------------------------------------------------------- #
# Candidate P-value kernels
# --------------------------------------------------------------------- #
# Each kernel takes a *mismatch* array and a *param* (sigma/width/etc.)
# and returns a value in [0, 1] that should reproduce Match!'s P value.
# The mismatch is the underlying "error" metric (e.g. mean Δ2θ² for
# peakpos, mean ΔI² for intensity, n_unmatched/n_total for npeaks, etc).
# The kernel is fit by sweeping ``param`` over a grid and picking the
# best R².


def _kernel_gaussian(mismatch: float, sigma: float) -> float:
    """Gaussian penalty: P = exp(-mismatch / sigma²)."""
    if sigma <= 0:
        return 0.0
    return float(math.exp(-mismatch / (sigma * sigma)))


def _kernel_lorentzian(mismatch: float, gamma: float) -> float:
    """Lorentzian penalty: P = 1 / (1 + mismatch / gamma²)."""
    if gamma <= 0:
        return 0.0
    return float(1.0 / (1.0 + mismatch / (gamma * gamma)))


def _kernel_linear(mismatch: float, scale: float) -> float:
    """Linear penalty: P = max(0, 1 - mismatch / scale)."""
    if scale <= 0:
        return 0.0
    return float(max(0.0, 1.0 - mismatch / scale))


def _kernel_cosine(mismatch: float, half_period: float) -> float:
    """Cosine penalty: P = cos(pi * mismatch / (2 * half_period)) in [0, half_period], else 0."""
    if half_period <= 0:
        return 0.0
    arg = math.pi * mismatch / (2.0 * half_period)
    if arg >= math.pi / 2.0:
        return 0.0
    return float(math.cos(arg))


# Family registry: (name, fn, param grid).
_KERNEL_FAMILIES: list[tuple[str, Callable[[float, float], float], list[float]]] = [
    ("gaussian", _kernel_gaussian,
     [0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]),
    ("lorentzian", _kernel_lorentzian,
     [0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]),
    ("linear", _kernel_linear,
     [0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]),
    ("cosine", _kernel_cosine,
     [0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]),
]


def _r_squared(observed: list[float], predicted: list[float]) -> float:
    """Coefficient of determination R² between observed and predicted."""
    n = len(observed)
    if n < 2:
        return 0.0
    mean_obs = sum(observed) / n
    ss_res = sum((o - p) ** 2 for o, p in zip(observed, predicted, strict=True))
    ss_tot = sum((o - mean_obs) ** 2 for o in observed)
    if ss_tot == 0:
        return 1.0 if ss_res == 0 else 0.0
    return 1.0 - ss_res / ss_tot


def _rmse(observed: list[float], predicted: list[float]) -> float:
    """Root-mean-square error."""
    n = len(observed)
    if n == 0:
        return 0.0
    return math.sqrt(sum((o - p) ** 2 for o, p in zip(observed, predicted, strict=True)) / n)


def _fit_kernel(
    kernel_fn: Callable[[float, float], float],
    param_grid: list[float],
    mismatches: list[float],
    observed: list[float],
) -> tuple[float, float, float]:
    """Return (best_param, best_r2, best_rmse) for a single kernel family."""
    best_r2 = -math.inf
    best_param = 0.0
    best_rmse = math.inf
    for param in param_grid:
        predicted = [kernel_fn(m, param) for m in mismatches]
        r2 = _r_squared(observed, predicted)
        rmse = _rmse(observed, predicted)
        if r2 > best_r2:
            best_r2 = r2
            best_param = param
            best_rmse = rmse
    return best_param, best_r2, best_rmse


def reverse_engineer_p_defs(
    samples: list[dict],
    our_p_values: list[dict],
) -> dict[str, ReverseEngineerReport]:
    """Reverse-engineer the definition of each P value from data.

    For each P value (peakpos / intensity / npeaks / ncorr / i_scale),
    the function tries multiple kernel families (Gaussian, Lorentzian,
    Linear, Cosine) and picks the one whose R² against Match!'s exported
    P value is highest.

    Parameters
    ----------
    samples:
        Output of :func:`parse_match4_csv` — one dict per candidate row,
        with keys from :data:`MATCH4_CSV_HEADER`.
    our_p_values:
        Parallel list of dicts with the **mismatch metrics** that our
        P-value computation produces *before* applying any kernel.
        Each dict must carry keys:

        - ``peakpos_mismatch``: mean(Δ2θ²)
        - ``intensity_mismatch``: mean(ΔI_norm²)
        - ``npeaks_mismatch``: 1 − n_matched/n_exp
        - ``ncorr_mismatch``: 1 − n_matched_ref / min(n_exp, n_ref)
        - ``i_scale_log_delta``: |ln(I_scale)|

        These are the *raw* mismatches that the kernels map to P values.
        Callers can compute these via
        :func:`xinmatch.core.search.fom_criteria.compute_p_values`
        plus the underlying peak arrays; here we treat them as given so
        the framework stays decoupled from the core API.

    Returns
    -------
    dict[str, ReverseEngineerReport]
        One report per P key (``peakpos`` / ``intensity`` / ``npeaks``
        / ``ncorr`` / ``i_scale``).  Each report carries the best kernel
        family + parameter + R², plus the full per-family list.

    Raises
    ------
    ValueError
        If *samples* and *our_p_values* have different lengths.
    """
    if len(samples) != len(our_p_values):
        raise ValueError(
            f"samples and our_p_values must have the same length; "
            f"got {len(samples)} vs {len(our_p_values)}"
        )

    # Mismatch key -> CSV column name (for observed P).
    p_specs = [
        ("peakpos", "P(peakpos.)", "peakpos_mismatch",
         "mean(Δ2θ²)", "gaussian: P = exp(-mean(Δ2θ²) / σ²)"),
        ("intensity", "P(I/I0)", "intensity_mismatch",
         "mean(ΔI_norm²)", "gaussian: P = exp(-mean(ΔI²) / σ²)"),
        ("npeaks", "P(#peaks)", "npeaks_mismatch",
         "1 − n_matched/n_exp", "linear: P = max(0, 1 − mismatch/σ)"),
        ("ncorr", "P(#corr.)", "ncorr_mismatch",
         "1 − n_matched_ref/min(n_exp,n_ref)",
         "linear: P = max(0, 1 − mismatch/σ)"),
        ("i_scale", "I scale fct.", "i_scale_log_delta",
         "|ln(I_scale)|",
         "linear (multiplicative): P = exp(-|ln(I_scale)|)"),
    ]

    reports: dict[str, ReverseEngineerReport] = {}
    for p_key, csv_key, mismatch_key, mismatch_desc, formula_hint in p_specs:
        # Build (mismatch, observed_p) pairs from the parallel lists.
        pairs_xy: list[tuple[float, float]] = []
        for sample, our in zip(samples, our_p_values, strict=True):
            if mismatch_key not in our:
                continue
            mismatch = float(our[mismatch_key])
            observed_p = float(sample.get(csv_key, 0.0))
            # i_scale: observed value is the I scale fct. itself, not a
            # P value.  We compare to exp(-|ln(I_scale_obs)|) so the
            # kernel target is in [0, 1].
            if p_key == "i_scale":
                obs = observed_p
                target = math.exp(-abs(math.log(max(obs, 1e-12))))
            else:
                target = observed_p
            pairs_xy.append((mismatch, target))

        if not pairs_xy:
            reports[p_key] = ReverseEngineerReport(
                p_key=p_key,
                csv_key=csv_key,
                best_kernel=KernelFit(
                    name="none",
                    formula=f"no data; expected mismatch='{mismatch_desc}'",
                    best_param=0.0,
                    r_squared=0.0,
                    rmse=0.0,
                    n=0,
                ),
                all_kernels=[],
                n_samples=0,
            )
            continue

        mismatches = [m for m, _ in pairs_xy]
        observed = [t for _, t in pairs_xy]

        all_kernels: list[KernelFit] = []
        best_overall = KernelFit(
            name="none", formula="", best_param=0.0,
            r_squared=-math.inf, rmse=math.inf, n=len(pairs_xy),
        )
        for name, fn, grid in _KERNEL_FAMILIES:
            best_param, best_r2, best_rmse = _fit_kernel(
                fn, grid, mismatches, observed
            )
            fit = KernelFit(
                name=name,
                formula=formula_hint,
                best_param=best_param,
                r_squared=best_r2,
                rmse=best_rmse,
                n=len(pairs_xy),
            )
            all_kernels.append(fit)
            if best_r2 > best_overall.r_squared:
                best_overall = fit

        reports[p_key] = ReverseEngineerReport(
            p_key=p_key,
            csv_key=csv_key,
            best_kernel=best_overall,
            all_kernels=all_kernels,
            n_samples=len(pairs_xy),
        )

    return reports


# --------------------------------------------------------------------- #
# LaB6 reference table (computed from crystal structure)
# --------------------------------------------------------------------- #


def compute_lab6_reference_table(
    *,
    a: float = 4.157,
    wavelength: float = 1.5406,
    max_n: int = 16,
    b_iso_la: float = 0.5,
    b_iso_b: float = 1.0,
    max_2theta_deg: float = 150.0,
) -> list[tuple[float, float]]:
    """Compute the LaB6 reference (d, I) table from crystallographic structure.

    LaB6 crystallises in Pm-3m (#221) with La at (0,0,0) and the B6
    octahedron occupying the six face centres of the cubic cell
    (three unique positions, each translation-equivalent pair giving
    multiplicity 2 per site).  This routine enumerates one representative
    reflection per Laue orbit, computes the integrated intensity

        I(hkl) = |F(hkl)|² · m(hkl) · LP(2θ)

    and merges reflections sharing the same 2θ (e.g. (3,0,0) and
    (2,2,1), both with h²+k²+l²=9 in cubic).  The output is normalised
    to max = 100 — the convention Match! uses for the ``I/I₀`` column
    of the candidate-list CSV — and sorted by *d descending* (Match!
    reference-peak-table convention).

    Used by T0.8 (1-row rough pass) to provide the reference table that
    :func:`~xinmatch.core.search.fom_criteria.score_candidate` expects,
    so the same XinMatch pipeline that scores candidates can also score
    the lab6 sample.

    Parameters
    ----------
    a:
        Lattice parameter in Å (default 4.157, LaB6 at room T).
    wavelength:
        Radiation wavelength in Å (default 1.5406, Cu Kα1).
    max_n:
        Maximum value of ``h²+k²+l²`` to enumerate (default 16).
        Covers reflections up to ~150° 2θ for Cu Kα on LaB6.
    b_iso_la, b_iso_b:
        Isotropic displacement parameters (Å²) for La and B.
    max_2theta_deg:
        Hard upper bound on 2θ (default 150°).

    Returns
    -------
    list[tuple[float, float]]
        ``(d_spacing_Å, intensity)`` tuples, intensities normalised to
        max = 100, sorted by d descending (= 2θ ascending).

    Notes
    -----
    The hard-coded ``b_iso`` values are rough literature estimates
    (La ~0.5 Å², B ~1.0 Å²).  They affect the relative intensities of
    high-angle peaks; for the FoM P-value verification the effect is
    small because the (110) and (211) peaks that dominate the FoM lie
    below 60° 2θ where ``T(s)`` is close to 1.
    """
    # Lazy imports keep the module importable without the full core
    # stack (e.g. when run as a CLI from a stripped-down distribution).
    from xinmatch.core.index.lattice import compute_d
    from xinmatch.core.model.entry import CellParams
    from xinmatch.core.refine.structure_factor import (
        Atom,
        lorentz_polarization,
        multiplicity,
        structure_factor,
    )

    cell = CellParams(a=a, b=a, c=a)
    atoms = [
        Atom("La", 0.0, 0.0, 0.0, occupancy=1.0, b_iso=b_iso_la),
        # B6 octahedron: 6 B atoms at the 6 face centres of the cubic
        # cell.  Three unique positions, each with a translation-equivalent
        # partner → occupancy 2 per unique site.
        Atom("B", 0.5, 0.5, 0.0, occupancy=2.0, b_iso=b_iso_b),
        Atom("B", 0.5, 0.0, 0.5, occupancy=2.0, b_iso=b_iso_b),
        Atom("B", 0.0, 0.5, 0.5, occupancy=2.0, b_iso=b_iso_b),
    ]

    # Enumerate one (h,k,l) per Laue orbit (canonical sorted form
    # h ≥ k ≥ l ≥ 0).  Different orbits with the same N = h²+k²+l²
    # land at the same 2θ in cubic and must be merged afterwards.
    refls: list[tuple[float, float, float]] = []  # (d, two_theta, I_unnorm)
    seen_canonical: set[tuple[int, int, int]] = set()
    for h in range(0, max_n + 1):
        for k in range(0, max_n + 1):
            for ll in range(0, max_n + 1):
                if h == 0 and k == 0 and ll == 0:
                    continue
                if h * h + k * k + ll * ll > max_n:
                    continue
                canonical = tuple(sorted((h, k, ll), reverse=True))
                if canonical in seen_canonical:
                    continue
                seen_canonical.add(canonical)
                d = float(compute_d(canonical, cell))
                if d <= wavelength / 2.0:
                    continue
                sin_t = wavelength / (2.0 * d)
                if sin_t >= 1.0:
                    continue
                two_theta = math.degrees(2.0 * math.asin(sin_t))
                if two_theta > max_2theta_deg:
                    continue
                f_hkl = structure_factor(
                    canonical, atoms, cell, wavelength=wavelength
                )
                m = multiplicity(canonical, "cubic")
                lp = lorentz_polarization(
                    two_theta, wavelength=wavelength
                )
                intensity = (abs(f_hkl) ** 2) * m * lp
                refls.append((d, two_theta, intensity))

    if not refls:
        return []

    # Merge orbits that share the same 2θ (within 0.01° tolerance).
    refls.sort(key=lambda r: r[1])
    merged: list[list[float]] = []  # [d_weighted_sum, two_theta, I_total]
    for d, tt, intensity in refls:
        if merged and abs(tt - merged[-1][1]) < 0.01:
            merged[-1][0] += d * intensity
            merged[-1][2] += intensity
            merged[-1][3] += intensity  # weight accumulator
        else:
            merged.append([d * intensity, tt, intensity, intensity])

    out: list[tuple[float, float]] = []
    for d_weighted, _, intensity_total, weight in merged:
        d_avg = d_weighted / weight if weight > 0 else 0.0
        out.append((d_avg, intensity_total))

    if not out:
        return []
    max_i = max(intensity for _, intensity in out)
    if max_i <= 0.0:
        return out
    normalised = [(d, i / max_i * 100.0) for d, i in out]
    # Match! reference-peak table is sorted by descending intensity;
    # for FoM computation the order does not matter — both correlate
    # by 2θ-window matching — but we follow the convention.
    normalised.sort(key=lambda r: -r[1])
    return normalised


# --------------------------------------------------------------------- #
# One-candidate pipeline → raw mismatches
# --------------------------------------------------------------------- #


def compute_our_p_mismatches(
    exp_peaks: list,
    ref_peaks_d_intensity: list[tuple[float, float]],
    wavelength: float,
    *,
    window_deg: float = 0.3,
    sigma_pos: float = 0.1,
    sigma_intensity: float = 10.0,
    method: str = "greedy",
) -> dict[str, float]:
    """Run the XinMatch pipeline for one candidate and return raw mismatches.

    Wraps :func:`~xinmatch.core.search.correlate.correlate_peaks` +
    :func:`~xinmatch.core.search.fom_criteria.compute_p_values` and
    inverts the resulting P values back to the underlying mismatch
    quantities so that :func:`reverse_engineer_p_defs` can fit kernel
    families against them.

    Parameters
    ----------
    exp_peaks:
        Experimental peaks (``list[Peak]`` — typed loosely here to
        avoid importing :class:`~xinmatch.core.model.Peak` at module
        load time and creating a circular dependency).
    ref_peaks_d_intensity:
        Reference peaks as ``(d_spacing_Å, intensity)`` tuples.
    wavelength:
        Wavelength in Å.
    window_deg, sigma_pos, sigma_intensity, method:
        Forwarded to the XinMatch correlation / P-value pipeline.

    Returns
    -------
    dict[str, float]
        Keys:

        - ``peakpos_mismatch``: ``mean(Δ2θ²)`` (deg²)
        - ``intensity_mismatch``: ``mean(ΔI_norm²)`` (norm-to-100 units²)
        - ``npeaks_mismatch``: ``1 − n_matched_exp / n_exp``
        - ``ncorr_mismatch``: ``1 − n_matched_ref / min(n_exp, n_ref)``
        - ``i_scale_log_delta``: ``|ln(I_scale)|``
        - ``peakpos``, ``intensity``, ``npeaks``, ``ncorr``, ``i_scale``:
          the five P values computed by :func:`compute_p_values`
          (kept for inspection / debugging)
        - ``n_pairs``: number of correlated pairs.
    """
    from xinmatch.core.search.correlate import correlate_peaks
    from xinmatch.core.search.fom_criteria import compute_p_values

    pairs = correlate_peaks(
        exp_peaks,
        ref_peaks_d_intensity,
        wavelength,
        window_deg,
        method=method,
    )
    p = compute_p_values(
        exp_peaks,
        ref_peaks_d_intensity,
        pairs,
        wavelength,
        sigma_pos=sigma_pos,
        sigma_intensity=sigma_intensity,
    )

    return {
        # Invert P = exp(-mismatch / σ²) → mismatch = -σ² · ln(P).
        "peakpos_mismatch": -sigma_pos ** 2 * math.log(
            max(p["peakpos"], 1e-12)
        ),
        "intensity_mismatch": -sigma_intensity ** 2 * math.log(
            max(p["intensity"], 1e-12)
        ),
        "npeaks_mismatch": 1.0 - p["npeaks"],
        "ncorr_mismatch": 1.0 - p["ncorr"],
        "i_scale_log_delta": abs(math.log(max(p["i_scale"], 1e-12))),
        # Echo the raw P values for inspection / log output.
        "peakpos": p["peakpos"],
        "intensity": p["intensity"],
        "npeaks": p["npeaks"],
        "ncorr": p["ncorr"],
        "i_scale": p["i_scale"],
        "n_pairs": float(len(pairs)),
    }


# --------------------------------------------------------------------- #
# LaB6 P-value verification (T0.8 1-row rough pass)
# --------------------------------------------------------------------- #


# Match! 4.3 Build 360 exported P values for the LaB6 Top1 candidate of
# the lab6 sample (FOM_MODEL.md §1).  These are the **ground truth** we
# are reverse-engineering against.  Source: ``export_candidatelist(...,
# CSV)`` on the lab6 sample loaded from
# ``C:\Program Files\Match4\Tutorial\LaB6_Cu_Ka1.dat``.
LAB6_MATCH4_P_VALUES: dict[str, float] = {
    "peakpos": 0.9968,
    "intensity": 0.9963,
    "npeaks": 0.9961,
    "ncorr": 1.0000,
    "i_scale": 1.0348,
    "fom": 0.9979,
}


@dataclass
class Lab6VerificationResult:
    """Outcome of running the XinMatch pipeline against the lab6 sample.

    Attributes
    ----------
    n_exp_peaks:
        Number of experimental peaks detected by ``find_peaks`` in the
        lab6 ``.dat`` file after the auto-processing pipeline.
    n_ref_peaks:
        Number of reference peaks in the LaB6 d-I table returned by
        :func:`compute_lab6_reference_table`.
    n_pairs:
        Number of one-to-one correlated pairs.
    our_p:
        The five P values produced by our
        :func:`~xinmatch.core.search.fom_criteria.compute_p_values`.
    match4_p:
        The five P values exported by Match! 4.3 (see
        :data:`LAB6_MATCH4_P_VALUES`).
    delta:
        ``our_p[k] - match4_p[k]`` for each key.  Positive = our value
        overestimates Match!'s.
    relative_delta_pct:
        ``(our_p[k] - match4_p[k]) / match4_p[k] × 100``.  For ``i_scale``
        and FoM a multiplicative deviation is more meaningful than an
        additive one.
    """

    n_exp_peaks: int
    n_ref_peaks: int
    n_pairs: int
    our_p: dict[str, float]
    match4_p: dict[str, float]
    delta: dict[str, float]
    relative_delta_pct: dict[str, float]


def verify_lab6_p_values(
    dat_path: str | Path,
    *,
    wavelength: float = 1.5406,
    window_deg: float = 0.3,
    sigma_pos: float = 0.1,
    sigma_intensity: float = 10.0,
    sensitivity: str = "medium",
) -> Lab6VerificationResult:
    """Run the XinMatch pipeline on the lab6 sample and compare to Match!.

    Loads the lab6 ``.dat`` file (the LaB6 standard sample shipped with
    the Match! tutorial), runs the automatic preprocessing + peak-search
    pipeline, scores the result against the LaB6 reference d-I table
    built by :func:`compute_lab6_reference_table`, and compares the
    resulting five P values against Match!'s exported Top1 row
    (:data:`LAB6_MATCH4_P_VALUES`).

    This is the T0.8 **1-row rough pass**: with only one sample the
    comparison cannot pin down a kernel family, but it can verify that
    our P-value definitions are in the right ballpark (within a few
    percent of Match!'s values) and surface any sign errors or
    normalisation mistakes.

    Parameters
    ----------
    dat_path:
        Path to the lab6 ``.dat`` file shipped with Match! 4
        (typically ``C:\\Program Files\\Match4\\Tutorial\\LaB6_Cu_Ka1.dat``
        or a copy of it under ``tests/baseline/fixtures/``).
    wavelength, window_deg, sigma_pos, sigma_intensity:
        Pipeline parameters forwarded to the FoM computation.
    sensitivity:
        Peak-search sensitivity preset (``'low'`` / ``'medium'`` /
        ``'high'``).

    Returns
    -------
    Lab6VerificationResult
        The structured comparison.  Inspect ``delta`` and
        ``relative_delta_pct`` for the per-P-value disagreement.
    """
    from xinmatch.core.io import load_pattern
    from xinmatch.core.preprocess.auto_pipeline import auto_process
    from xinmatch.core.search.correlate import correlate_peaks
    from xinmatch.core.search.fom_criteria import compute_fom, compute_p_values

    pattern = load_pattern(dat_path)
    _, exp_peaks = auto_process(
        pattern,
        config={
            "wavelength_kalpha1": wavelength,
            "wavelength_kalpha2": 1.5444,
            "peak_sensitivity": sensitivity,
        },
    )
    ref_table = compute_lab6_reference_table(wavelength=wavelength)
    pairs = correlate_peaks(
        exp_peaks,
        ref_table,
        wavelength,
        window_deg,
    )
    p = compute_p_values(
        exp_peaks,
        ref_table,
        pairs,
        wavelength,
        sigma_pos=sigma_pos,
        sigma_intensity=sigma_intensity,
    )
    fom = compute_fom(p)
    p_with_fom = dict(p)
    p_with_fom["fom"] = fom

    delta = {k: p_with_fom.get(k, 0.0) - LAB6_MATCH4_P_VALUES.get(k, 0.0)
             for k in LAB6_MATCH4_P_VALUES}
    rel = {}
    for k in LAB6_MATCH4_P_VALUES:
        ref = LAB6_MATCH4_P_VALUES[k]
        if abs(ref) > 1e-12:
            rel[k] = (p_with_fom.get(k, 0.0) - ref) / ref * 100.0
        else:
            rel[k] = 0.0

    return Lab6VerificationResult(
        n_exp_peaks=len(exp_peaks),
        n_ref_peaks=len(ref_table),
        n_pairs=len(pairs),
        our_p=p_with_fom,
        match4_p=dict(LAB6_MATCH4_P_VALUES),
        delta=delta,
        relative_delta_pct=rel,
    )


# --------------------------------------------------------------------- #
# Baseline directory scan
# --------------------------------------------------------------------- #


def build_baseline(csv_dir: Path = Path("tests/baseline")) -> dict:
    """Scan a directory for Match! candidate-list CSVs and reverse-engineer.

    Parameters
    ----------
    csv_dir:
        Directory containing one or more ``*.csv`` files exported by
        Match!'s ``export_candidatelist(..., CSV)`` function.  Defaults
        to ``tests/baseline``.

    Returns
    -------
    dict
        A structured report with keys:

        - ``csv_files``: list of file names found.
        - ``n_candidates_total``: total candidate rows across all files.
        - ``per_file``: list of ``{file, n_candidates, candidates}``.
        - ``reverse_engineer``: dict of :class:`ReverseEngineerReport`
          (only populated when *our* P values are also provided via
          :func:`reverse_engineer_p_defs` — here we can only parse).

        For the reverse-engineering step the caller must supply their
        own P-value side-channel via
        :func:`reverse_engineer_p_defs`.  This function only handles
        the file-I/O + parsing layer.

    Notes
    -----
    If the directory does not exist or contains no ``*.csv`` files, an
    empty report is returned (no exception).
    """
    csv_dir = Path(csv_dir)
    out: dict = {
        "csv_files": [],
        "n_candidates_total": 0,
        "per_file": [],
    }
    if not csv_dir.exists() or not csv_dir.is_dir():
        return out

    csv_files = sorted(csv_dir.glob("*.csv"))
    out["csv_files"] = [str(p.name) for p in csv_files]
    for p in csv_files:
        try:
            candidates = parse_match4_csv(p)
        except (FileNotFoundError, ValueError):
            continue
        out["per_file"].append({
            "file": str(p.name),
            "n_candidates": len(candidates),
            "candidates": candidates,
        })
        out["n_candidates_total"] += len(candidates)
    return out


# --------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------- #


def _format_report(report: ReverseEngineerReport) -> str:
    """Human-readable one-line summary of a single P value's best fit."""
    best = report.best_kernel
    return (
        f"  {report.p_key:9s}  best: {best.name:10s}  "
        f"param={best.best_param:.4f}  R²={best.r_squared:.4f}  "
        f"RMSE={best.rmse:.4f}  n={best.n}"
    )


def main(argv: Iterable[str] | None = None) -> int:
    """CLI entry point: ``python -m tools.build_baseline``.

    Scans ``tests/baseline/`` for Match! CSV exports and prints a
    summary.  If no CSV files are found, prints a hint and exits 0.
    """
    _ = list(argv) if argv is not None else sys.argv[1:]
    csv_dir = Path("tests/baseline")
    baseline = build_baseline(csv_dir)

    if not baseline["csv_files"]:
        print(
            f"No Match! candidate-list CSVs found in {csv_dir}/.\n"
            "Export candidate lists from Match! 4.x via "
            "'File → Export → candidate list (CSV)' and place them "
            "in that directory, then re-run."
        )
        return 0

    print(f"Found {len(baseline['csv_files'])} CSV file(s) in {csv_dir}/:")
    for entry in baseline["per_file"]:
        print(f"  {entry['file']}: {entry['n_candidates']} candidates")
    print(f"\nTotal candidates: {baseline['n_candidates_total']}")

    # Note: we cannot do reverse-engineering without the *our* P values
    # side-channel; the CLI only does parsing in this default mode.
    print(
        "\nTo reverse-engineer P-value definitions, call "
        "reverse_engineer_p_defs(samples, our_p_values) with the "
        "mismatch metrics computed via the XinMatch pipeline."
    )

    # Print first sample for sanity.
    if baseline["per_file"]:
        first = baseline["per_file"][0]["candidates"][0]
        print("\nFirst candidate of first file:")
        for k, v in first.items():
            print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
