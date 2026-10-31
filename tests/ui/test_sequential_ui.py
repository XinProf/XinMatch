"""Offscreen tests for the v3.1.0 sequential phase-identification UI.

The workflow under test (all in :class:`~xinmatch.ui.main_window.MainWindow`):

    整谱检索 → 候选列表 → 选中/双击确认一相 → 剩余峰再检索 → 再确认 → …

The reference database is never touched: ``search_residual`` is stubbed at the
module boundary and ``open_search_library`` returns a dummy handle, so the
tests exercise the GUI wiring (state machine, three views, buttons) only.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

import numpy as np
import pytest
from PySide6 import QtWidgets

from xinmatch.core.model import Entry, Pattern, Peak
from xinmatch.core.search.fom import CandidateResult
from xinmatch.core.search.sequential import ResidualSearchResult
from xinmatch.ui import main_window as mw

WL = 1.5406

A_D = (3.0, 2.0, 1.5)
A_I = (100.0, 50.0, 25.0)
B_D = (2.6, 1.8, 1.3)
B_I = (100.0, 60.0, 30.0)


def _two_theta(d: float) -> float:
    return float(2.0 * np.degrees(np.arcsin(WL / (2.0 * d))))


def _entry(entry_id: str, ds, intensities) -> Entry:
    return Entry(
        entry_id=entry_id,
        formula=entry_id,
        d_spacings=np.array(ds, dtype=np.float64),
        intensities=np.array(intensities, dtype=np.float64),
    )


def _peaks() -> list[Peak]:
    peaks = [
        Peak(two_theta=_two_theta(d), intensity=i * 10.0)
        for d, i in zip(A_D, A_I, strict=True)
    ]
    peaks += [
        Peak(two_theta=_two_theta(d), intensity=i * 3.0)
        for d, i in zip(B_D, B_I, strict=True)
    ]
    peaks.sort(key=lambda p: p.two_theta)
    return peaks


class _Conn:
    """Stand-in reference-DB handle (only ``close`` is used)."""

    def __init__(self) -> None:
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


@pytest.fixture
def harness(qapp, monkeypatch):
    """Window + stubbed residual search; returns a small record object."""
    entry_a = _entry("A", A_D, A_I)
    entry_b = _entry("B", B_D, B_I)
    peaks = _peaks()
    conn = _Conn()
    calls: list[int] = []
    follow_up = {"candidates": [CandidateResult(entry=entry_b, fom=0.71)]}

    def fake_search_residual(seq, connection, **kwargs):
        calls.append(seq.n_residual_peaks)
        return ResidualSearchResult(
            candidates=list(follow_up["candidates"]),
            n_residual_peaks=seq.n_residual_peaks,
            n_explained=seq.n_explained,
            covered_fraction=seq.covered_fraction,
        )

    monkeypatch.setattr(mw, "search_residual", fake_search_residual)

    win = mw.MainWindow()
    win.set_pattern(Pattern(np.linspace(10.0, 80.0, 3500), np.ones(3500), wavelength=WL))
    win.open_search_library = lambda: conn  # type: ignore[method-assign]
    win._start_sequential(peaks)
    win.set_candidates(
        [
            CandidateResult(entry=entry_a, fom=0.92),
            CandidateResult(entry=entry_b, fom=0.55),
        ]
    )

    return SimpleNamespace(
        window=win,
        calls=calls,          # live list — records every residual search
        follow_up=follow_up,  # mutable: next residual-search answer
        connection=conn,
    )


# --------------------------------------------------------------------------- #
# Confirm → residual search → match list
# --------------------------------------------------------------------------- #
def test_confirm_adds_phase_and_searches_residual(harness):
    win = harness.window
    assert len(win.matched_phases()) == 0
    assert win.match_table.model().rowCount() == 0

    win.confirm_candidate("A")

    phases = win.matched_phases()
    assert [p.entry.entry_id for p in phases] == ["A"]
    assert win.match_table.model().rowCount() == 1
    # Residual search ran once on the 3 unexplained peaks, then the candidate
    # list was replaced by its answer.
    assert harness.calls == [3]
    assert [c.entry.entry_id for c in win._candidates] == ["B"]
    assert "剩余 3/6 峰" in win.residual_label.text()
    assert harness.connection.closed == 1


def test_confirm_is_idempotent(harness):
    win = harness.window
    win.confirm_candidate("A")
    win.confirm_candidate("A")
    assert len(win.matched_phases()) == 1
    assert harness.calls == [3]  # second confirm did not re-search


def test_peak_table_marks_explained_peaks(harness):
    win = harness.window
    win.confirm_candidate("A")
    flags = [p.correlated for p in win._exp_peaks]
    assert flags.count(True) == 3
    assert win.peak_table.model().rowCount() == len(win._exp_peaks)


def test_reference_sticks_follow_confirmed_phases(harness):
    win = harness.window
    assert win.pattern_view.stick_count() == 0
    win.confirm_candidate("A")
    assert win.pattern_view.stick_count() == 1
    win.confirm_candidate("B")
    assert win.pattern_view.stick_count() == 2
    win.undo_last_phase()
    assert win.pattern_view.stick_count() == 1


def test_confirm_via_candidate_table_signal(harness):
    """Double-click / Enter path: the table signal must reach the window."""
    win = harness.window
    win.candidate_table.candidate_activated.emit("A")
    assert [p.entry.entry_id for p in win.matched_phases()] == ["A"]


def test_confirm_button_uses_highlighted_row(harness):
    win = harness.window
    win.candidate_table.selectRow(0)  # FoM descending → row 0 is A
    win.confirm_selected_candidate()
    assert [p.entry.entry_id for p in win.matched_phases()] == ["A"]


def test_confirm_second_phase_explains_everything(harness):
    win = harness.window
    win.confirm_candidate("A")
    harness.follow_up["candidates"] = []  # nothing left to report
    win.confirm_candidate("B")
    assert len(win.matched_phases()) == 2
    assert "无剩余待解释峰" in win.residual_label.text()
    assert win._candidates == []
    # The residual round is skipped when nothing is left; the last recorded
    # call is still the 3-peak one.
    assert harness.calls == [3]


# --------------------------------------------------------------------------- #
# Undo / remove / clear
# --------------------------------------------------------------------------- #
def test_undo_last_phase(harness):
    win = harness.window
    win.confirm_candidate("A")
    win.undo_last_phase()
    assert win.matched_phases() == []
    assert win.match_table.model().rowCount() == 0
    assert "剩余 6/6 峰" in win.residual_label.text()
    assert harness.calls == [3, 6]


def test_remove_matched_phase_by_id(harness):
    win = harness.window
    win.confirm_candidate("A")
    win.remove_matched_phase("A")
    assert win.matched_phases() == []
    assert harness.calls == [3, 6]


def test_clear_matched_phases(harness):
    win = harness.window
    win.confirm_candidate("A")
    win.clear_matched_phases()
    assert win.matched_phases() == []
    assert "已确认 0 相" in win.residual_label.text()
    # Peak list is untouched by clearing.
    assert win.peak_table.model().rowCount() == len(win._exp_peaks)


def test_undo_with_empty_match_list_is_noop(harness):
    win = harness.window
    win.undo_last_phase()
    assert win.matched_phases() == []
    assert harness.calls == []


# --------------------------------------------------------------------------- #
# Guards and interactions with the ordinary search path
# --------------------------------------------------------------------------- #
def test_confirm_without_pattern_or_peaks_informs(qapp, monkeypatch):
    win = mw.MainWindow()
    win._candidates = [CandidateResult(entry=_entry("A", A_D, A_I), fom=0.9)]
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information",
        lambda *args, **kwargs: shown.append(str(args[1])),
    )
    win.confirm_candidate("A")
    assert shown, "无数据/无峰时必须提示，而不是静默失败"
    assert win.matched_phases() == []


def test_confirm_unknown_entry_is_ignored(harness):
    win = harness.window
    win.confirm_candidate("NOT-IN-LIST")
    assert win.matched_phases() == []
    assert harness.calls == []


def test_full_search_resets_sequential_state(harness):
    """A new whole-pattern search starts a new analysis (phases cleared)."""
    win = harness.window
    win.confirm_candidate("A")
    assert len(win.matched_phases()) == 1

    peaks = _peaks()
    win._apply_search_results(
        ([CandidateResult(entry=_entry("A", A_D, A_I), fom=0.9)], "峰列表 FoM", peaks)
    )

    assert win.matched_phases() == []
    assert win.match_table.model().rowCount() == 0
    assert win.pattern_view.stick_count() == 0
    assert win.peak_table.model().rowCount() == len(peaks)
    assert "已确认 0 相" in win.residual_label.text()


def test_buttons_reflect_state(harness):
    win = harness.window
    assert win.undo_phase_button.isEnabled() is False
    assert win.clear_phases_button.isEnabled() is False
    assert win.confirm_phase_button.isEnabled() is True
    win.confirm_candidate("A")
    assert win.undo_phase_button.isEnabled() is True
    assert win.clear_phases_button.isEnabled() is True


def test_loading_new_pattern_resets_sequential(harness):
    """换数据必须作废上一轮的峰/候选/已确认相，否则会拿旧峰继续算。"""
    win = harness.window
    win.confirm_candidate("A")
    assert len(win.matched_phases()) == 1

    fresh = Pattern(np.linspace(10.0, 80.0, 500), np.ones(500), wavelength=WL)
    win._apply_loaded_pattern(fresh, "another_sample.txt")

    assert win.matched_phases() == []
    assert win.match_table.model().rowCount() == 0
    assert win.pattern_view.stick_count() == 0
    assert win._candidates == []
    assert win.peak_table.model().rowCount() == 0
    assert win.residual_label.text() == "尚未检索"


def test_duplicate_card_is_flagged_as_low_gain(harness):
    """A second card of the same phase explains nothing new → warn the user."""
    win = harness.window
    win.confirm_candidate("A")
    duplicate = CandidateResult(entry=_entry("A-dup", A_D, A_I), fom=0.5)
    win._candidates = [duplicate]
    win.candidate_table.set_candidates([duplicate])

    win.confirm_candidate("A-dup")

    assert len(win.matched_phases()) == 2
    assert "几乎未解释新峰" in win.statusBar().currentMessage()
