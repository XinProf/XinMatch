# Cross-platform & coding conventions

> Task T0.7 of ROADMAP_v3. These conventions keep the codebase portable across
> Windows / Linux / macOS and consistent enough for AI agents to collaborate.

## 1. Paths & files

- Always use [`pathlib.Path`](https://docs.python.org/3/library/pathlib.html) —
  never hard-code `\` or `/`.
- Resolve user home with `Path.home()`, not `os.environ["HOME"]`.
- For config / cache, use
  [`platformdirs`](https://pypi.org/project/platformdirs/) (planned dep) or
  fall back to `Path.home() / ".xinmatch"`.

## 2. Text & encoding

- All source files and data files written by XinMatch must be **UTF-8**.
- When reading third-party files (vendor diffraction formats), sniff the
  encoding; default to `latin-1` for legacy formats, but document it.
- **Newlines**: Match! does not support CR-only line endings. When *writing*
  files, use `\n` (LF) universally — never `\r` alone. Python's `open(...,
  newline="")` gives explicit control.

## 3. Numerics

- Use `numpy.float64` for all diffraction intensities, 2θ, d-spacings.
- Never compare floats with `==`; use `np.isclose(a, b, atol=..., rtol=...)`.
- Round-trip serialization must preserve values to `< 1e-9` relative error.

## 4. Function signatures (core layer)

- Inputs / outputs are **numpy arrays or dataclasses**.
- The algorithm layer must **not** read or write files — I/O lives in
  `xinmatch/core/io/`.
- Every public function needs a docstring stating:
  1. which Match! feature it implements,
  2. the algorithm source (publication / formula),
  3. parameter meanings and units.

## 5. Testing

- Every task ships with a `tests/<module>/test_<topic>.py`.
- Use `pytest` + `hypothesis` for property-based tests where relevant.
- Acceptance thresholds (e.g. *Rwp < 2 %*) are stated in the test itself and
  match the roadmap task.

## 6. Imports & typing

- Absolute imports only (`from xinmatch.core.model import Pattern`).
- Type hints on all public functions; `mypy` passes on `xinmatch.core`.

## 7. Logging

- Use the standard `logging` module, never `print()` inside `xinmatch.core`.
- The CLI / UI configures handlers; the kernel just emits log records.

## 8. Dependencies & licensing

- No GPL-licensed runtime dependencies (would taint the MIT project).
- Prefer MIT / BSD / LGPL / Apache-2.0.
- LGPL deps (e.g. PySide6) are fine as long as we link dynamically.
