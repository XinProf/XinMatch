"""Prescreen family cap: at most *k* cards of one phase family per pool.

Family = the card's **three strongest reflections** quantised to the d-window
(:func:`xinmatch.core.db.reader_v3._family_keys`).  No metadata lookup is needed
— the prescreen already holds the ``top_d`` matrix.

The cap is **off by default**: measured 2026-11-05, it lifts pool recall on the
25 benchmark samples from 45/67 to 48/67 (cap 1) but cannot rescue the ``3-1``
minor phases, whose first same-phase cards sit at pool positions 2071 / 4262.
These tests pin the mechanism, not a default.
"""

from __future__ import annotations

import numpy as np

from xinmatch.core.db.reader_v3 import XinDBReader, _family_keys
from xinmatch.core.model.entry import Entry


def _phase(entry_id: str, d: list[float], intensities: list[float]) -> Entry:
    return Entry(
        entry_id=entry_id,
        formula="X Y",
        d_spacings=np.asarray(d, dtype=float),
        intensities=np.asarray(intensities, dtype=float),
    )


# ---------------------------------------------------------------------------
# fingerprint
# ---------------------------------------------------------------------------
def test_family_keys_group_siblings_and_split_polymorphs():
    siblings = np.array([
        [3.000, 1.860, 1.580],
        [3.001, 1.861, 1.581],   # same phase, cell 0.03 % off
    ])
    keys = _family_keys(siblings, 0.02)
    assert keys[0] == keys[1]

    polymorph = np.array([[3.000, 1.860, 1.500]])  # third line clearly different
    assert _family_keys(polymorph, 0.02)[0] != keys[0]


def test_family_keys_keep_short_cards_apart():
    """A 2-line card must not share a key with a 3-line card of the same d."""
    full = np.array([[3.0, 1.86, 1.58]])
    short = np.array([[3.0, 1.86, 0.0]])  # third line missing (padding)
    assert _family_keys(full, 0.02)[0] != _family_keys(short, 0.02)[0]


# ---------------------------------------------------------------------------
# slot allocation
# ---------------------------------------------------------------------------
def test_cap_is_off_by_default(tmp_path, xindb_factory):
    """Without a cap every sibling card keeps its slot (pre-3.5.0 behaviour)."""
    entries = [
        _phase("SIB1", [3.0, 1.90, 1.60], [900, 500, 400]),
        _phase("SIB2", [3.001, 1.901, 1.601], [880, 490, 390]),
        _phase("OTHER", [4.5, 2.20, 1.75], [700, 400, 300]),
    ]
    reader = XinDBReader(xindb_factory(tmp_path / "off.xinDB", entries))
    try:
        ids = reader.prescreen([3.0, 1.9, 4.5], [1.0, 1.0, 1.0],
                               min_match=1, rank_limit=2).candidate_ids
        assert ids == ["SIB1", "SIB2"]
    finally:
        reader.close()


def test_cap_lets_a_later_family_into_the_pool(tmp_path, xindb_factory):
    """With one slot per family the third card enters even though it ranks last."""
    entries = [
        _phase("SIB1", [3.0, 1.90, 1.60], [900, 500, 400]),
        _phase("SIB2", [3.001, 1.901, 1.601], [880, 490, 390]),
        _phase("OTHER", [4.5, 2.20, 1.75], [700, 400, 300]),
    ]
    reader = XinDBReader(xindb_factory(tmp_path / "cap.xinDB", entries),
                         family_slots=1)
    try:
        ids = reader.prescreen([3.0, 1.9, 4.5], [1.0, 1.0, 1.0],
                               min_match=1, rank_limit=2).candidate_ids
        assert ids == ["SIB1", "OTHER"]
    finally:
        reader.close()


def test_cap_still_fills_every_slot(tmp_path, xindb_factory):
    """The cap changes which cards get slots, never how many."""
    entries = [
        _phase(f"S{i}", [3.0 + 0.001 * i, 1.90, 1.60], [900, 500, 400])
        for i in range(5)
    ] + [_phase("P1", [4.5, 2.20, 1.75], [700, 400, 300]),
         _phase("P2", [5.5, 2.60, 2.10], [650, 380, 280])]
    reader = XinDBReader(xindb_factory(tmp_path / "fill.xinDB", entries),
                         family_slots=1)
    try:
        ids = reader.prescreen([3.0, 1.9, 4.5, 5.5], [1.0] * 4,
                               min_match=1, rank_limit=3).candidate_ids
        assert len(ids) == 3
        assert sum(1 for i in ids if i.startswith("S")) == 1  # one S card only
        assert {"P1", "P2"} <= set(ids)
    finally:
        reader.close()


def test_cap_keeps_the_legacy_leader_first(tmp_path, xindb_factory):
    entries = [
        _phase("TOP", [3.0, 1.90, 1.60], [900, 500, 400]),
        _phase("DUP", [3.001, 1.901, 1.601], [890, 490, 390]),
        _phase("NEXT", [4.5, 2.20, 1.75], [700, 400, 300]),
    ]
    reader = XinDBReader(xindb_factory(tmp_path / "head.xinDB", entries),
                         family_slots=1)
    try:
        ids = reader.prescreen([3.0, 1.9, 4.5], [1.0, 1.0, 1.0],
                               min_match=1, rank_limit=2).candidate_ids
        assert ids[0] == "TOP"
        assert "DUP" not in ids
    finally:
        reader.close()
