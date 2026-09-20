from __future__ import annotations

import types
from collections.abc import Mapping as ABCMapping
from dataclasses import MISSING, fields, is_dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Union, get_args, get_origin, get_type_hints

FIXED_PROMPT = (
    "通用说明：script 表示产生输入数据的脚本来源；output 表示脚本实际产生的数据或产物路径；"
    "task 表示需要完成的具体任务；prompt 表示本通用说明；expected_output 表示 agent 完成后期待返回的 "
    "agent2script 输出格式。请先理解各字段，再执行 task；如果信息不足，明确指出缺失信息；"
    "完成后仅按 expected_output 返回。"
)


def _annotation_schema(annotation: Any) -> dict:
    if annotation is Any:
        return {"type": "any-json"}

    if hasattr(annotation, "model_json_schema"):
        return annotation.model_json_schema()

    if isinstance(annotation, type) and is_dataclass(annotation):
        return describe_schema(annotation)

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (Union, types.UnionType):
        choices = [_annotation_schema(arg) for arg in args]
        return {"anyOf": choices}

    if origin is Literal:
        values = list(args)
        schema: dict[str, Any] = {"enum": values}
        if values:
            value_types = {_json_schema_type(type(v)) for v in values}
            value_types.discard(None)
            if len(value_types) == 1:
                schema["type"] = next(iter(value_types))
        return schema

    if origin in (list, tuple, set, frozenset):
        item_schema = _annotation_schema(args[0]) if args else {"type": "any-json"}
        return {"type": "array", "items": item_schema}

    if origin in (dict, Mapping, ABCMapping):
        value_schema = _annotation_schema(args[1]) if len(args) >= 2 else {"type": "any-json"}
        return {"type": "object", "additionalProperties": value_schema}

    schema_type = _json_schema_type(annotation)
    if schema_type is not None:
        return {"type": schema_type}

    return {"python_type": getattr(annotation, "__qualname__", str(annotation))}


def _json_schema_type(annotation: Any) -> str | None:
    builtin = {
        dict: "object",
        list: "array",
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        type(None): "null",
    }
    return builtin.get(annotation)


def describe_schema(schema: Any) -> Any:
    if schema is None:
        return {"type": "any-json"}

    if isinstance(schema, Mapping):
        return dict(schema)

    if hasattr(schema, "model_json_schema"):
        return schema.model_json_schema()

    if not isinstance(schema, type) and is_dataclass(schema):
        schema = type(schema)

    if isinstance(schema, type) and is_dataclass(schema):
        properties: dict[str, Any] = {}
        required: list[str] = []
        try:
            type_hints = get_type_hints(schema)
        except Exception:
            type_hints = {}

        for field in fields(schema):
            annotation = type_hints.get(field.name, field.type)
            properties[field.name] = _annotation_schema(annotation)
            if field.default is MISSING and field.default_factory is MISSING:
                required.append(field.name)

        result: dict[str, Any] = {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        }
        if required:
            result["required"] = required
        return result

    schema_type = _json_schema_type(schema)
    if schema_type is not None:
        return {"type": schema_type}

    return _annotation_schema(schema)


def build_script2agent(
    *,
    source_script: str,
    source_function: str,
    agent_input: Any,
    task: str,
    result_file: Path,
    input_schema: Any,
    output_schema: Any,
    expected_script: str,
    expected_args: list[str],
) -> dict:
    schema = describe_schema(output_schema)
    input_schema_description = (
        describe_schema(input_schema) if input_schema is not None else None
    )
    enriched_task = (
        f"{task.rstrip()}\n\n"
        "运行时交接要求：\n"
        "1. 使用 output.agent_input 作为本次 agent 调用的输入；若存在 output.input_schema，"
        "该输入已经由 Runtime 校验通过。\n"
        f"2. 将最终业务结果写入 `{result_file}`。该文件必须是 UTF-8 JSON。\n"
        "3. 结果需满足 output.output_schema。\n"
        "4. 写入结果后，不要把业务结果放进 agent2script；最终只返回 expected_output 指定的 script 和 args。\n"
        "5. agent2script 在执行前必须与 expected_output 严格校验；如不一致，不得执行该命令，应根据校验错误重新返回 expected_output。"
    )
    output = {
        "agent_input": agent_input,
        "result_file": str(result_file),
        "output_schema": schema,
    }
    if input_schema_description is not None:
        output["input_schema"] = input_schema_description

    return {
        "script": {
            "path": source_script,
            "function": source_function,
            "class": None,
        },
        "output": output,
        "task": enriched_task,
        "prompt": FIXED_PROMPT,
        "expected_output": {
            "script": expected_script,
            "args": expected_args,
        },
    }
