from dataclasses import dataclass

from looma import agent, step, workflow


@dataclass
class Decision:
    choice: str


def preprocess(value: int):
    print("preprocess runs once")
    return {"value": value * 2}


def finish(x, choice):
    return {"choice": choice, "value": x["value"]}


@workflow
def main(value: int):
    x = step(preprocess, value)
    decision = agent(
        task='判断应返回 A 还是 B，并写入形如 {"choice":"A"} 的 JSON。',
        input=x,
        output_schema=Decision,
    )
    return step(finish, x, decision.choice)


if __name__ == "__main__":
    print(main(21))
