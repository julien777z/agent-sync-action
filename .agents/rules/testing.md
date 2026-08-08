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

- Use clearly synthetic data that is unique to each test or parametrized case unless an exact protocol or catalog literal is the contract under test; never paste exact user-provided examples into tests, and preserve only the shape or edge case being verified when inventing replacements.
- Define test helper functions at module level.
- Keep helper docstrings to a single line.
- **Builders belong in `conftest.py`, not in test files.** A "builder" is any helper whose job is to construct a domain object (Pydantic model, ORM row, request/response payload, mock with structured fields, file/path artifact, etc.) for use in tests. Promote reusable builders to fixtures in the nearest shared `conftest.py`.
- Module-level helpers are allowed only for trivial, non-construction utilities scoped to one file (predicates, small formatters, `to_comparable_string`-style assertion adapters). When in doubt, move it to `conftest.py`.

- For HTTP endpoint tests, build request payloads from the same request models used by application routes/services, then serialize with `model_dump(...)`.
- Prefer `model_dump(mode="json", exclude_unset=True, exclude_none=True)` unless the endpoint contract needs different dump options.
- Do not pass ad-hoc inline dictionaries directly to `json=` when an application request model exists.
- For mocked HTTP response bodies, prefer application response models (or shared contract response models) and serialize them with `model_dump(...)` instead of hand-rolled response dictionaries.
- Use enum members in model payloads instead of hardcoded enum strings.
- For invalid-request tests, derive from a valid model payload and then mutate/remove fields intentionally to assert validation behavior.

- Do not create module-level helper factories inside test files for reusable objects. This includes the first invocation — even a one-off "I'll just put it here for now" builder belongs in `conftest.py` from day one.
- Follow the canonical factory shape: a `@pytest.fixture` named `<noun>_factory` (for example `order_factory`, `customer_factory`, `payment_payload_factory`, or `task_factory`) that returns an inner `_build(**overrides) -> Noun` closure. Name ORM persistence fixtures for their domain action, such as `create_order` or `create_customer`; never use an `*_orm_factory` suffix.
- Put shared factories in `conftest.py` and prefer `@pytest.fixture` for setup.
- Helper functions that appear in multiple test files must be extracted to the nearest shared `conftest.py` or a `utils.py` in the test service folder.
- When multiple tests in a suite need the same config overrides, expose a reusable fixture helper (for example, `mock_config` returning `_mock_config(**overrides)`) in `conftest.py` instead of repeating `monkeypatch.setattr(...)` in each test.
- Common payload creation functions (for example, `make_create_payload`) should be defined in the service-specific `conftest.py` and exposed as `@pytest.fixture` when a default payload is sufficient.
- Keep `conftest.py` at shared test boundaries instead of scattering many topic-local `conftest.py` files.
- If tests need additional properties that belong to shared fixture models, add the missing field in the shared fixture or factory instead of hardcoding literals in test payloads.
- Prefer shared fixtures and domain-named creation fixtures over ad-hoc object setup in test modules.
- Keep reusable fixture helpers in shared `conftest.py` instead of duplicating setup in each test.
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

- Prefer shared ready fixtures that return real ORM instances. Use domain-named creation fixtures such as `create_user`, `create_account`, `create_order`, or `create_subscription` only when tests need multiple independently configured persisted roots.
- ORM factory fixtures must live in shared `conftest.py` files, not inside individual test modules.
- Factory fixtures should return real model instances with fixture-backed defaults and allow overrides via keyword arguments.
- For related entities, build real nested relationships in the factory (for example, attach a real `Customer` instance to `Order.customer`).

```python
# Good: reusable fixture-backed ORM factory in conftest.py
@pytest.fixture
def create_order(order_fixture, customer_fixture, create_customer):
    """Build Order ORM instances with nested real Customer relation."""

    def _build(**overrides):
        customer = create_customer()
        order = Orders(
            id=order_fixture.id,
            customer_id=customer_fixture.id,
            status=OrderStatus.PENDING,
        )
        order.customer = customer
        for key, value in overrides.items():
            setattr(order, key, value)
        return order

    return _build
```

## Assertions and Mocking

- Use descriptive assertions.
- For database verification, query the database directly and compare fields.
- For a substantial behavior change, cover the normal path, each meaningful boundary, and relevant validation or failure path. Do not treat a single assertion or a single happy-path case as sufficient coverage for a multi-path contract.

- Prefer third-party fakes first, then reusable test utilities, then patch-based mocks.
- Use `AsyncMock` for async functions.
- Avoid `MagicMock` for ORM/domain entities; use domain-named creation fixtures that return real instances.
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
- For every pull request an agent creates, ensure all test-related CI jobs pass before considering delivery complete; investigate and fix any failures within the pull request's scope.

- If tests cannot be run locally (for example, missing dependencies, Docker not available, or environment issues), do NOT guess what the issue is. Ask the user for the error logs instead of speculating.
- When CI tests fail and you cannot access the logs directly, ask the user to provide the failure output before attempting fixes.

## Environments

- A cloud workspace snapshot restores files, not running processes. A failing `docker info` at session start means the daemon may need to be started; it does not by itself prove Docker is unavailable.
- Prefer the repository's service-startup helper or skill. Otherwise start the daemon explicitly, wait for `docker info` to succeed, and report Docker as unavailable only when the CLI is missing or the daemon still fails with its log available.
- Browser-automation daemons may start browsers with fresh temporary profiles. Save authenticated session state explicitly and restore it after a daemon restart instead of assuming cookies survive.

## Agent Configuration Changes

- A pull request confined to canonical agent configuration and generated provider mirrors contains no application or package behavior change. Validate the Markdown and synchronization contract; do not run application suites or gate the pull request on them.
- Keep CI change-detection paths scoped to application, package, dependency, test, or runtime files so an agent-configuration-only pull request selects no application test job.
- The exemption applies to the complete pull request, not individual files. If a pull request also changes application code, package source, dependencies, tests, runtime configuration, or CI behavior, run its normal validation.

## Guardrails

- **Hardcoded test values** - Don't use literal values when fixtures provide them:
  - `UUID("00000000-...")` -> `entity_fixture.id`
  - `name="John Doe"` -> `name=user_fixture.name`
  - `email="test@example.com"` -> `email=user_fixture.email`
- **SimpleNamespace as fake domain model** - Do not build test entities with `SimpleNamespace`; use ready fixture-backed models, domain-qualified creation fixtures, or test-only `BaseModel` types.
- **Local duplicate fixtures/builders** - Do not define ad-hoc helper constructors in test modules when a shared fixture or factory already covers the use case.
- **Inline aggregate/scenario builders in test files** - Reusable domain aggregate, persisted-root, public-boundary, and multi-object scenario construction belongs in `conftest.py`. Test files should compose fixtures, not define builders.
- **Duplicate domain-object setup** - If the same construction appears in multiple tests, extract one ready fixture at the nearest shared boundary. Add a callable creation fixture only when arbitrary instance counts are required.

- Do not duplicate helper models or utility types across multiple test files. Put shared models in a shared test helper module instead.
