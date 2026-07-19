---
alwaysApply: true
---

# Poetry Project Rules

## Project Configuration

- Target Python 3.12 and use Poetry 2.x with PEP 621 `[project]` metadata; do not use legacy `[tool.poetry]` metadata or dependency tables.
- Declare runtime dependencies in `[project.dependencies]`, development dependencies in Poetry `[dependency-groups].dev`, and console entry points in `[project.scripts]`.
- Configure strict Pyright, pytest, and Black with a 100-character line length and Python 3.12 target inferred from `[project.requires-python]`.
- Keep the Poetry build system at the end of `pyproject.toml`:

```toml
[build-system]
requires = ["poetry-core>=2.0.0"]
build-backend = "poetry.core.masonry.api"
```

- Use `poetry install`, `poetry run black .`, `poetry run pyright`, and `poetry run pytest` for the standard local workflow.

## Application Structure

- Prefer separate focused modules over monoliths, organizing code under `clients/`, `services/`, `models/`, and `core/` as applicable.
- Prefer PEP 695 generic syntax when it improves a Python 3.12 interface.
- Give every function and class a one-line imperative docstring followed by a blank line.
- Services may be plain functions. Pass clients, sessions, and configuration explicitly rather than storing module-level runtime globals.
- Use `aiohttp` for HTTP I/O, inject a `ClientSession` configured with a sensible timeout, create long-lived sessions at application startup, enable `raise_for_status` when appropriate, and parse responses asynchronously with `json()` or `text()`.
- Keep HTTP-style error types in `core/errors.py`. Import the project's canonical `ErrorResponse` or `Error` as `HttpError`; create the missing canonical type rather than adding runtime import or compatibility fallbacks.
- Configure logging centrally and use it instead of `print()`.

## Testing

- Use pytest with small, readable tests.
- Prefer dependency injection or fakes over deep patching.

## Guardrails

- Use Black rather than Ruff for formatting.
- Keep comments minimal and do not generate additional Markdown beyond the existing rules and Project Layout documents unless the user requests it.
