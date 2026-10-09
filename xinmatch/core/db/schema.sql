-- XinMatch reference database schema (Phase 5)
-- SQLite DDL for the COD-style reference database.
-- Covers the 28 参考软件 search fields: element, cell, d-value, formula,
-- mineral name, author, journal, year, space group, color, density, etc.

-- ---------------------------------------------------------------------------
-- entries: one row per reference-database entry (COD record)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS entries (
    entry_id       TEXT PRIMARY KEY,
    formula        TEXT,
    mineral_name   TEXT,
    space_group    TEXT,
    crystal_system TEXT,
    a              REAL,
    b              REAL,
    c              REAL,
    alpha          REAL,
    beta           REAL,
    gamma          REAL,
    volume         REAL,
    density        REAL,
    color          TEXT,
    year           INTEGER,
    author         TEXT,
    journal        TEXT,
    quality        TEXT,
    elements       TEXT            -- comma-separated element symbols, e.g. "Ca,C,O"
);

-- ---------------------------------------------------------------------------
-- peaks: d–I peak table (one entry -> many rows)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS peaks (
    entry_id  TEXT NOT NULL,
    d         REAL NOT NULL,
    intensity REAL,
    h         INTEGER,
    k         INTEGER,
    l         INTEGER,
    FOREIGN KEY (entry_id) REFERENCES entries(entry_id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- elements: inverted index (entry_id, element) — one row per element per entry
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS elements (
    entry_id TEXT NOT NULL,
    element  TEXT NOT NULL,
    PRIMARY KEY (entry_id, element)
);

-- ---------------------------------------------------------------------------
-- element_combo: precomputed element-set hash -> entry ids (acceleration)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS element_combo (
    element_set_hash TEXT PRIMARY KEY,
    entry_ids        TEXT NOT NULL    -- newline-separated entry_id list
);

-- ---------------------------------------------------------------------------
-- Indexes for the common 参考软件 search fields
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_elements_element_entry
    ON elements(element, entry_id);
CREATE INDEX IF NOT EXISTS idx_peaks_d
    ON peaks(d);
-- Entry-id lookups on the peaks table (fetch_entries_by_ids) are a
-- full-table scan without this index; on COD-scale databases that is
-- minutes per search-match run.
CREATE INDEX IF NOT EXISTS idx_peaks_entry_id
    ON peaks(entry_id);
CREATE INDEX IF NOT EXISTS idx_entries_formula
    ON entries(formula);
CREATE INDEX IF NOT EXISTS idx_entries_space_group
    ON entries(space_group);
CREATE INDEX IF NOT EXISTS idx_entries_crystal_system
    ON entries(crystal_system);
CREATE INDEX IF NOT EXISTS idx_entries_year
    ON entries(year);
CREATE INDEX IF NOT EXISTS idx_entries_mineral_name
    ON entries(mineral_name);
CREATE INDEX IF NOT EXISTS idx_entries_author
    ON entries(author);
CREATE INDEX IF NOT EXISTS idx_entries_journal
    ON entries(journal);
