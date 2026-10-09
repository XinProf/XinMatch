"""3D crystal-structure viewer (Phase 16).

Renders a crystal structure with :class:`~PySide6.QtWebEngineWidgets.QWebEngineView`
plus **locally bundled** 3Dmol.js (no external CDN at runtime).

Data pipeline
-------------
CIF → viewer-ready data is split into GUI-free pure functions so they can be
unit-tested offscreen:

* :func:`ref_id_to_cod_id` — XinMatch entry id (PolyXRD ``ref_id``, e.g.
  ``"96-400-1849"``) → numeric COD id.  The mapping is arithmetic: the middle
  and last ``-``-separated groups concatenate (verified against the full
  522 K-row PolyXRD dump: 0 mismatches).
* :func:`cod_cif_path` — numeric COD id → ``{d}/{dd}/{dd}/{id:07d}.cif`` path
  inside the local COD CIF archive (layout verified on disk).
* :func:`cif_to_structure_data` — parse a CIF with gemmi 0.7.5 into a plain
  dict (cell / formula / space group / atom count / raw CIF text) that the
  HTML template injects into 3Dmol.

CIF sources
-----------
1. Refined CIFs produced by ``core.refine.gsas2_project`` (``*_new.cif``) —
   callers pass the path directly to :meth:`StructureViewDialog.load_cif`.
2. COD archive lookup by entry id — :meth:`StructureViewDialog.load_entry`.

The local COD archive is treated as read-only; this module never writes there.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtWebEngineWidgets, QtWidgets

__all__ = [
    "ASSETS_DIR",
    "DEFAULT_COD_ROOT",
    "THREEMOL_VERSION",
    "THREEMOL_SOURCE_URL",
    "StructureViewDialog",
    "cif_to_structure_data",
    "cod_cif_path",
    "ref_id_to_cod_id",
    "render_html",
    "resolve_entry_cif",
]

#: Directory holding the bundled 3Dmol.js and the HTML template.
ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "3dmol"

#: Local COD CIF archive root (read-only; 522 K files).
DEFAULT_COD_ROOT = Path(r"D:\Project\XRD\PolyXRD\cod\cif")

#: Bundled 3Dmol.js version and the URL it was downloaded from (build-time
#: fetch only — the HTML references the local ``3Dmol-min.js``, never a CDN).
THREEMOL_VERSION = "2.5.5"
THREEMOL_SOURCE_URL = (
    "https://cdn.jsdelivr.net/npm/3dmol@2.5.5/build/3Dmol-min.js"
)

# Placeholder in ``structure_view.html`` replaced by the embedded structure JSON.
_JSON_TOKEN = "__XINMATCH_STRUCTURE_JSON__"


# ---------------------------------------------------------------------------
# Pure path / id helpers (GUI-free, unit-tested offscreen)
# ---------------------------------------------------------------------------
def ref_id_to_cod_id(ref_id: str) -> int:
    """Convert a XinMatch entry id (PolyXRD ``ref_id``) to a numeric COD id.

    ``"96-100-0005"`` → ``1000005``.  Raises :class:`ValueError` when the id
    is not in the ``NN-NNN-NNNN`` ref_id shape.
    """
    parts = ref_id.strip().split("-")
    if len(parts) != 3 or not (parts[1] + parts[2]).isdigit():
        raise ValueError(
            f"not a PolyXRD ref_id: {ref_id!r} (expected e.g. '96-400-1849')"
        )
    return int(parts[1] + parts[2])


def cod_cif_path(cod_id: int, root: str | Path = DEFAULT_COD_ROOT) -> Path:
    """Numeric COD id → CIF path under the archive *root*.

    Layout (verified on the real archive): the 7-digit-zero-padded id is split
    as ``{first}/{next two}/{next two}/{id:07d}.cif`` — e.g. id ``1000005``
    → ``1/00/00/1000005.cif``.
    """
    s = str(int(cod_id)).zfill(7)
    return Path(root) / s[0] / s[1:3] / s[3:5] / f"{s}.cif"


def resolve_entry_cif(
    entry_id: str, root: str | Path = DEFAULT_COD_ROOT
) -> Path | None:
    """Resolve a XinMatch entry id to an existing COD CIF, or ``None``."""
    try:
        path = cod_cif_path(ref_id_to_cod_id(entry_id), root)
    except ValueError:
        return None
    return path if path.is_file() else None


# ---------------------------------------------------------------------------
# CIF → viewer data (gemmi, GUI-free)
# ---------------------------------------------------------------------------
def _cif_scalar(block: Any, tag: str) -> str | None:
    """Best-effort scalar tag read from a gemmi CIF block."""
    try:
        value = block.find_value(tag)
    except Exception:  # noqa: BLE001 - gemmi raises on malformed blocks
        return None
    if value is None:
        return None
    text = str(value).strip().strip("'\"")
    return text or None


_ESD_RE = re.compile(r"\(\d+\)$")


def _cif_float(block: Any, tag: str, default: float | None = None) -> float | None:
    """Read a numeric CIF scalar, stripping parenthesized esds (``11.217(2)``)."""
    text = _cif_scalar(block, tag)
    if text is None:
        return default
    text = _ESD_RE.sub("", text).strip()
    try:
        return float(text)
    except ValueError:
        return default


def _count_atom_rows(block: Any) -> int:
    """Count asymmetric-unit atom rows in the CIF ``_atom_site_`` loop."""
    for tag in (
        "_atom_site_label",
        "_atom_site_type_symbol",
        "_atom_site_Wyckoff_label",
    ):
        try:
            rows = block.find_loop(tag)
        except Exception:  # noqa: BLE001
            continue
        n = len(rows)
        if n:
            return n
    return 0


def cif_to_structure_data(cif_path: str | Path) -> dict[str, Any]:
    """Parse a CIF with gemmi into a JSON-serialisable dict.

    Returns
    -------
    dict
        Keys: ``title``, ``formula``, ``space_group``, ``cell``
        (``a/b/c/alpha/beta/gamma``), ``n_atoms`` (asymmetric-unit atoms),
        ``cif_text`` (verbatim file content, handed to 3Dmol's CIF parser),
        ``source_path``.
    """
    import gemmi  # local import: keeps module import light in pure-unit tests

    path = Path(cif_path)
    cif_text = path.read_text(encoding="utf-8", errors="replace")

    block = gemmi.cif.read(path.as_posix()).sole_block()
    # gemmi's read_structure leaves a default cell on these powder CIFs, so
    # read cell / space-group scalars straight from the CIF tags.
    cell = {
        "a": _cif_float(block, "_cell_length_a", 1.0),
        "b": _cif_float(block, "_cell_length_b", 1.0),
        "c": _cif_float(block, "_cell_length_c", 1.0),
        "alpha": _cif_float(block, "_cell_angle_alpha", 90.0),
        "beta": _cif_float(block, "_cell_angle_beta", 90.0),
        "gamma": _cif_float(block, "_cell_angle_gamma", 90.0),
    }

    n_atoms = _count_atom_rows(block)
    formula = (
        _cif_scalar(block, "_chemical_formula_sum")
        or _cif_scalar(block, "_chemical_formula_moiety")
        or ""
    )
    space_group = (
        _cif_scalar(block, "_symmetry_space_group_name_H-M")
        or _cif_scalar(block, "_space_group_name_H-M_alt")
        or ""
    )
    title = (
        _cif_scalar(block, "_chemical_name_common")
        or path.stem
    )

    return {
        "title": title,
        "formula": formula,
        "space_group": space_group,
        "cell": cell,
        "n_atoms": n_atoms,
        "cif_text": cif_text,
        "source_path": str(path),
    }


# ---------------------------------------------------------------------------
# HTML rendering (pure)
# ---------------------------------------------------------------------------
def render_html(data: dict[str, Any] | None, message: str = "") -> str:
    """Inject *data* into the local HTML template and return full HTML.

    ``None`` renders an empty-state page with *message*.  The returned
    HTML never references an external URL: 3Dmol.js is loaded from the local
    bundle via a relative ``<script src>`` resolved against the template
    directory.
    """
    template = (ASSETS_DIR / "structure_view.html").read_text(encoding="utf-8")
    payload: dict[str, Any]
    if data is None:
        payload = {"empty": True, "message": message}
    else:
        payload = {
            "empty": False,
            "title": data.get("title", ""),
            "formula": data.get("formula", ""),
            "space_group": data.get("space_group", ""),
            "cell": data.get("cell", {}),
            "n_atoms": data.get("n_atoms", 0),
            "cif_text": data.get("cif_text", ""),
        }
    # Escape '<' so an injected CIF can never close the <script> tag.
    encoded = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    return template.replace(_JSON_TOKEN, encoded)


# ---------------------------------------------------------------------------
# Dialog widget
# ---------------------------------------------------------------------------
class StructureViewDialog(QtWidgets.QDialog):
    """Modal-ish dialog hosting the 3Dmol.js viewer.

    Public loading methods return ``True`` on success and ``False`` (with a
    friendly placeholder page shown) when the CIF cannot be located/parsed —
    the dialog never raises into the caller on bad input.
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("3D 结构视图")
        self.resize(960, 720)

        self._current: dict[str, Any] | None = None

        layout = QtWidgets.QVBoxLayout(self)

        self._info = QtWidgets.QLabel("尚未加载结构。")
        self._info.setStyleSheet("color: #444; padding: 2px;")
        layout.addWidget(self._info)

        self._web = QtWebEngineWidgets.QWebEngineView(self)
        layout.addWidget(self._web, 1)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addStretch()
        btn_close = QtWidgets.QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        button_row.addWidget(btn_close)
        layout.addLayout(button_row)

        self._show_empty("未选择物相或 CIF。")

    # ------------------------------------------------------------------
    # Loading API
    # ------------------------------------------------------------------
    def current_data(self) -> dict[str, Any] | None:
        """Return the structure data currently shown, or ``None``."""
        return self._current

    def load_cif(self, cif_path: str | Path) -> bool:
        """Load a CIF file directly (e.g. a refined ``*_new.cif``)."""
        try:
            data = cif_to_structure_data(cif_path)
        except Exception as exc:  # noqa: BLE001 - user-facing fallback
            self._show_empty(f"CIF 解析失败：{exc}")
            return False
        self._current = data
        self._web.setHtml(
            render_html(data),
            QtCore.QUrl.fromLocalFile((ASSETS_DIR / "structure_view.html").as_posix()),
        )
        cell = data["cell"]
        self._info.setText(
            f"{data['title']}　{data['formula']}　"
            f"空间群 {data['space_group'] or '—'}　"
            f"a={cell['a']:.4f} c={cell['c']:.4f} Å　"
            f"ASU 原子数 {data['n_atoms']}"
        )
        return True

    def load_entry(
        self,
        entry_id: str,
        root: str | Path = DEFAULT_COD_ROOT,
    ) -> bool:
        """Resolve a XinMatch entry id against the local COD archive and load it."""
        cif = resolve_entry_cif(entry_id, root)
        if cif is None:
            self._show_empty(
                f"未找到条目 {entry_id} 的 CIF（本地 COD 归档中不存在或 id 格式不识别）。"
            )
            return False
        return self.load_cif(cif)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _show_empty(self, message: str) -> None:
        self._current = None
        self._info.setText(message)
        self._web.setHtml(
            render_html(None, message),
            QtCore.QUrl.fromLocalFile((ASSETS_DIR / "structure_view.html").as_posix()),
        )
