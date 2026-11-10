"""Metrics for one relevant next item per evaluation example."""

from math import log2


def ranking_metrics(predictions: list[str], target: str, k: int) -> dict[str, float]:
    if k < 1:
        raise ValueError("k must be positive")
    if len(set(predictions)) != len(predictions):
        raise ValueError("predictions must not contain duplicate items")
    top_k = predictions[:k]
    if target not in top_k:
        return {"hr": 0.0, "mrr": 0.0, "ndcg": 0.0}
    rank = top_k.index(target) + 1
    return {"hr": 1.0, "mrr": 1.0 / rank, "ndcg": 1.0 / log2(rank + 1)}
