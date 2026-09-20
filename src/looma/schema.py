from __future__ import annotations

from typing import Any, Mapping


def validate_json_schema(value: Any, schema: Any) -> list[dict]:
    """Validate JSON-compatible data against the subset of JSON Schema Looma emits.

    The validator intentionally focuses on structural validation needed at the
    Agent/Program boundary. It supports object/array/scalar types, required
    properties, items, enum/const, anyOf/oneOf/allOf, nullable type arrays, and
    local #/$defs references commonly produced by Pydantic.
    """
    errors: list[dict] = []
    _validate(value, schema, path="$", root=schema, errors=errors)
    return errors


def _validate(value: Any, schema: Any, *, path: str, root: Any, errors: list[dict]) -> None:
    if not isinstance(schema, Mapping):
        return

    if schema.get("type") == "any-json":
        return

    ref = schema.get("$ref")
    if isinstance(ref, str):
        target = _resolve_ref(root, ref)
        if target is None:
            errors.append({"path": path, "reason": "unresolved_ref", "ref": ref})
            return
        _validate(value, target, path=path, root=root, errors=errors)
        return

    if "allOf" in schema:
        for child in schema.get("allOf") or []:
            _validate(value, child, path=path, root=root, errors=errors)

    if "anyOf" in schema:
        choices = schema.get("anyOf") or []
        if choices and not any(not validate_json_schema_with_root(value, child, root) for child in choices):
            errors.append({"path": path, "reason": "anyOf", "expected": choices, "actual": value})
            return

    if "oneOf" in schema:
        choices = schema.get("oneOf") or []
        matches = sum(1 for child in choices if not validate_json_schema_with_root(value, child, root))
        if matches != 1:
            errors.append(
                {"path": path, "reason": "oneOf", "expected_matches": 1, "actual_matches": matches}
            )
            return

    if "const" in schema and value != schema["const"]:
        errors.append({"path": path, "reason": "const", "expected": schema["const"], "actual": value})

    if "enum" in schema and value not in schema["enum"]:
        errors.append({"path": path, "reason": "enum", "expected": schema["enum"], "actual": value})

    expected_type = schema.get("type")
    if expected_type is not None:
        allowed = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_matches_type(value, item) for item in allowed):
            errors.append(
                {
                    "path": path,
                    "reason": "type",
                    "expected": expected_type,
                    "actual_type": _json_type_name(value),
                }
            )
            return

    if isinstance(value, dict):
        required = schema.get("required") or []
        for name in required:
            if name not in value:
                errors.append({"path": f"{path}.{name}", "reason": "required"})

        properties = schema.get("properties")
        allowed_names: set[str] = set()
        if isinstance(properties, Mapping):
            allowed_names = set(properties.keys())
            for name, child_schema in properties.items():
                if name in value:
                    _validate(
                        value[name],
                        child_schema,
                        path=f"{path}.{name}",
                        root=root,
                        errors=errors,
                    )

        additional = schema.get("additionalProperties")
        if additional is False:
            for name in value:
                if name not in allowed_names:
                    errors.append(
                        {"path": f"{path}.{name}", "reason": "additional_property"}
                    )
        elif isinstance(additional, Mapping):
            for name, item in value.items():
                if name not in allowed_names:
                    _validate(
                        item,
                        additional,
                        path=f"{path}.{name}",
                        root=root,
                        errors=errors,
                    )

    if isinstance(value, list):
        items = schema.get("items")
        if isinstance(items, Mapping):
            for index, item in enumerate(value):
                _validate(item, items, path=f"{path}[{index}]", root=root, errors=errors)

        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(
                {"path": path, "reason": "minItems", "expected": min_items, "actual": len(value)}
            )

        max_items = schema.get("maxItems")
        if isinstance(max_items, int) and len(value) > max_items:
            errors.append(
                {"path": path, "reason": "maxItems", "expected": max_items, "actual": len(value)}
            )

    if isinstance(value, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            errors.append(
                {"path": path, "reason": "minLength", "expected": min_length, "actual": len(value)}
            )

        max_length = schema.get("maxLength")
        if isinstance(max_length, int) and len(value) > max_length:
            errors.append(
                {"path": path, "reason": "maxLength", "expected": max_length, "actual": len(value)}
            )


def validate_json_schema_with_root(value: Any, schema: Any, root: Any) -> list[dict]:
    errors: list[dict] = []
    _validate(value, schema, path="$", root=root, errors=errors)
    return errors


def _resolve_ref(root: Any, ref: str) -> Any | None:
    if not ref.startswith("#/") or not isinstance(root, Mapping):
        return None

    current: Any = root
    for raw_part in ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _matches_type(value: Any, expected: Any) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True


def _json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__
