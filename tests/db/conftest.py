"""Shared pytest fixtures for the db test suite."""

from __future__ import annotations

import sqlite3

import pytest

from xinmatch.core.db import build_element_index, create_tables, insert_entries
from xinmatch.core.model import Entry

from ._synth import make_random_entries, make_recipe_entries


@pytest.fixture
def empty_conn() -> sqlite3.Connection:
    """An in-memory SQLite connection with the schema applied but no data."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def recipe_entries() -> list[Entry]:
    """The curated recipe entries (known formulas / space groups)."""
    return make_recipe_entries()


@pytest.fixture
def random_entries() -> list[Entry]:
    """150 synthetic entries including the ground-truth LaB6."""
    return make_random_entries(n=150)


@pytest.fixture
def populated_conn(random_entries: list[Entry]) -> sqlite3.Connection:
    """In-memory DB populated with 150 synthetic entries + indexes built."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)
    insert_entries(conn, random_entries)
    build_element_index(conn)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# v3 ``.xinDB`` helpers (v3.0.0: the only searchable reference format)
# ---------------------------------------------------------------------------
# 实现放在 ``tests/xindb_support.py``, 供根目录/cli 测试共用; 这里只做 fixture 包装。
from tests.xindb_support import write_xindb  # noqa: E402


@pytest.fixture
def xindb_factory(recipe_entries):
    """Return ``make(path, entries=None)`` that writes a small valid ``.xinDB``."""
    from pathlib import Path

    def _make(path, entries=None):
        return write_xindb(Path(path), list(entries if entries is not None
                                           else recipe_entries))

    return _make
