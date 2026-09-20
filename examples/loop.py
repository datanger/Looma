from dataclasses import dataclass

from looma import agent, step, workflow


@dataclass
class Review:
    done: bool
    next_value: int


def evaluate(value: int):
    return {"value": value, "square": value * value}


@workflow
def optimize(start: int):
    value = start
    for iteration in range(3):
        metrics = step(evaluate, value)
        review = agent(
            task=(
                "判断当前值是否可以结束。返回 JSON："
                '{"done": true|false, "next_value": integer}。'
            ),
            input={"iteration": iteration, "metrics": metrics},
            output_schema=Review,
        )
        if review.done:
            return metrics
        value = review.next_value
    return step(evaluate, value)


if __name__ == "__main__":
    print(optimize(2))
