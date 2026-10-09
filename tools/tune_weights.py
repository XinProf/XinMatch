"""FoM weight tuning tool (Phase 6 / T6.10).

Refines the FoM weights documented in ``FOM_MODEL.md`` (R² = 0.9913,
Kendall τ = 0.9105, reverse-engineered from 3640 the reference software candidate
rows) by running a non-negative least-squares (NNLS) refit and a small
grid-search refinement on the baseline data.

The FoM model is linear in the weights::

    FoM = 1 − w1·(1−P_peakpos) − w2·(1−P_intensity) − w3·(1−P_npeaks)
                − w4·(1−P_ncorr) − w5·|ln(I_scale)|

so NNLS recovers the optimal weights directly (this is the same method
used by ``tools/build_baseline.py`` to obtain the published weights).
The grid-search refinement probes a small neighbourhood around the
published weights to verify that no local improvement is missed.

Inputs
------
The tool loads candidate P values + FoM from
``tests/baseline/baseline.json``.  When that file is absent (the
The reference software baseline CSVs have not been imported yet), the tool falls back
to a **synthetic baseline** generated from the published weights with
small Gaussian noise (σ=0.005) so the tuning pipeline is exercisable
end-to-end.  The synthetic baseline has the same 3-sample / 3640-
candidate structure documented in ``FOM_MODEL.md`` §6.

Outputs
-------
- A printed table of weights (published / NNLS / grid-refined) with
  R² and Kendall τ for each.
- A recommendation: ``KEEP`` (no improvement) or ``UPDATE`` (improved
  R² beyond the published value).
- Optionally writes the structured report to JSON.

Exit code is 0 regardless of the recommendation (the published weights
are not modified in place — the user must update ``FOM_MODEL.md`` /
``fom_criteria.DEFAULT_WEIGHTS`` manually if ``UPDATE`` is advised).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import nnls
from scipy.stats import kendalltau

logger = logging.getLogger(__name__)

__all__ = [
    "PUBLISHED_WEIGHTS",
    "P_KEYS",
    "WeightSet",
    "TuneReport",
    "load_or_generate_baseline",
    "fit_weights_nnls",
    "grid_search_refine",
    "compute_r2_kendall",
    "main",
]


# --------------------------------------------------------------------------- #
# Published weights (FOM_MODEL.md §2)
# --------------------------------------------------------------------------- #
PUBLISHED_WEIGHTS: dict[str, float] = {
    "peakpos": 0.2275,
    "intensity": 0.1112,
    "npeaks": 0.2306,
    "ncorr": 0.1152,
    "i_scale": 0.0454,
}

P_KEYS: list[str] = ["peakpos", "intensity", "npeaks", "ncorr", "i_scale"]

# Default baseline JSON path.
BASELINE_JSON = Path("tests/baseline/baseline.json")


# --------------------------------------------------------------------------- #
# Result containers
# --------------------------------------------------------------------------- #
@dataclass
class WeightSet:
    """A set of FoM weights with associated quality metrics."""

    name: str
    weights: dict[str, float]
    r_squared: float
    kendall_tau: float
    rmse: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TuneReport:
    """Aggregated weight-tuning report."""

    n_candidates: int = 0
    n_samples: int = 0
    source: str = ""  # "baseline.json" or "synthetic"
    published: WeightSet | None = None
    nnls_fit: WeightSet | None = None
    grid_refined: WeightSet | None = None
    recommendation: str = "KEEP"  # "KEEP" or "UPDATE"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_candidates": self.n_candidates,
            "n_samples": self.n_samples,
            "source": self.source,
            "published": self.published.to_dict() if self.published else None,
            "nnls_fit": self.nnls_fit.to_dict() if self.nnls_fit else None,
            "grid_refined": self.grid_refined.to_dict() if self.grid_refined else None,
            "recommendation": self.recommendation,
            "notes": self.notes,
        }


# --------------------------------------------------------------------------- #
# Baseline loading / synthetic generation
# --------------------------------------------------------------------------- #
def _fom_from_p_values(
    p: dict[str, float], weights: dict[str, float]
) -> float:
    """Compute FoM from P values + weights (mirrors fom_criteria.compute_fom)."""
    i_scale = max(float(p.get("i_scale", 1.0)), 1e-12)
    return float(
        1.0
        - weights["peakpos"] * (1.0 - float(p.get("peakpos", 0.0)))
        - weights["intensity"] * (1.0 - float(p.get("intensity", 0.0)))
        - weights["npeaks"] * (1.0 - float(p.get("npeaks", 0.0)))
        - weights["ncorr"] * (1.0 - float(p.get("ncorr", 0.0)))
        - weights["i_scale"] * abs(math.log(i_scale))
    )


def generate_synthetic_baseline(
    n_candidates: int = 3640,
    n_samples: int = 3,
    *,
    weights: dict[str, float] | None = None,
    noise_sigma: float = 0.005,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate a synthetic baseline mirroring FOM_MODEL.md §6.

    The synthetic baseline has the same 3-sample / 3640-candidate
    structure as the published reference baseline.  P values are drawn
    from realistic distributions (most candidates have moderate P
    values; a few are near 1.0), FoM is computed from the published
    weights, and small Gaussian noise is added to simulate the model
    mismatch (R² ≈ 0.9913 in the original fit).

    Parameters
    ----------
    n_candidates:
        Total number of candidate rows (default 3640).
    n_samples:
        Number of samples (default 3, like lab6/aragonite/quickstart).
    weights:
        Weights to generate FoM from.  Defaults to :data:`PUBLISHED_WEIGHTS`.
    noise_sigma:
        Standard deviation of Gaussian noise added to FoM (default 0.005).
    seed:
        Random seed for reproducibility.

    Returns
    -------
    dict
        A baseline dict with the same structure as
        ``tests/baseline/baseline.json``: ``{"samples": [...], "n_candidates": int}``.
    """
    w = weights if weights is not None else PUBLISHED_WEIGHTS
    rng = np.random.default_rng(seed)

    # Distribute candidates roughly equally across the n_samples samples.
    per_sample = n_candidates // n_samples
    samples: list[dict[str, Any]] = []
    for s_idx in range(n_samples):
        rows: list[dict[str, Any]] = []
        n_this = per_sample + (n_candidates - per_sample * n_samples
                               if s_idx == n_samples - 1 else 0)
        for c_idx in range(n_this):
            # P values: most moderate, a few near 1.0 (the correct phase).
            is_top = (c_idx < 5)  # top-5 of each sample are the "real" hits
            if is_top:
                p_vals = {
                    "peakpos": float(rng.uniform(0.95, 1.0)),
                    "intensity": float(rng.uniform(0.90, 1.0)),
                    "npeaks": float(rng.uniform(0.92, 1.0)),
                    "ncorr": float(rng.uniform(0.95, 1.0)),
                    "i_scale": float(rng.uniform(0.85, 1.15)),
                }
            else:
                p_vals = {
                    "peakpos": float(rng.uniform(0.10, 0.95)),
                    "intensity": float(rng.uniform(0.05, 0.90)),
                    "npeaks": float(rng.uniform(0.05, 0.92)),
                    "ncorr": float(rng.uniform(0.10, 0.95)),
                    "i_scale": float(rng.uniform(0.40, 2.50)),
                }
            fom_clean = _fom_from_p_values(p_vals, w)
            fom_noisy = float(np.clip(
                fom_clean + rng.normal(0.0, noise_sigma), 0.0, 1.0
            ))
            rows.append({
                "entry_id": f"synth-{s_idx}-{c_idx:04d}",
                "p_values": p_vals,
                "fom": fom_noisy,
                "fom_clean": fom_clean,  # kept for diagnostics
            })
        samples.append({
            "sample_id": f"synth-sample-{s_idx}",
            "candidates": rows,
            "n_candidates": len(rows),
        })

    return {
        "samples": samples,
        "n_candidates": n_candidates,
        "n_samples": n_samples,
        "source": "synthetic",
        "published_weights": dict(w),
        "noise_sigma": noise_sigma,
        "seed": seed,
    }


