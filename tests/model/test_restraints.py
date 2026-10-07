"""Tests for :class:`xinmatch.core.model.Restraints` and :class:`ElementState`."""


from xinmatch.core.model import ElementState, Restraints


def test_element_three_states():
    r = Restraints()
    assert r.get_state("Si") == ElementState.OPTIONAL

    r.require("Si")
    assert r.get_state("Si") == ElementState.REQUIRED

    r.exclude("Pb")
    assert r.get_state("Pb") == ElementState.EXCLUDE


def test_set_optional_removes_entry():
    r = Restraints()
    r.require("Si")
    r.set_element("Si", ElementState.OPTIONAL)
    assert "Si" not in r.elements
    assert r.get_state("Si") == ElementState.OPTIONAL


def test_passes_elements_required():
    r = Restraints()
    r.require("Si")
    r.require("O")
    assert r.passes_elements({"Si", "O"}) is True
    assert r.passes_elements({"Si"}) is False  # missing O


def test_passes_elements_excluded():
    r = Restraints()
    r.exclude("Pb")
    assert r.passes_elements({"Si", "O"}) is True
    assert r.passes_elements({"Si", "O", "Pb"}) is False


def test_passes_elements_combined():
    r = Restraints()
    r.require("Si")
    r.exclude("Pb")
    assert r.passes_elements({"Si", "O"}) is True
    assert r.passes_elements({"Si", "Pb"}) is False
    assert r.passes_elements({"O"}) is False  # missing Si


def test_restraints_serialization_roundtrip():
    r = Restraints(
        crystal_system="cubic",
        space_group="Fm-3m",
        density_range=(2.0, 5.0),
        year_range=(1990, 2020),
        author="Smith",
    )
    r.require("Si")
    r.exclude("Pb")
    restored = Restraints.from_dict(r.to_dict())
    assert restored.crystal_system == "cubic"
    assert restored.get_state("Si") == ElementState.REQUIRED
    assert restored.get_state("Pb") == ElementState.EXCLUDE
    assert restored.density_range == (2.0, 5.0)
