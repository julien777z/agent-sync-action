---
alwaysApply: true
---

# Testing Rules

## Test Organization

- Test directories should mirror the source code structure.
- If the source has `core/`, `models/`, `routes/`, or `services/`, keep the corresponding `unit/` and `integration/` folders aligned with those boundaries.
- Place tests next to the source subdomain they verify, not in a loosely related folder.

- Use pytest async tests (`async def test_...`).
- Group tests in classes named `TestXxx`.
- Use fixtures for setup (defined in `conftest.py` or fixture modules).
- Register custom pytest markers in `pyproject.toml` under `[tool.pytest.ini_options].markers` instead of adding them dynamically in `pytest_configure(...)` inside `conftest.py`.
- Add a single-line docstring to every test class and test function.
- Test docstrings must start with `Test that ...` (example: `"""Test that when no credentials are provided an exception is raised"""`).
- Do not include numeric HTTP status codes in test function names; use semantic status names instead (for example, `bad_request`, `not_found`, `forbidden`).

- Keep ALL imports at the top of test files.
- Never import inside test functions or methods.

## Fixtures and Test Data

- Define test helper functions at module level.
- Keep helper docstrings to a single line.
- Use Polyfactory for structured test-data factories, selecting the factory base that matches the real model type; use `ModelFactory` for Pydantic models.
- Define concrete Polyfactory classes in the nearest shared `factories.py`, set `__model__`, provide deterministic defaults, and call `.build(**overrides)` directly from tests.
- Never use `Protocol` to describe test factories or wrap factory classes in callable pytest fixtures solely for dependency injection.
- Keep `conftest.py` focused on pytest-managed setup, teardown, and dependency lifecycles.
- Use explicit shared materialization helpers for filesystem or other I/O artifacts; accept typed factory-built models and explicit target paths.
- Module-level helpers inside test files are allowed only for trivial, non-construction utilities scoped to that file (predicates, small formatters, `to_comparable_string`-style assertion adapters).

- For HTTP endpoint tests, build request payloads from the same request models used by application routes/services, then serialize with `model_dump(...)`.
- Prefer `model_dump(mode="json", exclude_unset=True, exclude_none=True)` unless the endpoint contract needs different dump options.
- Do not pass ad-hoc inline dictionaries directly to `json=` when an application request model exists.
- For mocked HTTP response bodies, prefer application response models (or shared contract response models) and serialize them with `model_dump(...)` instead of hand-rolled response dictionaries.
- Use enum members in model payloads instead of hardcoded enum strings.
- For invalid-request tests, derive from a valid model payload and then mutate/remove fields intentionally to assert validation behavior.

- Do not create module-level helper factories inside test files for reusable objects; add a concrete class to the nearest shared `factories.py` from the first call site.
- Helper functions that appear in multiple test files must be extracted to the nearest shared helper module.
- When multiple tests in a suite need the same config overrides, expose a reusable fixture helper (for example, `mock_config` returning `_mock_config(**overrides)`) in `conftest.py` instead of repeating `monkeypatch.setattr(...)` in each test.
- Common payload creation belongs in a Polyfactory class for the real request model, not a free-floating `make_*` function.
- Keep `conftest.py` at shared test boundaries instead of scattering many topic-local `conftest.py` files.
- If tests need additional properties that belong to shared fixture models, add the missing field in the shared model or Polyfactory class instead of hardcoding literals in test payloads.
- Prefer shared concrete factories over ad-hoc object setup in test modules.
- Keep reusable setup fixtures in shared `conftest.py` instead of duplicating setup in each test.
- Use fixture-backed values instead of hardcoded IDs/names/emails/tax IDs when fixtures provide them.
- Do not hardcode business-profile values when a shared fixture or factory can provide them; extend the shared fixture first when needed.

```python
# Bad: hardcoded property in a test payload
payload = {
    "website": "https://example.com",
}

# Good: add website to the shared fixture setup and use fixture data
assert account_fixture.website is not None
payload = {
    "website": account_fixture.website,
}
```

```python
async def create_entity(
    client: httpx.AsyncClient, tenant_id: str, payload: CreateEntityPayload
):
    """Create an entity."""

    response_data = parse_response(
        await client.post(...),
        CreateEntityResponse,
    )
    return response_data
```

