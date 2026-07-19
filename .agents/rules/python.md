---
description: Follow modern Python typing, import, formatting, error handling, and maintainability conventions.
alwaysApply: true
---

# Python Rules

## Syntax and Typing

- Use modern type hints: `str | None` instead of `Optional[str]`.
- Use built-in generics: `list[T]`, `dict[K, V]` instead of `List[T]`, `Dict[K, V]`.
- Use `Self` from `typing` for class method return types.
- Use `collections.abc` for abstract types: `Callable`, `Iterable`, etc.
- Never use `Protocol` for model typing; use concrete model classes in type annotations.

- Model structured payloads explicitly: use `TypedDict` for mapping-shaped data and `BaseModel` when validation or serialization is required, rather than arbitrary inline dictionaries or `dict[str, object]`.
- Use exact types or precise unions for dynamic and nested shapes; never hide their contracts behind `Any` or placeholder `object` fields in application or test annotations.
- Prefer real SDK and model types over `cast(...)`; reserve a narrowly scoped cast for information the type system genuinely cannot express.
- Do not "fix" typing by expanding simple transformations into repetitive key-by-key copy blocks (for example, manually assigning each dict key only to satisfy pyright). Fix the source type hints (or add a precise cast/narrowing at the boundary) so the transformation can stay concise and readable.
- For persistence/update payloads (for example, `upsert(...)`), define a dedicated `TypedDict` and construct it inline at the call site. Do not add free-floating `build_*`/`make_*` helper functions whose only role is constructing a payload from another shape; the same no-free-floating-builders rule that applies to `BaseModel` applies here.
- When a `TypedDict` types a module-level constant or other shared blob (for example a CVA style config), build the value by **calling** the TypedDict constructor with keyword arguments (`MyTypedDict(field=value, ...)`) instead of assigning an annotated plain dict literal (`name: MyTypedDict = {...}`). Use the same for nested TypedDict rows inside lists (for example `CompoundVariantRule(match={...}, class_name="...")`). This keeps the type as the construction site, not only a static annotation on a dict literal. Requires Python 3.12+.

- Group parameters that always travel together and describe one concept into a single typed object, then pass that object rather than threading its fields through every signature and call site.

```python
from typing import TypedDict


class RequestContext(TypedDict):
    source_address: str | None
    client_name: str | None


# Bad: related values threaded as separate arguments
def record_event(event: Event, source_address: str | None, client_name: str | None) -> None:
    ...


# Good: one typed object describing the shared concept
def record_event(event: Event, request_context: RequestContext) -> None:
    ...
```

- Use `datetime` objects instead of raw integers (Unix timestamps) for representing time.
- Use `timedelta` for durations instead of raw integers (for example, `timedelta(seconds=10)` instead of `10`).
- For database columns, use `DateTime` or `Date` types from SQLAlchemy.
- For Pydantic models, use `datetime.datetime` or `datetime.date` types.

- Use a leading underscore **only** for nested definitions: a function defined inside another function or method (inner function), and a class defined inside another class (inner class).
- Everything else must **not** start with a leading underscore. This includes module-level functions, classes, Pydantic/ORM models, enums, `TypedDict`s, type aliases, and constants; **methods** (instance methods, `@classmethod`, and `@staticmethod`); and **module / file names**.
- Do not use a leading underscore to mark a method or a module-level helper as "private". Express privacy through module boundaries and `__all__` instead.
- This rule does not govern Python dunders (`__init__`, `__enter__`, …) or single-underscore names owned by third-party/stdlib code.

```python
class Report(BaseModel):
    @classmethod
    def from_rows(cls, rows: list[Row]) -> Self:
        def _format_row(row: Row) -> str:
            return f"{row.id}: {row.name}"

        return cls(lines=[_format_row(row) for row in rows])
```

- Prefer string enums for string-valued domains instead of loose string constants.

## Imports and Modules

