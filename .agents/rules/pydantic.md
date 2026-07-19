---
alwaysApply: true
---

# Pydantic Rules

## Model Design

- Never use `@dataclass` decorator from `dataclasses` module.
- Use Pydantic `BaseModel` for all class definitions that hold data.
- Do not use `NamedTuple` for application or script data models; use an explicit `BaseModel` subclass instead.
- Pydantic provides validation, serialization, and type coercion out of the box.

- Expose zero-argument boolean accessors as `@property` instead of methods when they describe model state or capability.
- Prefer property names such as `can_access_xyz` over `can_access_xyz()`.

```python
class AccessPolicy(BaseModel):
    role: str

    @property
    def can_access_admin(self) -> bool:
        return self.role == "admin"


policy = AccessPolicy(role="member")

if not policy.can_access_admin:
    raise PermissionError("Admin access required")
```

- Never use `Protocol` for data models that hold data.
- Use `Protocol` only for structural typing of interfaces (callbacks, duck typing).

- Create response models with `from_orm_model` class method for ORM conversion.
- Use `Self` return type for class methods.

## Validation and Configuration

- Use `model_config = ConfigDict(...)` for model configuration.
- Use `model_dump()` instead of deprecated `dict()`.
- Use `model_validator` decorator for custom validation.
- Do not add `field_validator` or `model_validator` just to coerce enum strings that should be represented by the enum itself; update the enum values to match the real contract instead.
- Do not define `__init__` on `BaseModel` subclasses; use fields, validators, `model_post_init`, or factory/class methods instead.
- Never use `pydantic.create_model`; define an explicit `BaseModel` subclass instead.
  If `create_model` feels necessary, the design is probably too dynamic or too clever; refactor toward a named model class.

```python
from enum import StrEnum

from pydantic import BaseModel, field_validator


class ShirtSize(StrEnum):
    SMALL = "small"
    LARGE = "large"

# Bad: validator added only to paper over the wrong enum values
class TShirtOrderBad(BaseModel):
    size: ShirtSize

    @field_validator("size", mode="before")
    @classmethod
    def validate_size(cls, value: str) -> str:
        return value.upper()
```

## Fields and Serialization

- Do not use `Field(...)` when only providing a description; field names should be self-explanatory.
- Only use `Field(...)` when applying actual constraints (for example, `min_length`, `max_length`, `ge`, `le`, `pattern`).
- Use `snake_case` for all Pydantic field names, even when an external API returns `camelCase`.
- When an external payload uses a different key style, keep the Python attribute in `snake_case` and map the external key with `Field(alias=...)` instead of mirroring the external casing in the model.

```python
from datetime import date

# Good: snake_case field with alias for external camelCase payload
class ExternalCustomer(BaseModel):
    last_name: str | None = Field(default=None, alias="lastName")
    date_of_birth: date | None = Field(default=None, alias="dateOfBirth")

# Bad: camelCase field names copied into the model
class ExternalCustomer(BaseModel):
    lastName: str | None = None
    dateOfBirth: date | None = None
```

```python
from pydantic import Field

# Good: no Field when just documenting
class WidgetPosition(BaseModel):
    id: str
    x: int
    y: int

# Good: Field with actual constraint
class WidgetLayout(BaseModel):
    layout_id: str = Field(..., min_length=1)

# Bad: Field only for description
class WidgetPosition(BaseModel):
    id: str = Field(..., description="Unique widget identifier")
    x: int = Field(..., description="X position")
```
