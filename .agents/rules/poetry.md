---
description: Maintain a modern Poetry project with one canonical dependency definition.
alwaysApply: true
---

# Poetry Rules

- Target Python 3.12 and Poetry 2 with PEP 621 `[project]` metadata.
- Declare runtime dependencies in `[project.dependencies]`, development tools in `[dependency-groups].dev`, and console commands in `[project.scripts]`.
- Keep only package-discovery configuration under `[tool.poetry]`; do not duplicate metadata or dependency declarations there.
- Configure Black with a 100-character line length, strict Pyright, and pytest.
- Use `poetry install`, `poetry run black --check .`, `poetry run pyright`, and `poetry run pytest` for validation.
- Keep the Poetry build system at the end of `pyproject.toml`.
