"""Branching pattern: Agent chooses which deterministic branch Python executes."""

from dataclasses import dataclass

from looma import agent, step, workflow


@dataclass
class RouteDecision:
    route: str
    reason: str


def collect_metrics():
    return {"latency_ms": 82, "error_rate": 0.012, "queue_depth": 14}


def use_fast_path(metrics):
    return {"selected": "fast", "metrics": metrics}


def use_safe_path(metrics):
    return {"selected": "safe", "metrics": metrics}


def escalate(metrics):
    return {"selected": "escalate", "metrics": metrics}


@workflow
def main():
    metrics = step(collect_metrics)

    decision = agent(
        task=(
            "根据服务指标选择 route。只允许 fast、safe、escalate。"
            "返回 JSON：{\"route\": str, \"reason\": str}。"
        ),
        input=metrics,
        output_schema=RouteDecision,
    )

    if decision.route == "fast":
        return step(use_fast_path, metrics)
    if decision.route == "safe":
        return step(use_safe_path, metrics)
    return step(escalate, metrics)


if __name__ == "__main__":
    print(main())