- Never name a module by joining two different concepts with an underscore — `resource_export.py` is "resource" + "export". Create a package for the entity and a topic module inside it: `resource/export.py`. The same applies when adding a second module for an entity that already has one (`resource.py` + `resource_access.py` must become the package `resource/` with `resource.py` and `access.py` inside).
- Inside an entity package, do not repeat the entity in module names: `resource/sync.py`, never `resource/resource_sync.py`.
- Compound nouns that name a single concept are one entity, not two — `access_control.py`, `request_metadata.py`, and `audit_trail.py` are all fine.
- When the entity package needs a module for its primary/orchestration surface, name it after the package (`resource/resource.py`) with an empty `__init__.py`; consumers import the specific submodule.

- Do not start Python files with module docstrings. Begin with imports, or leave package `__init__.py` files empty when they have no public surface.
- Keep ALL imports at the top of the file.
- Never import inside functions, methods, or test cases.
- Group imports: stdlib, third-party, local (separated by blank lines).
- Prefer **absolute imports** from the top-level package (for example `from application.routes.resources import router`) over **relative imports** with parent segments (for example `from ....routes.resources import router`). Absolute imports are stable when modules move, easier to grep, and avoid brittle `..` depth. Same rule applies to other installable packages: always anchor imports on the package name, not on the file’s directory depth.
- Never use import aliases for project modules; import the canonical symbol/module name and update call sites to that name instead of aliasing.
- Use `__all__` exports in module `__init__.py` files.
- Never define variables or call functions in between import statements; all imports must be contiguous at the top of the file.
- Never create shim modules that only re-export symbols from another package for backwards compatibility; update all consumers to import from the canonical source instead.
- Do not create a dedicated module for one generic stateless helper. Keep small cross-cutting helpers in the package's `utils.py`, and extract a focused module or package only when a cohesive domain or external boundary warrants it.
- Narrow exception: `__main__.py` entrypoints may use same-package relative imports for bootstrap (for example `from .runtime import main`), and `__init__.py` may use explicit relative imports when assembling the package’s public surface.

```python
# Bad: shim module that only re-exports symbols
from .http_transport import fetch, fetch_with_cache

__all__ = ["fetch", "fetch_with_cache"]

# Bad: consuming through a shim module
from myapp.http import fetch

# Good: import from the canonical source directly
from myapp.http_transport import fetch
```

- Prefer real fixes (annotations, stubs, deps). If a Pylint/static warning is a false positive or unfixable in our code (for example lazy third-party exports, missing stubs), use a **narrow** suppression: `# pylint: disable-next=<message-id>` on the smallest scope—never file-wide disables or import workarounds whose only purpose is to satisfy the checker.

```python
# pylint: disable-next=not-callable
config = third_party_package.Config(
    app_name="example",
)
```

## Configuration and Constants

- Define constants at the top of the file, after imports.
- Place module-level constants and enums (including type aliases like `AllowedApiClient`) directly after imports.
- Use `Final[T]` type annotation from `typing` for constants.
- When a mutable object is annotated with `Final`, complete any setup-time mutation in the same expression as initialization instead of binding it first and mutating it on the next line.
- Use UPPER_SNAKE_CASE naming convention for constants.
- Only extract literals to constants when they are reused, configurable, or carry domain meaning; keep trivial single-use literals inline (for example, delimiters like `"-"` or `"."`).
- Never hard-code constants like HTTP status codes; use `HTTPStatus` from the `http` module instead.
- Prefer enums for error identifiers/messages instead of a constant per error string.

- A group of related **configuration values** (API hosts, endpoint paths, protocol versions, header tokens, feature markers, default model names, timeouts) is not a set of constants — collect it into a **single typed config map**, not one `Final` per value.
- Model the map with a `TypedDict` and build it by **calling** the constructor with keyword arguments (`CONFIG: Final[ReviewConfig] = ReviewConfig(...)`), then read values by key (`CONFIG["routine_host"]`). Do not annotate a plain dict literal.
- Reserve standalone `Final` constants for genuinely single, unrelated constants — a compiled regex, a file path, a sentinel — that do not belong to a config group.
- This is about grouping; it does not override the **Configuration** section below. Environment-backed values, or values that belong in the repository's central settings layer, still go there — not in a module-level map.

