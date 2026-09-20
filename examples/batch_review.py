"""Batch pattern: deterministic extraction + Agent review for each record."""

from dataclasses import dataclass

from looma import agent, step, workflow


@dataclass
class Review:
    accepted: bool
    label: str
    reason: str


def normalize(record: dict):
    return {
        "id": str(record["id"]),
        "title": str(record["title"]).strip(),
        "score": float(record["score"]),
    }


@workflow
def main():
    records = [
        {"id": 1, "title": "alpha", "score": 0.92},
        {"id": 2, "title": "beta", "score": 0.41},
        {"id": 3, "title": "gamma", "score": 0.78},
    ]

    accepted = []
    rejected = []

    for record in records:
        normalized = step(normalize, record)

        review = agent(
            task=(
                "审核该记录并返回结构化结果。"
                "返回 JSON：{\"accepted\": bool, \"label\": str, \"reason\": str}。"
            ),
            input=normalized,
            output_schema=Review,
        )

        item = {"record": normalized, "review": review.__dict__}
        if review.accepted:
            accepted.append(item)
        else:
            rejected.append(item)

    return {"accepted": accepted, "rejected": rejected}


if __name__ == "__main__":
    print(main())
