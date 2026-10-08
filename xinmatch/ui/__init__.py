"""XinMatch GUI package (PySide6 native widgets).

Boundary rule: :mod:`xinmatch.core` stays completely GUI-free.  Widgets in
this package only consume plain data classes from
:mod:`xinmatch.core.model` (e.g. :class:`~xinmatch.core.model.pattern.Pattern`).
QWebEngineView-based 3D / rich-text report views are explicitly out of
scope for T13.0–T13.2.
"""
