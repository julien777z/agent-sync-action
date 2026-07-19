---
description: Use explicit Pydantic models for validated configuration and generated state.
alwaysApply: true
---

# Pydantic Rules

## Model Design

- Use `BaseModel` for classes that hold application data; do not use dataclasses or named tuples.
- Use discriminated unions when variants have different required fields instead of optional fields that permit invalid combinations.
- Do not override `BaseModel.__init__` or create models dynamically.

## Validation And Serialization

- Use `ConfigDict` for model configuration and strict validation at canonical input boundaries.
- Use `model_dump()` and `model_dump_json()` for serialization.
- Keep Python fields in `snake_case` and use aliases for external key names.
- Use `Field` only for constraints, aliases, or discriminators—not descriptions.
