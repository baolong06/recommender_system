"""Stream dataset-scale Random/Popularity predictions using the shared metric functions."""

import hashlib
import json
from collections import Counter
from random import Random
from statistics import mean, stdev

import pyarrow.parquet as pq

from recommender.data.examples_v2 import iter_examples
from recommender.metrics import ranking_metrics

METRICS = ("hr", "mrr", "ndcg")
GROUPS = ("overall", "warm", "cold")


def train_counts(path):
    counts = Counter()
    for batch in pq.ParquetFile(path).iter_batches(batch_size=250_000, columns=["item_id"]):
        counts.update(batch.column(0).to_pylist())
    return counts


def popularity_topk(counts, candidates, k):
    if k < 1 or len(set(candidates)) != len(candidates):
        raise ValueError("Require positive K and distinct candidates")
    return sorted(candidates, key=lambda item: (-counts.get(item, 0), item))[:k]


def random_topk(candidates, k, *, dataset, split_seed, model_seed, window, query):
    """Query identity excludes its target; traversal/chunk order cannot change predictions."""
    if k < 1:
        raise ValueError("K must be positive")
    key = [dataset, split_seed, model_seed, window, query["session_id"], query["raw_row_index"]]
    digest = hashlib.sha256(json.dumps(key, ensure_ascii=False, separators=(",", ":")).encode())
    return Random(int.from_bytes(digest.digest(), "big")).sample(
        candidates, min(k, len(candidates))
    )


def evaluate_window(
    events, candidates_path, counts, *, dataset, split_seed, model_seeds, window, k
):
    catalog = pq.read_table(candidates_path, columns=["item_id"]).column(0).to_pylist()
    candidates = sorted(catalog)
    if len(candidates) != len(set(candidates)):
        raise ValueError("Candidates contain duplicates")
    popularity = popularity_topk(counts, candidates, k)
    models = [("Popularity", None), *[("Random", seed) for seed in model_seeds]]
    sums = {model: {group: dict.fromkeys(METRICS, 0.0) for group in GROUPS} for model in models}
    samples = dict.fromkeys(GROUPS, 0)
    for example in iter_examples(events, candidates_path):
        groups = ("overall", example["group"])
        for group in groups:
            samples[group] += 1
        for model, seed in models:
            predictions = (
                popularity
                if model == "Popularity"
                else random_topk(
                    candidates,
                    k,
                    dataset=dataset,
                    split_seed=split_seed,
                    model_seed=seed,
                    window=window,
                    query=example,
                )
            )
            score = ranking_metrics(predictions, example["target"], k)
            for group in groups:
                for metric in METRICS:
                    sums[(model, seed)][group][metric] += score[metric]
    return [
        {
            "dataset": dataset,
            "split_seed": split_seed,
            "model": model,
            "model_seed": seed,
            "evaluation_split": window,
            "k": k,
            "group": group,
            "n": samples[group],
            **{
                metric: sums[(model, seed)][group][metric] / samples[group]
                if samples[group]
                else None
                for metric in METRICS
            },
            "status": "ok" if samples[group] else "N/A",
            "reason": "" if samples[group] else "no eligible targets in group",
        }
        for model, seed in models
        for group in GROUPS
    ]


def summarise(rows):
    """Aggregate model randomness within split, then split variation with ddof=1."""
    buckets = {}
    for row in rows:
        key = tuple(row[k] for k in ("dataset", "evaluation_split", "model", "k", "group"))
        buckets.setdefault(key, {}).setdefault(row["split_seed"], []).append(row)
    summaries = []
    for key, splits in sorted(buckets.items()):
        fixed = []
        for seed, runs in sorted(splits.items()):
            if len({r["n"] for r in runs}) != 1:
                raise ValueError("Model seeds must evaluate the same examples")
            fixed.append(
                {
                    "split_seed": seed,
                    "n": runs[0]["n"],
                    "model_runs": len(runs),
                    "metrics": {
                        metric: {
                            "mean": mean(r[metric] for r in runs) if runs[0]["n"] else None,
                            "sample_std": (stdev(r[metric] for r in runs) if len(runs) > 1 else 0.0)
                            if runs[0]["n"]
                            else None,
                        }
                        for metric in METRICS
                    },
                }
            )
        metrics = {}
        for metric in METRICS:
            values = [s["metrics"][metric]["mean"] for s in fixed if s["n"]]
            metrics[metric] = {
                "mean": mean(values) if values else None,
                "sample_std": stdev(values) if len(values) > 1 else None,
                "contributing_splits": len(values),
            }
        summaries.append(
            {
                **dict(
                    zip(("dataset", "evaluation_split", "model", "k", "group"), key, strict=True)
                ),
                "splits": fixed,
                "metrics": metrics,
                "aggregation": "unweighted mean of split-level model-seed means; sample std ddof=1",
            }
        )
    return summaries