```python
from typing import Final, TypedDict

# Bad: one config group spread across many individual constants
SERVICE_BASE_URL: Final[str] = "https://api.example.com/v1"
API_VERSION: Final[str] = "2026-01-01"
FEATURE_TOKEN: Final[str] = "example-feature"
REQUEST_MARKER: Final[str] = "<!-- request-marker -->"

# Good: one typed config map, built by calling the TypedDict constructor
class ServiceConfig(TypedDict):
    base_url: str
    api_version: str
    feature_token: str
    request_marker: str


CONFIG: Final[ServiceConfig] = ServiceConfig(
    base_url="https://api.example.com/v1",
    api_version="2026-01-01",
    feature_token="example-feature",
    request_marker="<!-- request-marker -->",
)
```

- Only **environment-backed or deployment-tunable** values (allowed environments, feature flags, limits, timeouts an operator may change) belong in the repository's typed configuration layer.
- Fixed third-party endpoint URLs and values fully derived from existing config (for example a from-address derived from `CONFIG.DOMAIN`) are **module-level `Final` constants** in the module that uses them, not config fields.
- API keys and secrets must be **required** config fields with **no defaults** (no `= ""` or `| None = None` escape hatches); optionality is reserved for credentials with a documented ambient fallback (for example AWS IAM role credentials).
- Avoid large piles of module-level constants. If a value is genuinely operator-tunable, add it to the project's central config model or settings layer.
- Do not add useless config values like `DEFAULT_ENVIRONMENT`.
- Do not add helper functions like `_get_environment` when the value already exists on `CONFIG`.
- Do not read environment variables directly with `os.getenv`, `os.environ`, or `os.environ.get` in application/service/library code.
- Always read environment-backed values from the typed config object so defaults, validation, and normalization live in one place.
- Exception: one-off scripts may read from `os` when introducing a `CONFIG` model would be unnecessary overhead.

- **Never commit development or test secret values into application or library code** — not even to compare against them. Embedding a known dev key (or its hash) so the code can reject it just moves the secret *into* the codebase, which is the opposite of the goal. Real secrets live in the secrets manager; test secrets live in test configuration (`pyproject.toml` env), never in `.py` source.
- **Do not branch on the environment in application code to relax or vary security posture** (`if ENVIRONMENT == "development": allow the weaker cipher / skip the check`). Which crypto backend, keys, and credentials are used is a deployment concern: production sets the real backend and secrets, tests set test values via test config. Application code states the single required contract (for example "encryption is AWS/KMS") and lets it hold everywhere.
- **Let the owning library validate its own contract; do not duplicate it behind an environment gate.** If a third-party SDK already requires a key for its selected method, do not re-implement that check in our config with environment branches — that is redundant and drifts.

## Functions and Interfaces

Avoid trivial wrapper functions that add no value. A function that just returns its argument or applies a trivial fallback is noise:

- Do not rebind function arguments to a second local name when the value is unchanged (for example, `profile = obj`); name the parameter correctly at the signature instead.
- Do not add passthrough function or method parameters when every call site provides the value from one shared source (for example, forwarding `timeout_seconds` from `CONFIG` in every call); read from that source directly where the value is used.

- Prefer normal attribute assignment over `object.__setattr__(...)` when mutating Pydantic models in validators or helper methods.
- Only use `object.__setattr__(...)` when normal assignment is genuinely unavailable (for example frozen models or descriptor bypass requirements), and keep that escape hatch explicit and justified.

```python
# Bad: useless wrapper
def resolve_config(config: Settings | None) -> Settings:
    return config or CONFIG

def get_auth_secret(config: Settings | None = None) -> str:
    resolved = resolve_config(config)  # Unnecessary indirection
    return resolved.SECRET

# Good: inline the fallback
def get_auth_secret(config: Settings | None = None) -> str:
    resolved = config or CONFIG
    return resolved.SECRET
```

## Architecture and Boundaries

