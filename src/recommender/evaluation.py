"""Aggregate metrics by the target item's membership in the cold set."""

from recommender.metrics import ranking_metrics


class GroupMetrics:
    """Streaming target-group metrics with explicit unsupported query accounting."""

    def __init__(self, k):
        if type(k) is not int or k < 1:
            raise ValueError("k must be a positive integer")
        self.k = k
        self.groups = {
            group: {
                "n_eligible": 0,
                "n": 0,
                "sums": dict.fromkeys(("hr", "mrr", "ndcg"), 0.0),
                "unsupported": {},
            }
            for group in ("overall", "warm", "cold")
        }

    def add(self, target, predictions, group, reason=None):
        if group not in {"warm", "cold"}:
            raise ValueError("group must be warm or cold")
        if predictions is None and not reason:
            raise ValueError("Unsupported predictions require a reason")
        if predictions is not None and reason:
            raise ValueError("Scored predictions cannot have an unsupported reason")
        score = ranking_metrics(predictions, target, self.k) if predictions is not None else None
        for name in ("overall", group):
            row = self.groups[name]
            row["n_eligible"] += 1
            if score is None:
                row["unsupported"][reason] = row["unsupported"].get(reason, 0) + 1
            else:
                row["n"] += 1
                for key, value in score.items():
                    row["sums"][key] += value

    def result(self):
        return {
            group: {
                "n": row["n"],
                "n_eligible": row["n_eligible"],
                "support_fraction": row["n"] / row["n_eligible"] if row["n_eligible"] else None,
                "metrics": {
                    key: value / row["n"] if row["n"] else None
                    for key, value in row["sums"].items()
                },
                "status": "N/A"
                if not row["n"]
                else ("ok" if row["n"] == row["n_eligible"] else "partial"),
                "unsupported": dict(row["unsupported"]),
            }
            for group, row in self.groups.items()
        }


def evaluate_groups(
    examples: list[dict], predictions: list[list[str]], cold_items: set[str], k: int
) -> dict:
    if len(examples) != len(predictions):
        raise ValueError("each example must have one prediction list")
    accumulator = GroupMetrics(k)
    for example, ranking in zip(examples, predictions, strict=True):
        group = "cold" if example["target"] in cold_items else "warm"
        accumulator.add(example["target"], ranking, group)
    return {
        group: {"n": row["n"], "metrics": row["metrics"]}
        for group, row in accumulator.result().items()
    }
