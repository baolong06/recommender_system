"""Exercise the CI fixture; outputs are never research results."""

import argparse
import hashlib
import json
import platform
import tomllib
from pathlib import Path
from statistics import mean, stdev

from recommender.baselines import popularity_ranking, random_ranking
from recommender.contracts import validate_dataset
from recommender.evaluation import evaluate_groups


def run_fixture(fixture: Path, protocol: Path, seeds: list[int]) -> dict:
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("provide distinct seeds")
    raw = fixture.read_bytes()
    config_raw = protocol.read_bytes()
    config = tomllib.loads(config_raw.decode("utf-8"))
    dataset = json.loads(raw)
    if dataset.get("kind") != "synthetic" or config["smoke"]["dataset_kind"] != "synthetic":
        raise ValueError("this runner only accepts synthetic CI fixtures")
    validate_dataset(dataset, config["cold_item_fraction"])
    k = config["smoke"]["k"]
    candidates = sorted(dataset["catalog"])
    runs = []
    for seed in seeds:
        rankings = {
            "popularity": popularity_ranking(dataset["train"], candidates),
            "random": random_ranking(candidates, seed),
        }
        models = {
            name: evaluate_groups(
                dataset["test"],
                [ranking for _ in dataset["test"]],
                set(dataset["cold_items"]),
                k,
            )
            for name, ranking in rankings.items()
        }
        runs.append({"seed": seed, "models": models})
    summary = {}
    for model in ["popularity", "random"]:
        summary[model] = {}
        for group in ["overall", "warm", "cold"]:
            summary[model][group] = {}
            for metric in ["hr", "mrr", "ndcg"]:
                values = [run["models"][model][group]["metrics"][metric] for run in runs]
                available = all(value is not None for value in values)
                summary[model][group][metric] = {
                    "mean": mean(values) if available else None,
                    "sample_std": stdev(values) if available and len(values) > 1 else None,
                }
    return {
        "kind": "synthetic-ci-check-not-research-results",
        "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "protocol_sha256": hashlib.sha256(config_raw).hexdigest(),
        "python": platform.python_version(),
        "k": k,
        "runs": runs,
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/session_dataset.json"))
    parser.add_argument("--protocol", type=Path, default=Path("configs/protocol.toml"))
    parser.add_argument("--seeds", type=int, nargs="+", default=[42])
    parser.add_argument("--output", type=Path, default=Path("artifacts/smoke.json"))
    args = parser.parse_args()
    report = run_fixture(args.fixture, args.protocol, args.seeds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Synthetic check completed: {args.output} (not P0 research results)")


if __name__ == "__main__":
    main()