- Application code (a function, method, property, class, constant, or field) with **zero non-test consumers** is dead code and must be deleted, along with the tests that only exist to exercise it.
- **Tests do not justify keeping otherwise-unused application code.** A test that asserts a symbol no other application code reads is testing a fabricated contract; delete the symbol and that test together rather than preserving the symbol "because it's covered".
- "Consumer" means live application/library code that reads the symbol — call sites, internal use by another live symbol, serialization, or a public package export in `__all__` that external packages import. Test modules are not consumers.
- A symbol reached only indirectly through another symbol that is itself dead is also dead; remove the whole unused chain.
- **Config fields that populate environment variables consumed by a third-party library are not dead code**, even when no application code reads the field directly. If a dependency we rely on reads an env var at runtime (for example a library whose `Settings` reads `ENCRYPTION_METHOD`/`ENCRYPTION_KEY`), the field must stay on `CONFIG` so the application sets that env var — the library is the consumer. Keep such fields and validate them where the environment requires it.

- For values persisted in databases, queues, or cross-service contracts (for example handler names, event names, state keys), use explicit constants or enums.
- Do not derive durable identifiers from implementation details like `function.__name__`.
- Keep durable identifiers in shared model/contract modules when they are used across services.

```python
from enum import StrEnum


class TaskHandlerKey(StrEnum):
    PROCESS_RESOURCE = "process_resource"

# Good: explicit durable key
register_task(task_type=TaskType.PROCESS_RESOURCE, handler_name=TaskHandlerKey.PROCESS_RESOURCE.value)

# Bad: fragile runtime-derived key
register_task(task_type=TaskType.PROCESS_RESOURCE, handler_name=handler.__name__)
```

- Avoid monolithic service modules that mix orchestration, third-party API calls, policy decisions, and data mappers.
- Split large services into focused modules, for example:
  - orchestration module (route-facing flow)
  - gateway module (external/internal API client calls)
  - domain helper modules (policy/state decisions, AI resolution, etc.)
- Keep public service function signatures stable while refactoring internals.
- **No upward imports**: `lib/` must never import from `services/`. Shared infrastructure both tiers need (client factories, session wiring, config) lives in `core/`, which either tier may import.
- **Orchestration does not live under `lib/`**: a module whose functions are route-facing entry points (they accept request-shaped inputs and return response models) belongs in `services/`, even if it started life as a helper. Keep the pure helpers (query builders, row/CSV machinery, mappers) in `lib/` and move only the orchestrator.
- **A transport-only "service" is a gateway**: a `services/` module whose functions only wrap internal-service or external API calls belongs in `lib/<domain>/gateway.py`; keeping it under `services/` invites upward imports from other lib modules.

- When multiple functions compute the same derived state (for example completion/missing stage lists), centralize that logic in one helper.
- Reuse the helper across read paths to avoid behavior drift.

- Keep explicit wrapper/helper functions for external dependencies so tests can patch clear module boundaries.
- Prefer patching module-level seams (for example `resource_gateway.fetch_resource`) over patching deep nested internals.

## Runtime Data and Caching

- Never use plain dictionaries (module-level, class-level, or any other in-process container) as caches for data that must stay correct across requests, workers, or deployments. In-process dict caches silently go stale, diverge between workers, and cannot be invalidated remotely.
- For cross-request or cross-process caching, use a distributed caching library such as Redis or the repository's shared caching layer, and always set an explicit TTL.
- Pair every cache write path with an explicit invalidation path for mutations that change the cached value.
- Request-scoped memoization is the only acceptable dict-shaped cache: it must be held in a `ContextVar`, reset at the start of every request, and invalidated on writes within the request.

- Use `@cache` (from `functools`) for expensive, deterministic builders that should be created once per process (for example, AI agents, parsed static configs, immutable lookup tables).
- Only cache functions whose return value is safe to reuse and does not depend on request-scoped state.
- Do not cache values that depend on mutable runtime inputs (per-request user data, DB sessions, auth context, timestamps).
- Keep cached builders side-effect free and parameter-light.

```python
from functools import cache

@cache
def build_classification_agent() -> Agent[None, ClassificationResult]:
    return Agent(...)
```

## Control Flow and Collections

