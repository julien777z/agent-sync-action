---
globs:
- pyproject.toml
- poetry.lock
- '**/*.py'
alwaysApply: false
paths:
- pyproject.toml
- poetry.lock
- '**/*.py'
---

# Poetry Project Rules

## Project Configuration

- For single-consumer, non-library repositories, require Python 3.12 or newer and prefer the latest stable Python release when the repository's runtime and dependencies are compatible. For public libraries, prefer the widest feasible supported range with a minimum no earlier than Python 3.11.
- Use Poetry 2.x with PEP 621 `[project]` metadata; do not use legacy `[tool.poetry]` metadata or dependency tables.
- Declare runtime dependencies in `[project.dependencies]`, development dependencies in `[project.optional-dependencies].dev`, and console entry points in `[project.scripts]`.
- Under static `[project.dependencies]`, `[tool.poetry.dependencies]` only supplies alternate sources. A package listed there but absent from `[project.dependencies]` is not installed. Declare the package name in `[project.dependencies]` and use `[tool.poetry.dependencies]` only for its path, Git, or URL source.
- Never repair a Poetry environment by installing packages directly with `pip`. Fix the manifest, regenerate the lock file, and run `poetry install` so the environment and lock remain consistent.
- Configure strict Pyright, pytest with automatic asyncio support, and Black with a 100-character line length and Python targets inferred from the full `[project.requires-python]` range.
- Keep the Poetry build system at the end of `pyproject.toml`:

```toml
[build-system]
requires = ["poetry-core>=2.0.0"]
build-backend = "poetry.core.masonry.api"
```

- Use `poetry install`, `poetry run black .`, `poetry run pyright`, and `poetry run pytest` for the standard local workflow.

## Application Structure

- Prefer separate focused modules over monoliths, organizing code under `clients/`, `services/`, `models/`, and `core/` as applicable.
- Prefer PEP 695 generic syntax when it improves an interface and the repository's minimum Python version is 3.12 or newer; otherwise use modern typing syntax supported across the declared range.
- Give every function and class a one-line imperative docstring followed by a blank line.
- Services may be plain functions. Pass clients, sessions, and configuration explicitly rather than storing module-level runtime globals.
- Use `aiohttp` for HTTP I/O, inject a `ClientSession` configured with a sensible timeout, create long-lived sessions at application startup, enable `raise_for_status` when appropriate, and parse responses asynchronously with `json()` or `text()`.
- Keep HTTP-style error types in `core/errors.py`. Import the project's canonical `ErrorResponse` or `Error` as `HttpError`; create the missing canonical type rather than adding runtime import or compatibility fallbacks.
- Configure logging centrally and use it instead of `print()`.

## Testing

- Use pytest and pytest-asyncio with small, readable tests, and mark async tests with `@pytest.mark.asyncio`.
- Prefer dependency injection or fakes over deep patching.

## Guardrails

- Use Black rather than Ruff for formatting.
- Keep comments minimal and do not generate additional Markdown beyond the existing rules and Project Layout documents unless the user requests it.
