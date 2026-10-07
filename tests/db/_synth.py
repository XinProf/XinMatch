"""Synthetic reference-database entries for testing the db layer.

Generates 100-200 realistic-looking :class:`Entry` objects covering diverse
chemistries, crystal systems, and space groups — without needing a real COD
dump.  One known entry (LaB6, cubic ``Pm-3m``) is always included so the
d-spacing search test has a ground-truth target.
"""

from __future__ import annotations

import numpy as np

from xinmatch.core.model import CellParams, Entry

# A curated pool of (formula, space_group, cell_params, mineral_name) records.
# d-spacings are generated from the cell via a simple cubic/tetragonal/...
# approximation below.
_RECIPES: list[tuple[str, str, CellParams, str | None, int]] = [
    # formula, space_group, cell, mineral_name, year
    ("B6 La", "Pm-3m", CellParams(4.156, 4.156, 4.156), "Lanthanum hexaboride", 1971),
    ("Si O2", "P3221", CellParams(4.914, 4.914, 5.405, gamma=120.0), "Quartz", 1970),
    ("C Ca O3", "R-3c", CellParams(4.99, 4.99, 17.06, gamma=120.0), "Calcite", 1965),
    ("Na Cl", "Fm-3m", CellParams(5.64, 5.64, 5.64), "Halite", 1960),
    ("Al2 O3", "R-3c", CellParams(4.76, 4.76, 12.99, gamma=120.0), "Corundum", 1962),
    ("Fe2 O3", "R-3c", CellParams(5.04, 5.04, 13.75, gamma=120.0), "Hematite", 1968),
    ("Ti O2", "P42/mnm", CellParams(4.594, 4.594, 2.959), "Rutile", 1971),
    ("Zn S", "F-43m", CellParams(5.41, 5.41, 5.41), "Sphalerite", 1969),
    ("Cu", "Fm-3m", CellParams(3.615, 3.615, 3.615), None, 1963),
    ("Fe", "Im-3m", CellParams(2.87, 2.87, 2.87), None, 1964),
    ("Si", "Fd-3m", CellParams(5.431, 5.431, 5.431), None, 1965),
    ("Al", "Fm-3m", CellParams(4.05, 4.05, 4.05), None, 1961),
    ("Ca F2", "Fm-3m", CellParams(5.46, 5.46, 5.46), "Fluorite", 1966),
    ("Mg O", "Fm-3m", CellParams(4.21, 4.21, 4.21), "Periclase", 1967),
    ("K Al Si3 O8", "C2/m", CellParams(8.56, 12.99, 7.19, beta=116.0), "Microcline", 1972),
    ("Na Al Si3 O8", "C-1", CellParams(8.14, 12.79, 7.16, alpha=94.3, beta=116.6, gamma=87.7), "Albite", 1973),
    ("Ca CO3", "R-3c", CellParams(4.99, 4.99, 17.06, gamma=120.0), "Calcite", 1965),
    ("Fe S2", "Pa-3", CellParams(5.42, 5.42, 5.42), "Pyrite", 1970),
    ("Ba SO4", "Pnma", CellParams(8.88, 5.46, 7.16), "Barite", 1971),
    ("Sr SO4", "Pnma", CellParams(8.38, 5.35, 6.87), "Celestine", 1972),
    ("Pb S", "Fm-3m", CellParams(5.94, 5.94, 5.94), "Galena", 1968),
    ("Zn O", "P63mc", CellParams(3.25, 3.25, 5.21, gamma=120.0), "Zincite", 1969),
    ("Zr O2", "P21/c", CellParams(5.15, 5.21, 5.31, beta=99.2), "Baddeleyite", 1973),
    ("Sn O2", "P42/mnm", CellParams(4.74, 4.74, 3.19), "Cassiterite", 1971),
    ("MnO2", "P42/mnm", CellParams(4.40, 4.40, 2.87), "Pyrolusite", 1970),
]

_ELEMENTS_POOL = ["H", "Li", "Be", "B", "C", "N", "O", "F", "Na", "Mg", "Al",
                  "Si", "P", "S", "Cl", "K", "Ca", "Sc", "Ti", "V", "Cr", "Mn",
                  "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br",
                  "Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Ag", "Cd", "In", "Sn",
                  "Sb", "Te", "I", "Cs", "Ba", "La", "Ce", "W", "Au", "Pb", "Bi"]


def _cubic_d(a: float, h: int, k: int, ell: int) -> float:
    return a / np.sqrt(h * h + k * k + ell * ell)


def _tetragonal_d(a: float, c: float, h: int, k: int, ell: int) -> float:
    return 1.0 / np.sqrt((h * h + k * k) / (a * a) + ell * ell / (c * c))


def _orthorhombic_d(a: float, b: float, c: float, h: int, k: int, ell: int) -> float:
    return 1.0 / np.sqrt(h * h / (a * a) + k * k / (b * b) + ell * ell / (c * c))


def _hexagonal_d(a: float, c: float, h: int, k: int, ell: int) -> float:
    return 1.0 / np.sqrt(
        (4.0 / 3.0) * (h * h + h * k + k * k) / (a * a) + ell * ell / (c * c)
    )


