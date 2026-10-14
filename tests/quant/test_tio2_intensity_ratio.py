"""T0.3/T0.4: TiO2 rutile/anatase intensity-ratio quantification.

Real-data end-to-end on the GB/T 30893-2014 standard-sample series
(Shimadzu XRD-7000, CuKa, 24-29 deg local scans + full profiles).
Skipped when the external data directory is not present.

Method: Spurr-Myers style calibration K fitted on 6 standards
(5/10/15/20/30/50 %), then w_rutile = K*Ir/Ia / (1 + K*Ir/Ia) using
net peak heights of A(101) ~25.30 and R(110) ~27.44.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.io import load_pattern
from xinmatch.core.preprocess.background import estimate_background, subtract_background
from xinmatch.core.preprocess.smoothing import smooth

_TIO2 = Path(r"D:\Project\XRD\XRData\TiO2")
_RAW = _TIO2 / "钛白粉原始测试数据"

_CAL = {
    "5%": _RAW / "建立曲线用" / "5percent24-29" / "5percent24-29.RAW",
    "10%": _RAW / "建立曲线用" / "10percent24-29" / "10percent24-29.RAW",
    "15%": _RAW / "建立曲线用" / "15percent24-29" / "15percent24-29.RAW",
    "20%": _RAW / "建立曲线用" / "20percent24-29" / "20percent24-29.RAW",
    "30%": _RAW / "建立曲线用" / "30percent24-29" / "30percent24-29.RAW",
    "50%": _RAW / "建立曲线用" / "50percent24-29" / "50percent24-29.RAW",
}
_VALID = {
    "8%": _RAW / "验证曲线用" / "8percent24-29" / "8percent24-29.RAW",
    "18%": _RAW / "验证曲线用" / "18percent24-29" / "18percent24-29.RAW",
    "36%": _RAW / "验证曲线用" / "36percent24-29" / "36percent24-29.RAW",
}
_REP = {
    "4%-A1": _RAW / "重复性验证" / "4percent24-29" / "4percent24-29.RAW",
    "4%-A2": _RAW / "重复性验证" / "4percent24-29-2" / "4percent24-29-2.RAW",
}
_FULL = {
    "8%": _TIO2 / "精修数据" / "8%测试谱.txt",
    "18%": _TIO2 / "精修数据" / "18%实测谱.txt",
    "36%": _TIO2 / "精修数据" / "36%实测谱.txt",
}

A101, R110 = 25.30, 27.44
_K_REF = 1.2234  # Shimadzu / docx calibration


def _net_peak_height(path: Path, center: float) -> float:
    pat = load_pattern(path)
    y = smooth(pat.intensity, window=9, polyorder=3)
    bkg = estimate_background(pat.two_theta, y, method="snip", window=20)
    y_net = subtract_background(y, bkg)
    m = (pat.two_theta >= center - 0.4) & (pat.two_theta <= center + 0.4)
    if not m.any():
        return 0.0
    return max(0.0, float(y_net[m].max()))


def _ratio(path: Path) -> float:
    ia = _net_peak_height(path, A101)
    ir = _net_peak_height(path, R110)
    return ir / ia if ia > 0 else float("nan")


def _w_rutile(k: float, ratio: float) -> float:
    return k * ratio / (1.0 + k * ratio)


@pytest.mark.skipif(not _RAW.exists(), reason="TiO2 data dir not present")
def test_calibration_k_matches_reference_order() -> None:
    """6 standard samples -> fitted K close to the Shimadzu reference (1.2234)."""
    pts = []
    for name, path in _CAL.items():
        ia = _net_peak_height(path, A101)
        ir = _net_peak_height(path, R110)
        mass_r = float(name.rstrip("%")) / 100.0
        pts.append((ir / ia, mass_r / (1.0 - mass_r)))
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    k = float(np.mean(ys / xs))
    # Same order of magnitude as the instrument calibration; our net-peak
    # height definition differs from the vendor's integrated-intensity one.
    assert 0.8 < k < 2.0
    assert abs(k - _K_REF) / _K_REF < 0.4


@pytest.mark.skipif(not _RAW.exists(), reason="TiO2 data dir not present")
def test_validation_predictions_within_3_abs() -> None:
    """Predictions on 8/18/36 % within +/-3 % absolute of certified values."""
    pts = []
    for name, path in _CAL.items():
        ia = _net_peak_height(path, A101)
        ir = _net_peak_height(path, R110)
        mass_r = float(name.rstrip("%")) / 100.0
        pts.append((ir / ia, mass_r / (1.0 - mass_r)))
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    k = float(np.mean(ys / xs))

    for name, path in _VALID.items():
        wr = _w_rutile(k, _ratio(path))
        certified = float(name.rstrip("%")) / 100.0
        assert abs(wr - certified) < 0.03, f"{name}: predicted {wr:.4f} vs {certified:.4f}"


@pytest.mark.skipif(not _RAW.exists(), reason="TiO2 data dir not present")
def test_repeatability_4pct() -> None:
    """Two 4 % runs agree within 0.5 % absolute."""
    pts = []
    for name, path in _CAL.items():
        ia = _net_peak_height(path, A101)
        ir = _net_peak_height(path, R110)
        mass_r = float(name.rstrip("%")) / 100.0
        pts.append((ir / ia, mass_r / (1.0 - mass_r)))
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    k = float(np.mean(ys / xs))

    vals = [_w_rutile(k, _ratio(path)) for path in _REP.values()]
    assert abs(vals[0] - vals[1]) < 0.005


@pytest.mark.skipif(not _TIO2.exists(), reason="TiO2 data dir not present")
def test_full_profile_path_consistent_with_local() -> None:
    """Full-profile scans give the same ratio as the local 24-29 scans."""
    pts = []
    for name, path in _CAL.items():
        ia = _net_peak_height(path, A101)
        ir = _net_peak_height(path, R110)
        mass_r = float(name.rstrip("%")) / 100.0
        pts.append((ir / ia, mass_r / (1.0 - mass_r)))
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    k = float(np.mean(ys / xs))

    for name in ("8%", "18%", "36%"):
        wr_local = _w_rutile(k, _ratio(_VALID[name]))
        wr_full = _w_rutile(k, _ratio(_FULL[name]))
        assert abs(wr_full - wr_local) < 0.01, f"{name}: full {wr_full:.4f} vs local {wr_local:.4f}"
