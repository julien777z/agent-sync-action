---
name: new-env
description: When adding a new environment variable, ensure it is registered in all required locations across the repository.
---

# Adding a New Environment Variable

Every new environment variable must be added to **all** of the following locations:

## Required Locations

### 1. `.env.example` (repository root)
Add the variable with a placeholder or empty value so that developers and cloud agents pick it up automatically:
```bash
# ─── My Section ───────────────────────────────────────────────────────────────
MY_NEW_VAR=placeholder-value-or-empty
```

### 2. `packages/core/vaultgig_common/config.py` — `BaseConfig`
If the variable is shared across services, add it to the `BaseConfig` class with a sensible default (or no default if required):
```python
MY_NEW_VAR: str = ""
```

### 3. Service-specific `Config` classes
If a service needs the variable to be required (no default), override it in the service's own config:
- `apps/api/api/core/config.py`
- `services/records/records/core/config.py`
- `services/forms/forms/core/config.py`
- `services/worker/worker/core/config.py`
- `services/migrations/migrations/core/config.py`

### 4. Test environment — `pyproject.toml` `[tool.pytest.ini_options] env`
Add a test-safe value to every `pyproject.toml` that runs tests against code that reads this variable:
```toml
[tool.pytest.ini_options]
env = [
    "MY_NEW_VAR=test-value",
]
```

Files to update (add to whichever packages/services use the variable):
- `pyproject.toml` (repository root — shared / integration tests)
- `apps/api/pyproject.toml`
- `services/records/pyproject.toml`
- `services/forms/pyproject.toml`
- `services/worker/pyproject.toml`
- `packages/core/pyproject.toml`
- `packages/shared/pyproject.toml`
- `tests/pyproject.toml`

### 5. `.agents/cloud_agents/common.sh` (only if needed)
Cloud agents load `.env.example` automatically via `load_env_file`, so no explicit entry is normally required. Only add an explicit `export` here if the variable requires a non-empty value that the placeholder in `.env.example` does not provide.

### 6. GitHub repository secrets (staging / production)
For secrets or environment-specific values, add the variable to the GitHub repository secrets and reference it in the relevant workflow(s):
- `.github/workflows/run-tests.yml` (if needed by CI)
- `.github/workflows/deploy-migrations.yml` (if needed during migration runs)

## Checklist

- [ ] `.env.example`
- [ ] `packages/core/vaultgig_common/config.py` (`BaseConfig`)
- [ ] Service-specific `Config` class (if required without default)
- [ ] All relevant `pyproject.toml` test env sections
- [ ] GitHub repository secrets (for staging/production)
- [ ] Relevant workflow `env:` blocks (if needed by CI)