def _generate_peaks(cell: CellParams) -> tuple[np.ndarray, np.ndarray, list[tuple[int, int, int]]]:
    """Generate a handful of synthetic (d, I, hkl) peaks for *cell*.

    This is not a real structure-factor calculation — just enough realistic
    d-spacings to exercise the search machinery.
    """
    a, b, c = cell.a, cell.b, cell.c
    alpha, beta, gamma = cell.alpha, cell.beta, cell.gamma
    hkls: list[tuple[int, int, int]] = []
    ds: list[float] = []

    # Determine which d-spacing formula to use.
    def d_func(h, k, ell):
        if np.isclose(a, b) and np.isclose(b, c) and np.isclose(alpha, 90):
            return _cubic_d(a, h, k, ell)
        if np.isclose(a, b) and np.isclose(alpha, 90) and np.isclose(beta, 90):
            if np.isclose(gamma, 120):
                return _hexagonal_d(a, c, h, k, ell)
            return _tetragonal_d(a, c, h, k, ell)
        if np.isclose(alpha, 90) and np.isclose(beta, 90) and np.isclose(gamma, 90):
            return _orthorhombic_d(a, b, c, h, k, ell)
        # Fallback: orthorhombic-like (good enough for synthetic tests).
        return _orthorhombic_d(a, b, c, h, k, ell)

    for h in range(1, 4):
        for k in range(0, 4):
            for ell in range(0, 4):
                if h == k == ell == 0:
                    continue
                try:
                    d = d_func(h, k, ell)
                except ZeroDivisionError:
                    continue
                if d > 0.5 and d < 15.0:
                    hkls.append((h, k, ell))
                    ds.append(float(d))

    # Sort by d descending, keep strongest ~15.
    order = sorted(range(len(ds)), key=lambda i: ds[i], reverse=True)
    hkls = [hkls[i] for i in order[:15]]
    ds = [ds[i] for i in order[:15]]
    intensities = np.linspace(1000.0, 50.0, len(ds))
    return np.array(ds), intensities, hkls


def make_recipe_entries(n: int = 25) -> list[Entry]:
    """Return one :class:`Entry` per recipe (the known-correct set)."""
    entries: list[Entry] = []
    for i, (formula, sg, cell, mineral, year) in enumerate(_RECIPES[:n]):
        ds, intensities, hkl = _generate_peaks(cell)
        entries.append(Entry(
            entry_id=f"REC-{i:04d}",
            formula=formula,
            mineral_name=mineral,
            cell=cell,
            space_group=sg,
            d_spacings=ds,
            intensities=intensities,
            hkl=hkl,
            literature={"author": f"Author{i}", "journal": "J. Synth.", "year": year},
            quality="A",
        ))
    return entries


def make_random_entries(n: int = 150, seed: int = 42) -> list[Entry]:
    """Generate *n* synthetic entries with random formulas and cells.

    The first entry is always LaB6 (cubic ``Pm-3m``) so d-search tests have a
    known ground truth.
    """
    rng = np.random.default_rng(seed)
    entries: list[Entry] = []

    # Ground-truth LaB6 entry.
    lab6_cell = CellParams(4.156, 4.156, 4.156)
    ds, intensities, hkl = _generate_peaks(lab6_cell)
    entries.append(Entry(
        entry_id="LAB6-0001",
        formula="B6 La",
        mineral_name="Lanthanum hexaboride",
        cell=lab6_cell,
        space_group="Pm-3m",
        d_spacings=ds,
        intensities=intensities,
        hkl=hkl,
        literature={"author": "Tanaka", "journal": "J. Appl. Cryst.", "year": 1971},
        quality="A",
    ))

    def cubic_cell() -> CellParams:
        a = rng.uniform(3, 12)
        return CellParams(a, a, a)

    def tetragonal_cell() -> CellParams:
        a = rng.uniform(3, 10)
        c = rng.uniform(3, 15)
        return CellParams(a, a, c)

    def orthorhombic_cell() -> CellParams:
        return CellParams(rng.uniform(3, 10), rng.uniform(3, 10), rng.uniform(3, 15))

    def hexagonal_cell() -> CellParams:
        a = rng.uniform(3, 10)
        c = rng.uniform(3, 15)
        return CellParams(a, a, c, gamma=120.0)

    def monoclinic_cell() -> CellParams:
        a = rng.uniform(3, 10)
        b = rng.uniform(3, 10)
        c = rng.uniform(3, 15)
        be = rng.uniform(100, 130)
        return CellParams(a, b, c, beta=be)

    systems = [
        ("cubic", cubic_cell),
        ("tetragonal", tetragonal_cell),
        ("orthorhombic", orthorhombic_cell),
        ("hexagonal", hexagonal_cell),
        ("monoclinic", monoclinic_cell),
    ]

    for i in range(1, n):
        _sys_name, cell_fn = systems[i % len(systems)]
        cell = cell_fn()
        ds, intensities, hkl = _generate_peaks(cell)

        # Pick 2-4 random elements for the formula.
        n_elem = int(rng.integers(2, 5))
        elems = list(rng.choice(_ELEMENTS_POOL, size=n_elem, replace=False))
        formula = " ".join(f"{e}{int(rng.integers(1, 5))}" if rng.random() > 0.5 else e for e in elems)

        sg = _RECIPES[i % len(_RECIPES)][1]
        entries.append(Entry(
            entry_id=f"SYN-{i:04d}",
            formula=formula,
            mineral_name=None,
            cell=cell,
            space_group=sg,
            d_spacings=ds,
            intensities=intensities,
            hkl=hkl,
            literature={
                "author": f"Author{i % 20}",
                "journal": "J. Synth. Mater.",
                "year": int(rng.integers(1950, 2024)),
            },
            quality="B",
        ))
    return entries


# Cached ground-truth LaB6 d-spacings for the d-search test.
def lab6_dspacings() -> list[float]:
    """Return the synthetic LaB6 d-spacings used for d-search ground truth."""
    cell = CellParams(4.156, 4.156, 4.156)
    ds, _int, _hkl = _generate_peaks(cell)
    return ds.tolist()