- Combine conditional branches with `or` when they have the same body (including separate `if` statements and `if`/`elif` chains).
- Do not use an `if`/`else` block just to choose which attribute or mapping values to read. When the goal is only to select a source object and then read the same fields, resolve the source once with `or` and read from that single variable.

```python
# Good: combined conditions in one branch
if not principal.scope_id or principal.scope_id != scope_id:
    raise PermissionError("Principal cannot access this scope")

# Bad: separate branches with identical bodies
if not principal.scope_id:
    raise PermissionError("Principal cannot access this scope")

if principal.scope_id != scope_id:
    raise PermissionError("Principal cannot access this scope")
```

```python
# Good: resolve the source once, then read fields once
request_payload = request or {"name": ""}
resolved_name = request_payload["name"]
resolved_slug = request_payload.get("slug") or ""

# Bad: duplicated field extraction across branches
if request is None:
    resolved_name = ""
    resolved_slug = ""
else:
    resolved_name = request["name"]
    resolved_slug = request.get("slug") or ""
```

- For find-first patterns, use `next()` with a generator expression instead of a `for` loop with a nested `if` and early `return`/`break`.
- For filtering, prefer generator expressions or `filter(...)` over `for` loops that conditionally append to a list.

```python
# Bad: for loop with trivial nested if for find-first
for item in items:
    if item.id == target_id:
        return item.value

# Good: next() with generator expression
return next(
    (item.value for item in items if item.id == target_id),
    None,
)
```

- Use `match` statement instead of chains of `if`/`elif` statements when dispatching on enum members or discriminant values.
- For data-driven column/field selection with many independent boolean flags, prefer a declarative mapping iterated in a loop over repeated `if` blocks.
- Use enums with descriptive string values for column names, header labels, and other user-facing strings instead of raw string literals scattered across functions.

## External APIs and Errors

- Verify SDK method availability before coding integrations:
  - Prefer checking official docs with `@Browser`, or
  - Inspect the installed SDK directly (for example with Python `inspect`/`hasattr`) in the current environment.
- Do not add defensive attribute checks or fallback branches for third-party SDK methods (for example, catching `AttributeError` to try an alternate call path).
- Call the expected SDK method directly; if the integration changes, update it explicitly rather than supporting multiple speculative shapes in runtime code.

```python
# Bad: speculative fallback for a "maybe async, maybe sync" SDK shape
try:
    resources = await sdk.resources.list_async(
        scope_id=scope_id,
        resource_id=[resource_id],
        limit=1,
    )
except AttributeError:
    resource = sdk.resources.get(
        scope_id=scope_id,
        resource_id=resource_id,
    )

# Good: call the expected method directly
resources = await sdk.resources.list_async(
    scope_id=scope_id,
    resource_id=[resource_id],
    limit=1,
)
```

- Never insert fabricated placeholder values (for example `user-{id}@blank.com`) into database columns in application code to satisfy NOT NULL or UNIQUE constraints.
- If a required field is unavailable at a code path, fetch the real value from its authoritative source (for example an external identity provider API) or make the caller supply it.
- Placeholder backfills for legacy data belong exclusively in database migrations, not in runtime service logic.

- Implement only the single contract used by the current boundary (database schema, SDK contract, or API model).
- Do not widen types or add compatibility branches for alternate shapes that are not part of the real contract.
- Example: If the DB column type is `UUID`, function parameters and call sites should use `UUID` only (not `UUID | str` with runtime conversion).
- Prefer fixing call sites to provide the correct type over adding defensive conversion logic in core helpers.

```python
# Bad: backward-compatible branch for an unsupported secondary shape
async def get_source_id(session: AsyncSession, resource_id: UUID | str) -> str | None:
    resolved_resource_id = UUID(resource_id) if isinstance(resource_id, str) else resource_id
    resource = await Resource.get_one(session, where=Resource.id == resolved_resource_id)
    ...

# Good: single, complete implementation aligned to DB contract
async def get_source_id(session: AsyncSession, resource_id: UUID) -> str | None:
    resource = await Resource.get_one(session, where=Resource.id == resource_id)
    ...

# Good call site: convert once at boundary
raw_resource_id = response.json()["data"]["resource_id"]
source_id = await get_source_id(session, UUID(raw_resource_id))
```

