---
description: Keep tests behavior-focused, typed, isolated, and aligned with source ownership.
alwaysApply: true
---

# Testing Rules

## Organization And Fixtures

- Mirror source boundaries in the test layout and group related cases in descriptive test classes.
- Give every test class and function a one-line docstring beginning with `Test that` for functions.
- Put reusable workspace and artifact builders in the nearest `conftest.py` as typed factory fixtures.
- Use synthetic consumer names and paths; public tests must not contain private repository artifacts or terminology.

## Test Boundaries

- Prefer real Pydantic models and filesystem state over `SimpleNamespace` or loosely shaped mocks.
- Patch explicit external boundaries such as subprocess and network modules, not deep internal implementation details.

## Coverage And Scenarios

- Parametrize same-shape scenarios and give parameters readable IDs.
- Verify dry runs, failure exit codes, stale cleanup, complete provider-state convergence, and idempotence.
