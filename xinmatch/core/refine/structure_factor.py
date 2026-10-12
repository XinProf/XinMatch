"""Structure-factor and diffraction-physics utilities (T10.2).

Provides the building blocks needed to compute the integrated intensity of
a Bragg reflection from a known crystal structure:

* :func:`atomic_scattering_factor` — 9-parameter ITC approximation
  ``f(s) = Σ a_i·exp(-b_i·s²) + c`` with ``s = sin θ / λ``.
* :func:`debye_waller_factor` — isotropic temperature factor.
* :func:`lorentz_polarization` — Lorentz–polarisation factor.
* :func:`structure_factor` — complex structure factor ``F(hkl)``.
* :func:`multiplicity` — powder multiplicity for the Laue class.

These are the same quantities FullProf evaluates internally during a
Rietveld refinement (``docs/Rietveld.md``).  The scattering-factor
coefficients are the Cromer–Mann values tabulated in International Tables
for Crystallography Vol. C (1999), Table 6.1.1.4.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from xinmatch.core.index.lattice import compute_d
from xinmatch.core.model.entry import CellParams

_DEG2RAD = np.pi / 180.0

# Cromer–Mann 9-parameter atomic scattering-factor coefficients.
# Layout: (a1, a2, a3, a4, b1, b2, b3, b4, c).
# Values from International Tables for Crystallography Vol. C, Table 6.1.1.4
# (the IT92 table; f(0) = Σ a_i + c = Z for neutral atoms).
_SCATTERING_FACTORS: dict[str, tuple[float, ...]] = {
    "H":  (0.493002, 0.322912, 0.140191, 0.04081, 10.5109, 26.1257, 3.14236, 57.7997, 0.003038),
    "C":  (2.31, 1.02, 1.5886, 0.865, 20.8439, 10.2075, 0.5687, 51.6512, 0.2156),
    "N":  (12.2126, 3.1322, 2.0125, 1.1663, 0.0057, 9.8933, 28.9975, 0.5826, -11.529),
    "O":  (3.0485, 2.2868, 1.5463, 0.867, 13.2771, 5.7011, 0.3239, 32.9089, 0.2508),
    "Na": (4.7626, 3.1736, 1.2674, 1.1128, 3.285, 8.8422, 0.3136, 129.424, 0.676),
    "Mg": (5.4204, 2.1735, 1.2269, 2.3073, 2.8275, 79.2611, 0.3808, 7.1937, 0.8584),
    "Al": (6.4202, 1.9002, 1.5936, 1.9646, 3.0387, 0.7426, 31.5472, 85.0886, 1.1151),
    "Si": (6.2915, 3.0353, 1.9891, 1.541, 2.4386, 32.3337, 0.6785, 81.6937, 1.1407),
    "P":  (6.4345, 4.1791, 1.78, 1.4908, 1.9067, 27.157, 0.526, 68.1645, 1.1149),
    "S":  (6.9053, 5.2034, 1.4379, 1.5863, 1.4679, 22.2151, 0.2536, 56.172, 0.8669),
    "Cl": (11.4604, 7.1964, 6.2556, 1.6455, 0.0104, 1.1662, 18.5194, 47.7784, -9.5574),
    "K":  (8.2186, 7.4398, 1.0519, 0.8659, 12.7949, 0.7748, 213.187, 41.6841, 1.4228),
    "Ca": (8.6266, 7.3873, 1.5899, 1.0211, 10.4421, 0.6599, 85.7484, 178.437, 1.3751),
    "Ti": (9.7595, 7.3558, 1.6991, 1.9021, 7.8508, 0.5, 35.6338, 116.105, 1.2807),
    "Fe": (11.7695, 7.3573, 3.5222, 2.3045, 4.7611, 0.3072, 15.3535, 76.8805, 1.0369),
    "Cu": (13.338, 7.1676, 5.6158, 1.6735, 3.5828, 0.247, 11.3966, 64.8126, 1.191),
    "Zn": (14.0743, 7.0318, 5.1652, 2.41, 3.2655, 0.2333, 10.3163, 58.7097, 1.3041),
    "Br": (17.1789, 5.2358, 5.6377, 3.9851, 2.1723, 16.5796, 0.2609, 41.4328, 2.9557),
    "Ag": (19.2808, 16.6885, 4.8045, 1.0463, 0.6446, 7.4726, 24.6605, 99.8156, 5.179),
    "I":  (20.1472, 18.9949, 7.5138, 2.2735, 4.347, 0.3814, 27.766, 66.8776, 4.0712),
    "Ba": (20.3361, 19.297, 10.888, 2.6959, 3.216, 0.2756, 20.2073, 167.202, 2.7731),
    "La": (20.578, 19.599, 11.3727, 3.28719, 2.94817, 0.244475, 18.7726, 133.124, 2.14678),
    "Pb": (31.0617, 13.0637, 18.442, 5.9696, 0.6902, 2.3576, 8.618, 47.2579, 13.4118),
    "U":  (36.0228, 23.4128, 14.9491, 4.188, 0.5293, 3.3253, 16.0927, 100.613, 13.3966),
}


@dataclass
class Atom:
    """One atom in the asymmetric unit.

    Attributes
    ----------
    element:
        Chemical symbol (e.g. ``'Fe'``).
    x, y, z:
        Fractional coordinates.
    occupancy:
        Site occupancy (0–1).
    b_iso:
        Isotropic displacement parameter ``B_iso`` (Å²).
    """

    element: str
    x: float
    y: float
    z: float
    occupancy: float = 1.0
    b_iso: float = 1.0


def atomic_scattering_factor(element: str, sin_theta_over_lambda: float) -> float:
    """Atomic scattering factor for *element* at ``s = sin θ / λ``.

    Uses the 9-parameter International Tables approximation:

    .. math::

        f(s) = \\sum_{i=1}^{4} a_i \\exp(-b_i s^2) + c

    Parameters
    ----------
    element:
        Chemical symbol (case-sensitive).  Must be present in the built-in
        coefficient table.
    sin_theta_over_lambda:
        ``sin θ / λ`` in Å⁻¹.

    Returns
    -------
    float
        Scattering factor (in electrons).
    """
    coeffs = _SCATTERING_FACTORS.get(element)
    if coeffs is None:
        raise ValueError(
            f"no scattering-factor coefficients for element {element!r}; "
            f"available: {', '.join(sorted(_SCATTERING_FACTORS))}"
        )
    a1, a2, a3, a4, b1, b2, b3, b4, c = coeffs
    s2 = float(sin_theta_over_lambda) ** 2
    return float(
        a1 * np.exp(-b1 * s2)
        + a2 * np.exp(-b2 * s2)
        + a3 * np.exp(-b3 * s2)
        + a4 * np.exp(-b4 * s2)
        + c
    )


def debye_waller_factor(b_iso: float, sin_theta_over_lambda: float) -> float:
    """Isotropic Debye–Waller factor ``exp(-B·s²)``.

    Parameters
    ----------
    b_iso:
        Isotropic displacement parameter ``B`` in Å².
    sin_theta_over_lambda:
        ``sin θ / λ`` in Å⁻¹.
    """
    s2 = float(sin_theta_over_lambda) ** 2
    return float(np.exp(-b_iso * s2))


def lorentz_polarization(
    two_theta_deg: float,
    *,
    wavelength: float,
    polarization: float = 0.0,
) -> float:
    """Lorentz–polarisation factor for unpolarised or partially polarised radiation.

    .. math::

        LP(2\\theta) = \\frac{1 + P\\,\\cos^2 2\\theta}
                              {\\sin\\theta\\,\\cos\\theta}

    where ``P = polarization`` is the degree of polarisation
    (``0`` for an unpolarised beam, ``1`` for fully polarised,
    ``0.5`` for a diffracted-beam monochromator).

    Parameters
    ----------
    two_theta_deg:
        Scattering angle 2θ in degrees.
    wavelength:
        Radiation wavelength in Å (unused by the formula itself but kept
        for signature symmetry with the other physics functions).
    polarization:
        Polarisation factor ``P`` in ``[0, 1]``.

    Returns
    -------
    float
        Lorentz–polarisation factor.
    """
    theta = _DEG2RAD * float(two_theta_deg) / 2.0
    sin_t = np.sin(theta)
    cos_t = np.cos(theta)
    cos_2t = np.cos(2.0 * theta)
    denom = sin_t * cos_t
    if denom <= 0.0:
        return 0.0
    pol = float(polarization)
    return float((1.0 + pol * cos_2t * cos_2t) / denom)


def structure_factor(
    hkl: tuple[int, int, int],
    atoms: list[Atom],
    cell: CellParams,
    *,
    wavelength: float,
) -> complex:
    """Complex structure factor ``F(hkl)``.

    .. math::

        F(hkl) = \\sum_j f_j(s)\\, T_j(s)\\, \\exp\\bigl[2\\pi i\\,
                 (h x_j + k y_j + l z_j)\\bigr]

    where ``s = sin θ / λ = 1 / (2 d)``, ``f_j`` is the atomic scattering
    factor and ``T_j = exp(-B_j s²)`` the Debye–Waller factor.

    Parameters
    ----------
    hkl:
        Miller indices ``(h, k, l)``.
    atoms:
        Atoms in the (possibly expanded) unit cell.  If the list is empty
        or ``None``, returns ``0j``.
    cell:
        Unit-cell parameters (used to compute ``d`` and hence ``s``).
    wavelength:
        Radiation wavelength in Å.

    Returns
    -------
    complex
        Structure factor ``F(hkl)``.
    """
    if not atoms:
        return 0j
    h, k, ll = hkl
    d = compute_d(hkl, cell)
    sin_theta_over_lambda = 1.0 / (2.0 * d)
    f_sum = 0.0j
    for atom in atoms:
        f = atomic_scattering_factor(atom.element, sin_theta_over_lambda)
        t = debye_waller_factor(atom.b_iso, sin_theta_over_lambda)
        phase = 2.0 * np.pi * (h * atom.x + k * atom.y + ll * atom.z)
        f_sum += atom.occupancy * f * t * complex(np.cos(phase), np.sin(phase))
    return f_sum


def get_orbit(hkl: tuple[int, int, int], crystal_system: str) -> set[tuple[int, int, int]]:
    """Return the set of symmetry-equivalent reflections for *hkl*.

    Uses the highest-symmetry Laue group of *crystal_system*.  Friedel pairs
    are included (centrosymmetric Laue groups), so the orbit always contains
    both ``(h, k, l)`` and ``(-h, -k, -l)``.
    """
    h, k, ll = (int(v) for v in hkl)
    if h == 0 and k == 0 and ll == 0:
        return {(0, 0, 0)}

    orbit: set[tuple[int, int, int]] = set()

    def add(h0: int, k0: int, l0: int) -> None:
        orbit.add((h0, k0, l0))

    signs = [(1, 1, 1), (1, 1, -1), (1, -1, 1), (1, -1, -1),
             (-1, 1, 1), (-1, 1, -1), (-1, -1, 1), (-1, -1, -1)]

    if crystal_system == "triclinic":
        add(h, k, ll)
        add(-h, -k, -ll)
        return orbit

    if crystal_system == "monoclinic":
        add(h, k, ll)
        add(-h, k, -ll)
        add(h, -k, ll)
        add(-h, -k, -ll)
        return orbit

    if crystal_system == "orthorhombic":
        for sg in signs:
            add(sg[0] * h, sg[1] * k, sg[2] * ll)
        return orbit

    if crystal_system == "tetragonal":
        rots = [(h, k, ll), (-k, h, ll), (-h, -k, ll), (k, -h, ll)]
        for rh, rk, rl in rots:
            for sg in signs:
                add(sg[0] * rh, sg[1] * rk, sg[2] * rl)
        return orbit

    if crystal_system == "trigonal":
        rots = [(h, k, ll), (-k, h + k, ll), (-h - k, h, ll)]
        for rh, rk, rl in rots:
            for sg in signs:
                add(sg[0] * rh, sg[1] * rk, sg[2] * rl)
        return orbit

    if crystal_system == "hexagonal":
        rots = [
            (h, k, ll),
            (-k, h + k, ll),
            (-h - k, h, ll),
            (-h, -k, ll),
            (k, -h - k, ll),
            (h + k, -h, ll),
        ]
        for rh, rk, rl in rots:
            for sg in signs:
                add(sg[0] * rh, sg[1] * rk, sg[2] * rl)
        return orbit

    if crystal_system == "cubic":
        perms = [
            (h, k, ll), (h, ll, k), (k, h, ll), (k, ll, h), (ll, h, k), (ll, k, h),
        ]
        for ph, pk, pl in perms:
            for sg in signs:
                add(sg[0] * ph, sg[1] * pk, sg[2] * pl)
        return orbit

    raise ValueError(f"unknown crystal system {crystal_system!r}")


def multiplicity(hkl: tuple[int, int, int], crystal_system: str) -> int:
    """Powder multiplicity of reflection *hkl* for the Laue class of *crystal_system*.

    The multiplicity is the number of symmetry-equivalent reflections that
    overlap at the same d-spacing in a powder pattern.
    """
    return len(get_orbit(hkl, crystal_system))
