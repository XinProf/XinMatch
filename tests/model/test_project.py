"""Tests for :class:`xinmatch.core.model.Project` (incl. undo/redo and persistence)."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.model import Entry, Pattern, Peak, Project


@pytest.fixture
def project() -> Project:
    p = Pattern(
        two_theta=np.linspace(10.0, 80.0, 701),
        intensity=np.ones(701),
        wavelength=1.5406,
    )
    return Project(patterns=[p], peaks=[Peak(25.0, 100.0)])


def test_undo_redo(project: Project):
    project.snapshot()
    project.peaks.append(Peak(30.0, 50.0))
    assert len(project.peaks) == 2

    assert project.undo() is True
    assert len(project.peaks) == 1

    assert project.can_redo() is True
    assert project.redo() is True
    assert len(project.peaks) == 2


def test_undo_empty_returns_false(project: Project):
    assert project.undo() is False


def test_redo_empty_returns_false(project: Project):
    assert project.redo() is False


def test_undo_clears_redo_after_new_change(project: Project):
    project.snapshot()
    project.peaks.append(Peak(30.0, 50.0))
    project.undo()
    assert project.can_redo() is True

    # A new snapshot should clear the redo stack
    project.snapshot()
    project.peaks.append(Peak(35.0, 25.0))
    assert project.can_redo() is False


def test_save_load_roundtrip(project: Project):
    project.candidates = [
        (
            Entry(
                entry_id="1",
                formula="Si",
                d_spacings=np.array([3.0, 2.0]),
                intensities=np.array([1000.0, 500.0]),
            ),
            0.95,
        )
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.extmatch.json"
        project.save(str(path))
        assert path.exists()

        loaded = Project.load(str(path))
        assert len(loaded.patterns) == 1
        assert len(loaded.peaks) == 1
        assert len(loaded.candidates) == 1
        assert loaded.candidates[0][1] == pytest.approx(0.95)


def test_save_produces_valid_json(project: Project):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.json"
        project.save(str(path))
        with open(path) as f:
            data = json.load(f)
        assert "patterns" in data
        assert "peaks" in data
