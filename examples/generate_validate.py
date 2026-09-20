"""Generate/validate pattern: Agent edits an artifact; Python validates it deterministically."""

import json
from dataclasses import dataclass
from pathlib import Path

from looma import agent, step, workflow


OUTPUT = Path("generated_config.json")


@dataclass
class GenerationResult:
    changed: bool
    summary: str


def validate_config(path: str):
    p = Path(path)
    if not p.exists():
        return {"valid": False, "errors": ["file does not exist"]}

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"valid": False, "errors": [f"invalid JSON: {exc}"]}

    errors = []
    if data.get("name") != "demo":
        errors.append("name must equal 'demo'")
    if not isinstance(data.get("workers"), int) or data["workers"] < 1:
        errors.append("workers must be an integer >= 1")

    return {"valid": not errors, "errors": errors, "config": data}


@workflow
def main():
    for attempt in range(3):
        validation = step(validate_config, str(OUTPUT))
        if validation["valid"]:
            return validation["config"]

        agent(
            task=(
                f"请创建或修改 {OUTPUT}，使其通过给定校验。"
                "你可以直接使用宿主 Coding Agent 的文件工具修改该文件。"
                "完成后返回 JSON：{\"changed\": bool, \"summary\": str}。"
            ),
            input={"attempt": attempt, "validation": validation},
            output_schema=GenerationResult,
        )

    return step(validate_config, str(OUTPUT))


if __name__ == "__main__":
    print(main())
