---
description: Follow modern Python typing, module, error-handling, and maintainability conventions.
alwaysApply: true
---

# Python Rules

## Types And Models

- Use Python 3.12 syntax: `T | None`, built-in generics, `Self`, `StrEnum`, and precise unions.
- Model structured data explicitly. Use Pydantic `BaseModel` when validation or serialization is required and `TypedDict` for mapping-shaped contracts.
- Do not use `Any`, placeholder `object` fields, casts that hide a weak boundary, dataclasses, named tuples, or protocols as data models.
- Group values that always travel together into one typed model instead of threading unrelated parameters through the pipeline.

## Imports And Modules

- Keep imports at the top, grouped as standard library, third party, then local.
- Use absolute imports anchored at `agent_sync`; only `__main__.py` and package exports may use explicit relative imports.
- Do not use leading underscores for module-level symbols or methods. Module boundaries and `__all__` express ownership.
- Do not create compatibility shims or modules that merely re-export another implementation.
- Give each module one clear responsibility. If a name joins two separate concepts, create a package with focused topic modules instead.

## Architecture

- Pass workspace and configuration explicitly. Do not store mutable runtime context or filesystem caches in module globals.
- Keep entrypoints thin, generation pure, external commands behind explicit boundaries, and filesystem mutation inside reconciliation or vendoring.
- Delete application symbols with no non-test consumer; tests do not justify dead production code.
- Prefer direct flows over thin wrappers, fallback branches, generic dispatch machinery, and helpers that only rename one call.
- Read required data from its canonical source and fail loudly when present input is malformed. Do not silently substitute or ignore invalid state.

## Control Flow And Errors

- Use `match` for enum or command dispatch and comprehensions for simple filtering or transformation.
- Catch specific documented exceptions. Never catch bare `Exception`.
- Use logging for status and diagnostics; do not use `print()`.
- Keep constants with their owning module and annotate reused domain constants with `Final`.

## Documentation And Formatting

- Give every function, method, and class a one-line docstring followed by a blank line.
- Do not add module docstrings, decorative comments, migration-history comments, or comments that narrate behavior owned by tests.
- Use descriptive current-tense names and blank lines as logical phase boundaries.