- Read required data from its single canonical source — an SDK catalog/list call, a typed config value, a generated client — and use it directly. The implementation must be complete against that source, not hedged with a fallback.
- Do not wrap a canonical lookup in a `try`/`except` that swallows the failure and continues with a guessed value, a default, or a degraded mode. That hides drift and turns a real outage into silently wrong behavior. Let a genuine failure propagate to the normal error path so it fails loudly and gets fixed at the root.
- Handling a legitimate, expected *state* of the canonical data is fine (for example, a catalog entry that has no optional variant, so you use the base value). Inventing a substitute when the source is *unavailable or malformed* is not.
- If you catch yourself writing "if the lookup fails, use X instead", the fix is to make the lookup reliable (or to fail), not to paper over it with a fallback branch.

```python
# Bad: swallow a catalog failure and silently degrade to the default behavior
try:
    catalog = await client.list_models()
    variant = pick_variant(catalog)
except SomeError:
    variant = None  # silently falls back to the wrong/default behavior

# Good: use the canonical source completely; a real failure propagates to the caller's error path
catalog = await client.list_models()
variant = pick_variant(catalog)
```

- Use `HTTPStatus` enum from the `http` module instead of raw integer status codes.
- Import as: `from http import HTTPStatus`.
- Use your framework's standard error response type instead of hand-rolled JSON response bodies when the project already defines one.

```python
from http import HTTPStatus

# Good: use a typed or framework-standard error response
raise HttpError(
    status_code=HTTPStatus.NOT_FOUND,
    detail="Resource not found",
)

# Bad: using raw integer status code with JSONResponse
return JSONResponse(
    status_code=404,
    content={"error": "Resource not found"},
)
```

- Never catch bare `Exception`; always catch specific exception types unless that broad exception is being explicitly tested in a test case.
- For generated or SDK-backed API clients, catch the library's documented exception type instead of broad exceptions.

```python
import third_party_client

# Good: catch specific exception
try:
    response = await client.get_resource(...)
except third_party_client.ApiException as exc:
    logger.warning("Resource API call failed: %s", exc)

# Bad: catch all exceptions
try:
    response = await client.get_resource(...)
except Exception as exc:
    logger.warning("API call failed: %s", exc)
```

## Formatting and Documentation

- Never use vague, cute, or placeholder terminology in identifiers, docstrings, comments, or test names. Name things for the behavior they actually have. This applies to **new and pre-existing code** — if you touch a file that still uses a banned term, rename it.
- Banned terms and what to use instead:
  - **"best effort"** — state the real contract. A function that swallows failures and reports the outcome should say so: name it `try_<verb>` (for example `try_send_email`) and document it as "returning whether it succeeded", not "best-effort".
  - **"seed" / "seeds" / "seeding"** (for test data or sample records) — name the helper for what it builds: a `<noun>_*_factory` fixture, `create_*`, or "sample data". Do not call setup data a "seed".
- If you reach for a placeholder-ish term a future reader could not decode from the name alone, pick a more intuitive name instead of adding it to this list.

- Add a blank line after each docstring.
- Never add decorative separator comments (for example, `# -----` headers).
- Add a blank line after multi-line statements (function calls, context managers, etc.) before the next statement.
- Add a blank line before terminating statements (`sys.exit()`, `return`, `raise`) to visually separate them from preceding code.
- Use blank lines as logical phase boundaries. Keep consecutive assignments or calculations together only when they jointly prepare one check, transformation, or result.
- Insert a blank line whenever adjacent statements advance to a different responsibility, even when both are short. In particular, separate an action from logging or other reporting; separate construction of an object from configuring or using it; and separate each independently configured parser or command group from the next.
- At module scope, separate runtime collaborators such as loggers from subsequent constants, type aliases, enum declarations, or configuration data. Keep the declarations together only when they form their own cohesive group.
- A short compact block (2–3 lines) may stay together only when every line directly contributes to the same operation. Do not use compactness alone as a reason to remove a logical boundary.
- When consecutive lines switch to a different statement kind (for example `assert` to a mock-verification call, or `setattr(...)` to an unrelated assignment), insert a blank line when the new statement begins a new logical group.
- Add a blank line after setup/initialization code before the main logic begins.

