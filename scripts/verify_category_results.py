"""Independently score category and matched Popularity rows from raw holdout sequences."""

import argparse
import bisect
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import duckdb
import pyarrow.parquet as pq


def verify(input_root, results_path, output):
    rows = json.loads(results_path.read_text(encoding="utf-8"))
    compared = 0
    con = duckdb.connect()
    con.execute("SET threads=2")
    for dataset in sorted({r["dataset"] for r in rows}):
        for seed in sorted({r["split_seed"] for r in rows if r["dataset"] == dataset}):
            root = input_root / dataset
            seed_dir = root / f"splits/seed-{seed}"
            candidate_table = pq.read_table(seed_dir / "candidates.parquet").to_pydict()
            groups = dict(zip(candidate_table["item_id"], candidate_table["group"], strict=True))
            category_table = pq.read_table(seed_dir / "category_mapping.parquet").to_pydict()
            categories = dict(
                zip(category_table["item_id"], category_table["category_id"], strict=True)
            )
            path = str(seed_dir / "train.parquet").replace("'", "''")
            counts = dict(
                con.execute(
                    f"SELECT item_id,count(*) FROM read_parquet('{path}') GROUP BY item_id"
                ).fetchall()
            )
            ranked = sorted(groups, key=lambda i: (-counts.get(i, 0), i))
            global_rank = {i: pos for pos, i in enumerate(ranked, start=1)}
            category_ranks = defaultdict(list)
            for item in ranked:
                if categories[item] != "UNK":
                    category_ranks[categories[item]].append(global_rank[item])
            for window in ("validation", "test"):
                totals = defaultdict(
                    lambda: {
                        "eligible": 0,
                        "scored": 0,
                        "fallback": 0,
                        "hr": 0.0,
                        "mrr": 0.0,
                        "ndcg": 0.0,
                    }
                )
                events = pq.read_table(
                    root / f"splits/{window}.parquet",
                    columns=["session_id", "item_id", "timestamp_ms", "raw_row_index"],
                )
                records = list(
                    zip(*(events[c].to_pylist() for c in events.column_names), strict=True)
                )
                records.sort(key=lambda r: (r[0], r[2], r[3]))
                session, position = None, 0
                votes, latest = Counter(), {}
                for sid, target, _, _ in records:
                    if sid != session:
                        session, position, votes, latest = sid, 0, Counter(), {}
                    if position and target in groups:
                        group = groups[target]
                        for mode in ("non-oracle", "oracle"):
                            selected = (
                                (max(votes, key=lambda c: (votes[c], latest[c])) if votes else None)
                                if mode == "non-oracle"
                                else categories[target]
                            )
                            supported = not (dataset == "yoochoose" and group == "cold")
                            supported &= mode != "oracle" or selected != "UNK"
                            for model in (f"CatPopularity-{mode}", "Popularity"):
                                for g in ("overall", group):
                                    total = totals[(mode, model, g)]
                                    total["eligible"] += 1
                                    if not supported:
                                        continue
                                    total["scored"] += 1
                                    rank = global_rank[target]
                                    if model != "Popularity" and selected is not None:
                                        preferred = category_ranks[selected]
                                        index = bisect.bisect_left(preferred, rank)
                                        rank = (
                                            index + 1
                                            if categories[target] == selected
                                            else len(preferred) + rank - index
                                        )
                                    if (
                                        model != "Popularity"
                                        and mode == "non-oracle"
                                        and selected is None
                                    ):
                                        total["fallback"] += 1
                                    if rank <= 20:
                                        total["hr"] += 1
                                        total["mrr"] += 1 / rank
                                        total["ndcg"] += 1 / math.log2(rank + 1)
                    observed = categories.get(target, "UNK")
                    if observed != "UNK":
                        votes[observed] += 1
                        latest[observed] = position
                    position += 1
                relevant = [
                    r
                    for r in rows
                    if r["dataset"] == dataset
                    and r["split_seed"] == seed
                    and r["evaluation_split"] == window
                    and r["cohort"] != "full-primary"
                    and r["model"] != "Random"
                ]
                for row in relevant:
                    mode = row["cohort"].removesuffix("-supported")
                    total = totals[(mode, row["model"], row["group"])]
                    assert (row["n"], row["n_eligible"]) == (total["scored"], total["eligible"]), (
                        row
                    )
                    assert row["fallback_queries"] == total["fallback"], row
                    for metric in ("hr", "mrr", "ndcg"):
                        value = total[metric] / total["scored"] if total["scored"] else None
                        assert (
                            row[metric] is None
                            if value is None
                            else math.isclose(row[metric], value, abs_tol=1e-12)
                        ), row
                    compared += 1
            print(f"Verified {dataset} seed {seed}", flush=True)
    con.close()
    report = {
        "status": "passed",
        "category_and_matched_popularity_rows": compared,
        "method": (
            "independent SQL train counts, full raw holdout traversal, "
            "analytic ranks and direct metric sums"
        ),
        "shared_prediction_or_metric_code_used": False,
        "metric_tolerance": 1e-12,
        "input_runs_sha256": hashlib.sha256(results_path.read_bytes()).hexdigest(),
        "verifier_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.input_root, args.runs, args.output)


if __name__ == "__main__":
    main()
