"""Aggregate metrics by the target item's membership in the cold set."""

from recommender.metrics import ranking_metrics


def evaluate_groups(
    examples: list[dict], predictions: list[list[str]], cold_items: set[str], k: int
) -> dict:
    if len(examples) != len(predictions):
        raise ValueError("each example must have one prediction list")
    scores = {"overall": [], "warm": [], "cold": []}
    for example, ranking in zip(examples, predictions, strict=True):
        score = ranking_metrics(ranking, example["target"], k)
        group = "cold" if example["target"] in cold_items else "warm"
        scores["overall"].append(score)
        scores[group].append(score)
    result = {}
    for group, rows in scores.items():
        result[group] = {
            "n": len(rows),
            "metrics": {
                metric: sum(row[metric] for row in rows) / len(rows) if rows else None
                for metric in ["hr", "mrr", "ndcg"]
            },
        }
    return result
