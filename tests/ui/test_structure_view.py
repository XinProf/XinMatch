"""Tests for the 3D structure viewer (Phase 16).

Runs with ``QT_QPA_PLATFORM=offscreen`` (set in ``conftest.py``).  The pure
CIF→data conversion functions need no QApplication; the widget tests use the
session ``qapp`` fixture and never rely on real WebEngine rendering.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from xinmatch.ui import structure_view as sv

_FIX = Path(__file__).resolve().parent.parent / "fixtures" / "gsas2_project"
_ZNO = _FIX / "ZnO.cif"


# ---------------------------------------------------------------------------
# Pure id / path helpers
# ---------------------------------------------------------------------------
class TestIdHelpers:
    def test_ref_id_to_cod_id(self):
        assert sv.ref_id_to_cod_id("96-100-0005") == 1000005
        assert sv.ref_id_to_cod_id("96-400-1849") == 4001849

    def test_ref_id_invalid(self):
        with pytest.raises(ValueError):
            sv.ref_id_to_cod_id("garbage")
        with pytest.raises(ValueError):
            sv.ref_id_to_cod_id("12-34")

    def test_cod_cif_path_layout(self):
        p = sv.cod_cif_path(1000005, root="X")
        assert p == Path("X") / "1" / "00" / "00" / "1000005.cif"
        # zero-padding to 7 digits
        p2 = sv.cod_cif_path(42, root="X")
        assert p2.name == "0000042.cif"

    def test_resolve_entry_cif_fake_root(self, tmp_path):
        # Build the expected archive layout under tmp_path.
        target = tmp_path / "1" / "00" / "00" / "1000005.cif"
        target.parent.mkdir(parents=True)
        target.write_text("data_test\n", encoding="utf-8")
        found = sv.resolve_entry_cif("96-100-0005", root=tmp_path)
        assert found == target

    def test_resolve_entry_cif_missing(self, tmp_path):
        assert sv.resolve_entry_cif("96-100-0005", root=tmp_path) is None
        assert sv.resolve_entry_cif("not-an-id", root=tmp_path) is None


# ---------------------------------------------------------------------------
# CIF → structure data (gemmi)
# ---------------------------------------------------------------------------
class TestCifConversion:
    def test_zno_fixture(self):
        data = sv.cif_to_structure_data(_ZNO)
        assert data["formula"] == "O Zn"
        assert data["space_group"] == "P 63 m c"
        assert data["cell"]["a"] == pytest.approx(3.2494)
        assert data["cell"]["c"] == pytest.approx(5.2054)
        assert data["cell"]["gamma"] == pytest.approx(120.0)
        assert data["n_atoms"] == 2  # Zn + O in the asymmetric unit
        assert "_atom_site" in data["cif_text"]

    def test_esd_suffix_stripped(self, tmp_path):
        cif = tmp_path / "esd.cif"
        cif.write_text(
            "data_x\n"
            "_cell_length_a 11.217(2)\n"
            "_cell_length_b 8.1775(15)\n"
            "_cell_length_c 19.887(4)\n"
            "_symmetry_space_group_name_H-M 'P 1 21/n 1'\n"
            "loop_\n_atom_site_label\n'Zn'\n",
            encoding="utf-8",
        )
        data = sv.cif_to_structure_data(cif)
        assert data["cell"]["a"] == pytest.approx(11.217)
        assert data["cell"]["b"] == pytest.approx(8.1775)
        assert data["n_atoms"] == 1


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------
class TestRenderHtml:
    def test_no_external_urls(self):
        data = sv.cif_to_structure_data(_ZNO)
        html = sv.render_html(data)
        # 3Dmol must be referenced locally, never via CDN.
        assert "3Dmol-min.js" in html
        assert not re.search(r"https?://", html)

    def test_injects_cif_text(self):
        data = sv.cif_to_structure_data(_ZNO)
        html = sv.render_html(data)
        assert "P 63 m c" in html

    def test_empty_state(self):
        html = sv.render_html(None, "nothing here")
        assert "nothing here" in html
        assert "3Dmol-min.js" in html


# ---------------------------------------------------------------------------
# Widget construction (offscreen; no real WebEngine render required)
# ---------------------------------------------------------------------------
class TestStructureViewDialog:
    def test_constructs(self, qapp):
        dlg = sv.StructureViewDialog()
        assert dlg.current_data() is None
        dlg.close()

    def test_load_cif_fixture(self, qapp):
        dlg = sv.StructureViewDialog()
        ok = dlg.load_cif(_ZNO)
        assert ok is True
        assert dlg.current_data() is not None
        assert dlg.current_data()["formula"] == "O Zn"
        dlg.close()

    def test_load_cif_bogus(self, qapp):
        dlg = sv.StructureViewDialog()
        ok = dlg.load_cif(Path("no/such/file.cif"))
        assert ok is False
        assert dlg.current_data() is None
        dlg.close()

    def test_load_entry_fake_root(self, qapp, tmp_path):
        dlg = sv.StructureViewDialog()
        # No CIF under this root -> friendly failure, no exception.
        ok = dlg.load_entry("96-100-0005", root=tmp_path)
        assert ok is False
        dlg.close()