def load_or_generate_baseline(
    json_path: Path | None = None,
) -> tuple[dict[str, Any], str]:
    """Load baseline.json or generate a synthetic fallback.

    Returns
    -------
    tuple[dict, str]
        ``(baseline, source)`` where *source* is ``"baseline.json"``
        or ``"synthetic"``.
    """
    p = json_path or BASELINE_JSON
    if p.exists():
        with p.open(encoding="utf-8") as f:
            return json.load(f), str(p)
    logger.info("baseline.json not found at %s; generating synthetic", p)
    return generate_synthetic_baseline(), "synthetic"


def _extract_p_and_fom(
    baseline: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    """Extract the (P-value matrix, FoM vector) from the baseline dict.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        ``(x, y)`` where x has shape (n_candidates, 5) with columns
        ``[1-P_peakpos, 1-P_intensity, 1-P_npeaks, 1-P_ncorr,
        |ln(I_scale)|]`` and y has shape (n_candidates,) with the
        observed FoM values.
    """
    rows: list[dict[str, Any]] = []
    for sample in baseline.get("samples", []):
        rows.extend(sample.get("candidates", []))
    if not rows:
        return np.empty((0, 5)), np.empty(0)

    x = np.zeros((len(rows), 5), dtype=np.float64)
    y = np.zeros(len(rows), dtype=np.float64)
    for i, r in enumerate(rows):
        p = r.get("p_values", r)  # tolerate flat or nested structure
        p_peakpos = float(p.get("peakpos", 0.0))
        p_intensity = float(p.get("intensity", 0.0))
        p_npeaks = float(p.get("npeaks", 0.0))
        p_ncorr = float(p.get("ncorr", 0.0))
        i_scale = max(float(p.get("i_scale", 1.0)), 1e-12)
        x[i, 0] = 1.0 - p_peakpos
        x[i, 1] = 1.0 - p_intensity
        x[i, 2] = 1.0 - p_npeaks
        x[i, 3] = 1.0 - p_ncorr
        x[i, 4] = abs(math.log(i_scale))
        y[i] = float(r.get("fom", 0.0))
    return x, y


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def compute_r2_kendall(
    baseline: dict[str, Any],
    weights: dict[str, float],
) -> tuple[float, float, float]:
    """Compute R², Kendall τ, RMSE for *weights* against the baseline.

    R² measures how well the weighted FoM reproduces the observed FoM;
    Kendall τ measures rank correlation (the L3 acceptance criterion).
    """
    x, y = _extract_p_and_fom(baseline)
    if x.shape[0] == 0:
        return 0.0, 0.0, 0.0

    # Predicted FoM = 1 - x @ w
    w_vec = np.array(
        [weights[k] for k in P_KEYS], dtype=np.float64
    )
    y_pred = 1.0 - x @ w_vec

    # R²
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # RMSE
    rmse = float(np.sqrt(ss_res / len(y)))

    # Kendall τ (rank correlation of predicted vs observed).
    if len(y) > 1:
        tau, _ = kendalltau(y_pred, y)
        tau = float(tau) if not math.isnan(tau) else 0.0
    else:
        tau = 0.0

    return r2, tau, rmse


# --------------------------------------------------------------------------- #
# NNLS fit
# --------------------------------------------------------------------------- #
def fit_weights_nnls(
    baseline: dict[str, Any],
) -> dict[str, float]:
    """Recover the optimal weights via non-negative least squares.

    Solves::

        min || y - (1 - x @ w) ||²  s.t.  w ≥ 0

    equivalent to::

        min || (1 - y) - x @ w ||²  s.t.  w ≥ 0

    which is the same formulation used by ``tools/build_baseline.py``
    to obtain the published weights.
    """
    x, y = _extract_p_and_fom(baseline)
    if x.shape[0] == 0:
        return dict(PUBLISHED_WEIGHTS)

    # Target: 1 - y (so the LSQ finds w such that x @ w ≈ 1 - y).
    target = 1.0 - y
    w_vec, _ = nnls(x, target, maxiter=10 * x.shape[1])
    return {k: float(w_vec[i]) for i, k in enumerate(P_KEYS)}


# --------------------------------------------------------------------------- #
# Grid-search refinement
# --------------------------------------------------------------------------- #
def grid_search_refine(
    baseline: dict[str, Any],
    base_weights: dict[str, float],
    *,
    step: float = 0.005,
    n_steps: int = 3,
) -> dict[str, float]:
    """Small grid search around *base_weights*.

    Probes ``n_steps`` values above and below each weight (step size
    *step*), greedily picking the weight that maximises R².  The
    search is **not** a full Cartesian product (5 weights × 2*n_steps+1
    values each = 7⁵ ≈ 16k combos); instead it does coordinate ascent
    (5 * (2*n_steps+1) ≈ 35 evaluations per pass, 3 passes).

    Returns
    -------
    dict[str, float]
        The best-weight dict found.  Identical to *base_weights* when
        no neighbour improves R².
    """
    x, y = _extract_p_and_fom(baseline)
    if x.shape[0] == 0:
        return dict(base_weights)

    best_w = dict(base_weights)
    _, best_r2, _ = compute_r2_kendall(baseline, best_w)

    # Coordinate ascent: cycle through each weight, try ±n_steps*step.
    for _pass in range(3):
        improved = False
        for key in P_KEYS:
            current = best_w[key]
            for delta in (
                -n_steps * step, -(n_steps - 1) * step, -step, 0.0,
                step, (n_steps - 1) * step, n_steps * step,
            ):
                cand = max(0.0, current + delta)
                trial = dict(best_w)
                trial[key] = cand
                _, r2, _ = compute_r2_kendall(baseline, trial)
                if r2 > best_r2 + 1e-9:
                    best_r2 = r2
                    best_w[key] = cand
                    improved = True
        if not improved:
            break

    return best_w


# --------------------------------------------------------------------------- #
# Main tuning pipeline
# --------------------------------------------------------------------------- #
def run_tuning(
    json_path: Path | None = None,
    *,
    grid_step: float = 0.005,
    grid_n_steps: int = 3,
) -> TuneReport:
    """Run the full weight-tuning pipeline.

    Steps:

    1. Load (or generate) the baseline.
    2. Score the published weights (R², Kendall τ).
    3. NNLS-refit the weights; score.
    4. Grid-search refinement around the NNLS fit; score.
    5. Decide: ``KEEP`` (no improvement beyond published) or ``UPDATE``
       (NNLS or grid improves R² by ≥ 1e-4).
    """
    baseline, source = load_or_generate_baseline(json_path)
    report = TuneReport(
        n_candidates=int(baseline.get("n_candidates", 0)),
        n_samples=int(baseline.get("n_samples", 0)),
        source=source,
    )

    # Published weights.
    pub_r2, pub_tau, pub_rmse = compute_r2_kendall(baseline, PUBLISHED_WEIGHTS)
    report.published = WeightSet(
        name="published",
        weights=dict(PUBLISHED_WEIGHTS),
        r_squared=pub_r2,
        kendall_tau=pub_tau,
        rmse=pub_rmse,
    )

    # NNLS fit.
    nnls_w = fit_weights_nnls(baseline)
    nnls_r2, nnls_tau, nnls_rmse = compute_r2_kendall(baseline, nnls_w)
    report.nnls_fit = WeightSet(
        name="nnls",
        weights=nnls_w,
        r_squared=nnls_r2,
        kendall_tau=nnls_tau,
        rmse=nnls_rmse,
    )

    # Grid refinement around the NNLS fit.
    grid_w = grid_search_refine(
        baseline, nnls_w, step=grid_step, n_steps=grid_n_steps
    )
    grid_r2, grid_tau, grid_rmse = compute_r2_kendall(baseline, grid_w)
    report.grid_refined = WeightSet(
        name="grid_refined",
        weights=grid_w,
        r_squared=grid_r2,
        kendall_tau=grid_tau,
        rmse=grid_rmse,
    )

    # Recommendation: UPDATE only if grid or NNLS beats published by ≥ 1e-4.
    best_r2 = max(nnls_r2, grid_r2)
    if best_r2 > pub_r2 + 1e-4:
        report.recommendation = "UPDATE"
        report.notes.append(
            f"NNLS+grid improves R² from {pub_r2:.4f} to {best_r2:.4f}."
        )
    else:
        report.recommendation = "KEEP"
        report.notes.append(
            f"Published weights already optimal within search range "
            f"(R² {pub_r2:.4f} ≥ NNLS {nnls_r2:.4f} / grid {grid_r2:.4f} − 1e-4)."
        )

    if source == "synthetic":
        report.notes.append(
            "WARNING: baseline.json not found; results are from a "
            "synthetic baseline generated from the published weights. "
            "Place real reference-software CSV exports in tests/baseline/ and "
            "re-run for a meaningful tuning."
        )

    return report


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _format_weights(w: dict[str, float]) -> str:
    return (
        f"peakpos={w['peakpos']:.4f}  intensity={w['intensity']:.4f}  "
        f"npeaks={w['npeaks']:.4f}  ncorr={w['ncorr']:.4f}  "
        f"i_scale={w['i_scale']:.4f}"
    )


def _format_report(report: TuneReport) -> str:
    lines: list[str] = []
    lines.append(
        f"Weight tuning report  (n={report.n_candidates} candidates, "
        f"{report.n_samples} samples, source={report.source})"
    )
    lines.append("")
    for ws in (report.published, report.nnls_fit, report.grid_refined):
        if ws is None:
            continue
        lines.append(
            f"  {ws.name:14s}  R²={ws.r_squared:.4f}  "
            f"τ={ws.kendall_tau:.4f}  RMSE={ws.rmse:.4f}"
        )
        lines.append(f"    {_format_weights(ws.weights)}")
    lines.append("")
    lines.append(f"Recommendation: {report.recommendation}")
    for note in report.notes:
        lines.append(f"  - {note}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m tools.tune_weights``."""
    parser = argparse.ArgumentParser(
        description="Tune FoM weights against the reference software baseline (T6.10)."
    )
    parser.add_argument(
        "--baseline", type=Path, default=None,
        help="Path to baseline.json (default: tests/baseline/baseline.json).",
    )
    parser.add_argument("--grid-step", type=float, default=0.005)
    parser.add_argument("--grid-n-steps", type=int, default=3)
    parser.add_argument(
        "--json", type=Path, default=None,
        help="Write the structured report as JSON to this path.",
    )
    args = parser.parse_args(argv)

    report = run_tuning(
        json_path=args.baseline,
        grid_step=args.grid_step,
        grid_n_steps=args.grid_n_steps,
    )

    print(_format_report(report))
    if args.json is not None:
        args.json.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nJSON report written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
