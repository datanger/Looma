from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .exceptions import SerializationError
from .schema import validate_json_schema


def normalize_json(value: Any) -> Any:
    if is_dataclass(value):
        return normalize_json(asdict(value))
    if hasattr(value, "model_dump"):
        return normalize_json(value.model_dump(mode="json"))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): normalize_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_json(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise SerializationError(
        f"Value of type {type(value).__name__} is not JSON serializable. "
        "Values that cross a replay boundary must be JSON-compatible, dataclasses, Pydantic models, or paths."
    )


def dump_json(path: Path, value: Any) -> None:
    """Atomically persist JSON so interrupted writes do not corrupt durable state."""
    normalized = normalize_json(value)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def json_hash(value: Any) -> str:
    import hashlib

    payload = json.dumps(normalize_json(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_structural_result(value: Any, schema: Any) -> None:
    errors = validate_json_schema(value, schema)
    if errors:
        raise SerializationError(
            "Agent result does not satisfy output_schema: "
            + json.dumps(errors, ensure_ascii=False, separators=(",", ":"))
        )


def coerce_result(value: Any, schema: Any) -> Any:
    if schema is None:
        return value

    if isinstance(schema, dict):
        _validate_structural_result(value, schema)
        return value

    if hasattr(schema, "model_validate"):
        return schema.model_validate(value)

    if hasattr(schema, "__dataclass_fields__"):
        if not isinstance(value, dict):
            raise SerializationError(f"Expected JSON object for dataclass {schema.__name__}")
        from .protocol import describe_schema

        _validate_structural_result(value, describe_schema(schema))
        try:
            return schema(**value)
        except TypeError as exc:
            raise SerializationError(
                f"Invalid fields for dataclass {schema.__name__}: {exc}"
            ) from exc

    if schema in (dict, list, str, int, float, bool):
        expected_schema = {
            dict: {"type": "object"},
            list: {"type": "array"},
            str: {"type": "string"},
            int: {"type": "integer"},
            float: {"type": "number"},
            bool: {"type": "boolean"},
        }[schema]
        _validate_structural_result(value, expected_schema)
        return value

    return value
