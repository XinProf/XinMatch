"""XinMatch reference-database layer (Phase 5).

Submodules
----------
schema
    SQLite table layout (entries, peaks, elements, element_combo).
build_cod
    Insert :class:`~xinmatch.core.model.Entry` objects into the database.
user_db
    User-database (UDB) workflows — v3-native：产出可直接检索的 ``.xinDB``。
index_build
    Build inverted indexes (element sets, d-spacing range).
query_peaks
    d-spacing based search-match (peak-based FoM).
query_filter
    Multi-field restraints (elements, space group, year, ...).
manager
    Database library management (list / create / delete).
"""

from .build_cod import insert_entries, insert_entry
from .index_build import build_all_indexes, build_d_index, build_element_index
from .manager import create_database, delete_database, list_databases
from .query_filter import (
    search_by_crystal_system,
    search_by_elements,
    search_by_formula,
    search_by_mineral_name,
    search_by_space_group,
    search_by_year,
    search_combined,
)
from .query_peaks import search_by_d, search_by_d_with_intensity
from .schema import SCHEMA_SQL, create_tables, enable_wal
from .user_db import (
    add_cif_files,
    ensure_registered,
    list_user_entries,
    rebuild,
    remove_entries,
    user_entry_count,
    user_library_path,
)

__all__ = [
    # schema
    "SCHEMA_SQL",
    "create_tables",
    "enable_wal",
    # insert
    "insert_entry",
    "insert_entries",
    # user db（v3 原生：.xinDB）
    "add_cif_files",
    "ensure_registered",
    "list_user_entries",
    "user_entry_count",
    "user_library_path",
    "rebuild",
    "remove_entries",
    # indexes
    "build_element_index",
    "build_d_index",
    "build_all_indexes",
    # peak search
    "search_by_d",
    "search_by_d_with_intensity",
    # filters
    "search_by_elements",
    "search_by_crystal_system",
    "search_by_space_group",
    "search_by_year",
    "search_by_mineral_name",
    "search_by_formula",
    "search_combined",
    # manager
    "list_databases",
    "create_database",
    "delete_database",
]
