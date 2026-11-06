"""``python -m xinmatch`` — module entry point for the CLI.

The console script installed by ``pyproject.toml`` is ``xinmatch``
(``xinmatch.cli.main:main``); this file makes the *source* tree behave the same
way, so ``python -m xinmatch libraries`` works without an editable install.

Before 2026-11-06 the package had no ``__main__`` and this invocation failed with
``No module named xinmatch.__main__``, even though the handover notes documented
it — the documented form is the one users type, so make it true.

Source: standard :mod:`runpy`-style delegation; no logic lives here.
"""

from __future__ import annotations

from xinmatch.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
