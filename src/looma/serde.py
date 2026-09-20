from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .exceptions import SerializationError


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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(normalize_json(value), f, ensure_ascii=False, indent=2, sort_keys=True)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def json_hash(value: Any) -> str:
    import hashlib

    payload = json.dumps(normalize_json(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def coerce_result(value: Any, schema: Any) -> Any:
    if schema is None or isinstance(schema, dict):
        return value
    if hasattr(schema, "model_validate"):
        return schema.model_validate(value)
    if hasattr(schema, "__dataclass_fields__"):
        if not isinstance(value, dict):
            raise SerializationError(f"Expected JSON object for dataclass {schema.__name__}")
        return schema(**value)
    if schema in (dict, list, str, int, float, bool):
        if not isinstance(value, schema):
            raise SerializationError(f"Expected {schema.__name__}, got {type(value).__name__}")
        return value
    return value
