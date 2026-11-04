"""`XinDBReader.fetch_peaks` must survive SQLite's host-parameter cap.

The ``entry_id IN (?, ?, …)`` lookup used to be issued as one statement holding
every requested id.  SQLite allows 999 host parameters on older builds and
32766 on current ones; above that it raises ``OperationalError``, which the
blanket ``except sqlite3.Error`` in ``fetch_peaks`` converted into an **empty
result**.  A search with ``candidate_limit`` above the cap therefore returned no
candidates at all (found 2026-11-04: a 40 000-candidate probe came back empty).

The lookup is now issued in batches of ``_FETCH_ID_BATCH``.  This test pins the
contract without needing 33 k entries: it caps the connection at 10 parameters
and asks for 150.
"""

from __future__ import annotations

import sqlite3

from xinmatch.core.db import reader_v3
from xinmatch.core.db.reader_v3 import XinDBReader


class _ParamCappedConn:
    """A connection proxy that refuses statements with too many host parameters."""

    def __init__(self, conn: sqlite3.Connection, limit: int) -> None:
        self._conn = conn
        self._limit = limit

    def execute(self, sql, params=()):  # noqa: ANN001, ANN201
        if len(params) > self._limit:
            raise sqlite3.OperationalError("too many SQL variables")
        return self._conn.execute(sql, params)

    def close(self) -> None:
        self._conn.close()


def test_fetch_peaks_batches_id_lookup(tmp_path, xindb_factory, random_entries,
                                       monkeypatch):
    lib = xindb_factory(tmp_path / "cap.xinDB", random_entries)
    reader = XinDBReader(lib)
    ids = [entry.entry_id for entry in random_entries]
    try:
        assert len(reader.fetch_peaks(ids)) == len(ids)

        # Shrink the batch so the 10-parameter cap below actually bites, then
        # cap the connection: an unbatched lookup raises and silently yields {}.
        monkeypatch.setattr(reader_v3, "_FETCH_ID_BATCH", 8)
        real = reader._conn
        assert real is not None
        reader._conn = _ParamCappedConn(real, 10)  # type: ignore[assignment]
        capped = reader.fetch_peaks(ids)
        assert len(capped) == len(ids)
        assert all(capped[i][0] for i in ids if i in capped)
    finally:
        reader.close()


def test_fetch_peaks_empty_input(tmp_path, xindb_factory):
    reader = XinDBReader(xindb_factory(tmp_path / "empty.xinDB"))
    try:
        assert reader.fetch_peaks([]) == {}
    finally:
        reader.close()
