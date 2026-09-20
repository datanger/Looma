from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

FIXED_PROMPT = (
    "通用说明：script 表示产生输入数据的脚本来源；output 表示脚本实际产生的数据或产物路径；"
    "task 表示需要完成的具体任务；prompt 表示本通用说明；expected_output 表示 agent 完成后期待返回的 "
    "agent2script 输出格式。请先理解各字段，再执行 task；如果信息不足，明确指出缺失信息；"
    "完成后仅按 expected_output 返回。"
)


def describe_schema(schema: Any) -> Any:
    if schema is None:
        return {"type": "any-json"}
    if isinstance(schema, Mapping):
        return dict(schema)
    if hasattr(schema, "model_json_schema"):
        return schema.model_json_schema()
    if is_dataclass(schema):
        # A dataclass instance is not expected here, but keeping this defensive.
        schema = type(schema)
    if hasattr(schema, "__dataclass_fields__"):
        props = {}
        required = []
        for name, field in schema.__dataclass_fields__.items():
            required.append(name)
            annotation = getattr(field, "type", Any)
            props[name] = {"python_type": str(annotation)}
        return {"type": "object", "properties": props, "required": required}
    builtin = {dict: "object", list: "array", str: "string", int: "integer", float: "number", bool: "boolean"}
    if schema in builtin:
        return {"type": builtin[schema]}
    return {"python_type": getattr(schema, "__qualname__", str(schema))}


def build_script2agent(
    *,
    source_script: str,
    source_function: str,
    agent_input: Any,
    task: str,
    result_file: Path,
    output_schema: Any,
    expected_script: str,
    expected_args: list[str],
) -> dict:
    schema = describe_schema(output_schema)
    enriched_task = (
        f"{task.rstrip()}\n\n"
        "运行时交接要求：\n"
        f"1. 使用 output.agent_input 作为本次 agent 调用的输入。\n"
        f"2. 将最终业务结果写入 `{result_file}`。该文件必须是 UTF-8 JSON。\n"
        f"3. 结果需满足 output.output_schema。\n"
        "4. 写入结果后，不要把业务结果放进 agent2script；最终只返回 expected_output 指定的 script 和 args。\\n"
        "5. agent2script 在执行前必须与 expected_output 严格校验；如不一致，不得执行该命令，应根据校验错误重新返回 expected_output。"
    )
    return {
        "script": {
            "path": source_script,
            "function": source_function,
            "class": None,
        },
        "output": {
            "agent_input": agent_input,
            "result_file": str(result_file),
            "output_schema": schema,
        },
        "task": enriched_task,
        "prompt": FIXED_PROMPT,
        "expected_output": {
            "script": expected_script,
            "args": expected_args,
        },
    }
