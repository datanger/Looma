"""Retry pattern: deterministic validation controls a while loop; Agent proposes fixes."""

from dataclasses import dataclass

from looma import agent, step, workflow


@dataclass
class NextCandidate:
    value: int


def validate(value: int):
    return {
        "value": value,
        "valid": value >= 20 and value % 3 == 0,
        "rules": ["value >= 20", "value must be divisible by 3"],
    }


@workflow
def main(start: int = 5):
    value = start
    attempts = 0

    while attempts < 5:
        result = step(validate, value)
        if result["valid"]:
            return result

        proposal = agent(
            task=(
                "根据 validation 结果给出下一次尝试的整数。"
                "返回 JSON：{\"value\": integer}。"
            ),
            input={"attempt": attempts, "validation": result},
            output_schema=NextCandidate,
        )

        value = proposal.value
        attempts += 1

    return {"valid": False, "reason": "retry limit reached", "last_value": value}


if __name__ == "__main__":
    print(main())
