"""Smoke test — verifies the package imports and pytest collects correctly."""

import xinmatch


def test_package_version_is_string():
    assert isinstance(xinmatch.__version__, str)
    assert xinmatch.__version__


def test_core_subpackage_imports():
    from xinmatch import core  # noqa: F401
    from xinmatch.core import db, io, model, peak, preprocess, search  # noqa: F401
