"""Minimal baseline references used by the synthetic integration check."""

from collections import Counter
from random import Random


def popularity_ranking(train: list[dict], candidates: list[str]) -> list[str]:
    counts = Counter(event["item_id"] for event in train)
    return sorted(candidates, key=lambda item: (-counts[item], item))


def random_ranking(candidates: list[str], seed: int) -> list[str]:
    ranking = sorted(candidates)
    Random(seed).shuffle(ranking)
    return ranking