```python
# Good: blank line separates setup from main logic
artifacts_dir = tmp_path / "artifacts"
artifacts_dir.mkdir()

create_artifact(artifacts_dir, "first", None)
create_artifact(artifacts_dir, "second", "first")

# Bad: no separation between setup and main logic
artifacts_dir = tmp_path / "artifacts"
artifacts_dir.mkdir()
create_artifact(artifacts_dir, "first", None)
```

```python
# Good: related setup stays together, then one blank line introduces validation
start_marker = FORMAT["start_marker"]
end_marker = FORMAT["end_marker"]
start_count = content.count(start_marker)
end_count = content.count(end_marker)

if start_count != end_count:
    raise ValueError("Managed markers are malformed")
```

```python
# Good: action and reporting are separate responsibilities
perform_update(records)

logger.info("Update complete")

# Good: keep construction separate from later setup and use
parser = argparse.ArgumentParser()

subparsers = parser.add_subparsers(dest="command", required=True)

create_parser = subparsers.add_parser("create")
create_parser.add_argument("--dry-run", action="store_true")

validate_parser = subparsers.add_parser("validate")
validate_parser.set_defaults(dry_run=False)

parsed_arguments = parser.parse_args(arguments)

# Good: a runtime collaborator is separate from module declarations
logger = logging.getLogger(__name__)

MAX_ITEMS: Final[int] = 20
ALLOWED_STATES: Final[frozenset[str]] = frozenset({"ready", "complete"})
```

- Add a blank line before multi-line assert statements.
- Do NOT put docstrings or comments at the top of files (no module-level docstrings, no module-level comments, and no encoding header comments like `# coding: utf-8`); `__init__.py` files should either be empty or contain only imports and `__all__`.

- Every **function**, **method**, and **class** should have a one-line docstring (purpose or role). Include `main()` and nested helpers the same way unless the file’s existing style omits docstrings on tiny locals—when in doubt, add one line.
- Keep docstrings to a single line. Do not include Args, Returns, or Raises sections.
- Class docstrings go directly after the class definition.
- Docstrings describe current behavior only — never reference what the code replaces, used to do, or PR/migration history. The docstring must read the same to a new reader who never saw the prior version.

- **Comments are only for third-party quirks** — an SDK bug, a library's surprising contract, a spec oddity, a protocol requirement — that a reader could not infer from our own code. If the reason lives in code you control, it is not a comment.
- **If your own code needs a comment to be understood, the code is too complex — refactor it instead.** Rename the identifier, extract a well-named helper, split the function, or restructure until the intent is obvious without prose. Reach for a comment only after the code cannot be made clearer and the remaining "why" is genuinely external.
- **Never explain behavior in a comment — tests assert behavior.** Do not narrate what a branch, guard, ordering, or invariant does or protects against; encode that in a test that fails when it regresses. The test is the durable, executable specification; the comment is not.
- **Keep any comment to 1–2 lines**, factual, and about the external quirk only. A comment that runs longer is a signal the code (or the abstraction) needs restructuring, not more prose.
- Comments describe the current external quirk only — never reference what the code replaces, used to do, what was deleted, the current task/fix/PR, or callers ("previously…", "legacy…", "now uses X instead of Y", "added for the Y flow", "used by X"). Those belong in the PR description, not the source.

## Logging

- Use the `logging` module instead of `print()` for debugging, status, progress, or diagnostics in any code, including scripts and CLI tools.
- Configure a logger at the top of each module: `logger = logging.getLogger(__name__)`.
- Use appropriate log levels: `debug`, `info`, `warning`, `error`, `critical`.

## Guardrails

- Do not remove intentional feature logic merely because it looks extra; verify the active request, nearby tests, and call sites before deleting newly added code.
- If style-cleanup instructions conflict with clear feature intent, preserve behavior first and ask a clarifying question instead of removing the feature code.
