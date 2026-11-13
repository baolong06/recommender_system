"""Evaluate category modes and matched-cohort reference baselines on shared examples."""

import json
from statistics import mean, stdev

from recommender.baselines_v2 import GROUPS, METRICS, random_topk, summarise
from recommender.data.examples_v2 import iter_examples
from recommender.evaluation import GroupMetrics

MODES = {"non-oracle": "CatPopularity-non-oracle", "oracle": "CatPopularity-oracle"}


def evaluate_categories(
    events, candidates_path, model, *, dataset, split_seed, model_seeds, window
):
    baselines = [("Popularity", None), *[("Random", seed) for seed in model_seeds]]
    accumulators = {(name, None, mode): GroupMetrics(model.k) for mode, name in MODES.items()}
    for mode in MODES:
        for baseline, seed in baselines:
            accumulators[(baseline, seed, mode)] = GroupMetrics(model.k)
    fallback = {mode: dict.fromkeys(GROUPS, 0) for mode in MODES}
    for example in iter_examples(events, candidates_path):
        prefix = example["prefix"]
        # Predict non-oracle before the evaluator inspects target/category/group.
        selected = model.select_category(prefix)
        non_oracle = model.predict_non_oracle(prefix)
        target, group = example["target"], example["group"]
        category = model.mapping[target]
        oracle = model.predict_oracle(category)
        predictions = {"non-oracle": non_oracle, "oracle": oracle}
        reasons = {
            "non-oracle": None,
            "oracle": "target category unavailable" if oracle is None else None,
        }
        if dataset == "yoochoose" and group == "cold":
            for mode in MODES:
                predictions[mode] = None
                reasons[mode] = "Yoochoose cold has no independent category catalog"
        references = {("Popularity", None): list(model.popularity[: model.k])}
        for name, seed in baselines[1:]:
            references[(name, seed)] = random_topk(
                model.candidates,
                model.k,
                dataset=dataset,
                split_seed=split_seed,
                model_seed=seed,
                window=window,
                query=example,
            )
        for mode, name in MODES.items():
            accumulators[(name, None, mode)].add(target, predictions[mode], group, reasons[mode])
            if predictions[mode] is not None and mode == "non-oracle" and selected is None:
                for g in ("overall", group):
                    fallback[mode][g] += 1
            for baseline, seed in baselines:
                ranking = references[(baseline, seed)] if predictions[mode] is not None else None
                accumulators[(baseline, seed, mode)].add(target, ranking, group, reasons[mode])
    rows = []
    for (name, seed, mode), accumulator in accumulators.items():
        for group, result in accumulator.result().items():
            rows.append(
                {
                    "dataset": dataset,
                    "split_seed": split_seed,
                    "model": name,
                    "model_seed": seed,
                    "evaluation_split": window,
                    "k": model.k,
                    "group": group,
                    "cohort": f"{mode}-supported",
                    "oracle": name == MODES["oracle"],
                    "n": result["n"],
                    "n_eligible": result["n_eligible"],
                    "support_fraction": result["support_fraction"],
                    **result["metrics"],
                    "status": result["status"],
                    "reason": json.dumps(result["unsupported"], sort_keys=True),
                    "fallback_queries": fallback[mode][group] if name == MODES[mode] else 0,
                }
            )
    return rows


def category_summary(rows):
    summaries = []
    for cohort in sorted({row["cohort"] for row in rows}):
        selected = [row for row in rows if row["cohort"] == cohort]
        for summary in summarise(selected):
            group_rows = [
                r
                for r in selected
                if all(
                    r[k] == summary[k]
                    for k in ("dataset", "evaluation_split", "model", "k", "group")
                )
            ]
            summary["cohort"] = cohort
            summary["support"] = [
                {k: r[k] for k in ("split_seed", "n", "n_eligible", "support_fraction", "status")}
                for r in group_rows
                if r["model_seed"] in {None, 42}
            ]
            summaries.append(summary)
    return summaries


def paired_differences(rows):
    """Within-split differences on identical supported examples, no significance claim."""
    results = []
    for dataset in sorted({r["dataset"] for r in rows}):
        for window in ("validation", "test"):
            for mode, model in MODES.items():
                for group in GROUPS:
                    selected = [
                        r
                        for r in rows
                        if r["dataset"] == dataset
                        and r["evaluation_split"] == window
                        and r["group"] == group
                        and r["cohort"] == f"{mode}-supported"
                    ]
                    if not selected:
                        continue
                    for baseline in ("Random", "Popularity"):
                        splits = []
                        for seed in sorted({r["split_seed"] for r in selected}):
                            cat = next(
                                r
                                for r in selected
                                if r["split_seed"] == seed and r["model"] == model
                            )
                            refs = [
                                r
                                for r in selected
                                if r["split_seed"] == seed and r["model"] == baseline
                            ]
                            if any(
                                r["n"] != cat["n"] or r["n_eligible"] != cat["n_eligible"]
                                for r in refs
                            ):
                                raise ValueError(
                                    "Paired comparison requires identical cohort counts"
                                )
                            splits.append(
                                {
                                    "split_seed": seed,
                                    "n": cat["n"],
                                    **{
                                        key: cat[key] - mean(r[key] for r in refs)
                                        if cat["n"]
                                        else None
                                        for key in METRICS
                                    },
                                }
                            )
                        metrics = {}
                        for key in METRICS:
                            values = [r[key] for r in splits if r[key] is not None]
                            metrics[key] = {
                                "mean_difference": mean(values) if values else None,
                                "sample_std": stdev(values) if len(values) > 1 else None,
                                "contributing_splits": len(values),
                            }
                        results.append(
                            {
                                "dataset": dataset,
                                "evaluation_split": window,
                                "category_model": model,
                                "baseline": baseline,
                                "group": group,
                                "cohort": f"{mode}-supported",
                                "split_differences": splits,
                                "metrics": metrics,
                            }
                        )
    return results