```python
# Good: centralize repeated config overrides in conftest.py
@pytest.fixture
def mock_config(monkeypatch):
    """Create a reusable config override helper for tests."""

    def _mock_config(**overrides) -> None:
        defaults = {
            "FEATURE_FLAG_ENABLED": False,
            "API_KEY": "test-api-key",
        }
        for key, value in {**defaults, **overrides}.items():
            monkeypatch.setattr(f"app.config.CONFIG.{key}", value)

    _mock_config()
    return _mock_config
```

```python
# Good: use fixture helper in tests instead of repeated monkeypatch lines
async def test_extracts_tenant_from_token(mock_config):
    mock_config(
        ENVIRONMENT="development",
        ALLOWED_TEST_ENVIRONMENTS=("development", "staging"),
    )
    # ...
```

- Combine similar test cases with `@pytest.mark.parametrize` instead of duplicating tests.
- Tests that follow the same pattern with different inputs (for example, authorization error tests, not-found vs invalid-id, different name formats) must use `@pytest.mark.parametrize` instead of separate test methods.
- Use `@pytest.mark.parametrize` for same-shape scenarios with different inputs.
- Add readable `ids` for parametrized cases.

```python
@pytest.mark.parametrize(
    ("postal_code", "expected_region"),
    [
        ("03301", "NH"),
        ("90001", "CA"),
    ],
)
def test_lookup_region(postal_code: str, expected_region: str) -> None:
    result = lookup_postal_region(postal_code)

    assert result is not None
    assert result.region == expected_region
```

- Do not use `SimpleNamespace` for domain or API-shaped test objects; use real application models/factory fixtures or test-only `BaseModel` classes that mirror the contract.

```python
class TreeNode(BaseModel):
    name: str
    children: list["TreeNode"] = Field(default_factory=list)
```

- Use Polyfactory's `SQLAlchemyFactory` for ORM models and keep those concrete classes in the shared `factories.py` module.
- Factory-built ORM instances must use realistic defaults, accept `.build(**overrides)`, and construct real nested relationships.

## Assertions and Mocking

- Use descriptive assertions.
- For database verification, query the database directly and compare fields.

- Prefer third-party fakes first, then reusable test utilities, then patch-based mocks.
- Use `AsyncMock` for async functions.
- Avoid `MagicMock` for ORM/domain entities; use concrete Polyfactory classes that return real instances.
- `MagicMock` is acceptable for external boundaries (SDK/client response containers, subprocess handles, and network wrappers).
- For mocked third-party libraries, raise the real library exception types (for example `stripe.error.StripeError`) instead of mock-specific custom exceptions.
- In reusable mock library/fake implementations, prefer real SDK/HTTP models and response objects over `MagicMock` whenever practical.

- Test the documented and implemented SDK contract paths, not speculative runtime shapes.
- Do not add defensive tests for unsupported SDK surfaces (for example, missing required methods) when the integration contract guarantees method availability.
- If an SDK method is required by application code, tests should focus on valid responses and real failure modes from that method.
- Keep test names and docstrings aligned with behavior and outcomes rather than SDK internals; avoid exact required-method names or wording such as "when `<method>` is available."

## Configuration and Failures

- Define test configuration values (hostnames, database URLs, API keys, etc.) in `pyproject.toml` under `[tool.pytest.ini_options]` in the `env` section.
- Do NOT hardcode configuration values in `conftest.py` files.
- Access these values via `os.environ` in test code.

- If tests cannot be run locally (for example, missing dependencies, Docker not available, or environment issues), do NOT guess what the issue is. Ask the user for the error logs instead of speculating.
- When CI tests fail and you cannot access the logs directly, ask the user to provide the failure output before attempting fixes.

## Guardrails

- **Hardcoded test values** - Don't use literal values when fixtures provide them:
  - `UUID("00000000-...")` -> `entity_fixture.id`
  - `name="John Doe"` -> `name=user_fixture.name`
  - `email="test@example.com"` -> `email=user_fixture.email`
- **SimpleNamespace as fake domain model** - Do not build test entities with `SimpleNamespace`; use factory-built models or test-only `BaseModel` types.
- **Local duplicate fixtures/builders** - Do not define ad-hoc helper constructors in test modules when a shared Polyfactory class or materializer already covers the use case.
- **Inline `make_*`/`build_*`/`insert_*`/`create_*` builders in test files** - Structured test-data construction belongs in a shared concrete Polyfactory class, even for the first call site.
- **Duplicate domain-object setup** - If the same domain object construction appears in multiple tests, extract it to a shared concrete Polyfactory class.

- Do not duplicate helper models or utility types across multiple test files. Put shared models in a shared test helper module instead.
