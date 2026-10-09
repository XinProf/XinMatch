"""T13.4 — tests for the 118-element periodic-table selector (offscreen)."""

from __future__ import annotations

from xinmatch.core.model.restraints import ElementState
from xinmatch.ui.periodic_table import PeriodicTableWidget


def test_all_118_buttons_present(qapp):
    w = PeriodicTableWidget()
    assert len(w._buttons) == 118


def test_click_cycles_through_three_states(qapp):
    w = PeriodicTableWidget()
    # Default is OPTIONAL; cycle: optional -> required -> excluded -> optional.
    w._cycle("O")
    assert w._states["O"] == ElementState.REQUIRED
    w._cycle("O")
    assert w._states["O"] == ElementState.EXCLUDE
    w._cycle("O")
    assert w._states["O"] == ElementState.OPTIONAL


def test_state_changed_signal_emitted(qapp):
    w = PeriodicTableWidget()
    caught: list[tuple[str, ElementState]] = []
    w.state_changed.connect(lambda s, st: caught.append((s, st)))
    w._cycle("Fe")
    assert ("Fe", ElementState.REQUIRED) in caught


def test_states_only_returns_active(qapp):
    w = PeriodicTableWidget()
    w.set_states({"O": ElementState.REQUIRED, "Fe": ElementState.EXCLUDE})
    s = w.states()
    assert s == {"O": ElementState.REQUIRED, "Fe": ElementState.EXCLUDE}


def test_set_states_roundtrip(qapp):
    w = PeriodicTableWidget()
    wanted = {"Cu": "green", "Pb": "red"}
    w.set_states(wanted)
    out = w.states()
    assert out["Cu"] == ElementState.REQUIRED
    assert out["Pb"] == ElementState.EXCLUDE
    # Round-trip: build a fresh widget, apply the same states, equal result.
    w2 = PeriodicTableWidget()
    w2.set_states(out)
    assert w2.states() == out


def test_toggle_disables_buttons_but_keeps_states(qapp):
    w = PeriodicTableWidget()
    w.set_states({"Si": ElementState.REQUIRED})
    w.set_enabled(False)
    assert not w.is_enabled()
    # Buttons disabled yet states retained.
    assert not w._buttons["Si"].isEnabled()
    assert w.states() == {"Si": ElementState.REQUIRED}
    w.set_enabled(True)
    assert w._buttons["Si"].isEnabled()


def test_reset_clears_all(qapp):
    w = PeriodicTableWidget()
    w.set_states({"H": ElementState.EXCLUDE, "C": ElementState.REQUIRED})
    w.reset()
    assert w.states() == {}
