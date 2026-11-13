"""Run Bao Long's category experiment against exact Trung Chien v2 split artifacts."""

import argparse
import csv
import importlib.metadata
import json
import platform
import subprocess
import tomllib
from pathlib import Path

import pyarrow.parquet as pq

from recommender.baselines_v2 import evaluate_window, train_counts
from recommender.category import CategoryPopularity
from recommender.category_evaluation import (
    category_summary,
    evaluate_categories,
    paired_differences,
)
from recommender.category_metadata import verify_mapping
from recommender.splits.acceptance import accept_dataset, sha256

EXPECTED = {
    "protocol_version": "P0-category-v2",
    "data_protocol_version": "P0-data-v2",
    "k": 20,
    "split_seeds": [42, 43, 44],
    "random_model_seeds": [42, 43, 44],
    "evaluation_splits": ["validation", "test"],
    "candidate_policy": "final-warm-union-fixed-controlled-cold",
    "category_selection": "prefix modal known category; tie by latest prefix occurrence",
    "scoring": "selected-category first; train event count descending; item_id ascending",
    "fallback": "no known prefix category -> global popularity",
    "oracle": "allowed target category only; unknown -> unsupported",
    "yoochoose_cold": "N/A without independent catalog",
    "seen_items": "keep",
    "refit_on_validation": False,
}


def read_verified_reference(root):
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        path = root / entry["path"]
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Reference escapes directory")
        if path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
            raise ValueError("Trung Chien reference hash mismatch")
    return json.loads((root / "runs.json").read_text(encoding="utf-8"))


def verify_baseline_rows(actual, reference):
    fields = ("dataset", "split_seed", "model", "model_seed", "evaluation_split", "k", "group")
    expected = {tuple(r[k] for k in fields): r for r in reference}
    if len(expected) != len(reference):
        raise ValueError("Duplicate reference result identity")
    for row in actual:
        original = expected.get(tuple(row[k] for k in fields))
        if original is None or any(row[key] != original[key] for key in ("n", "hr", "mrr", "ndcg")):
            raise ValueError("Recomputed baseline differs from Trung Chien results")


def write_json(path, data):
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def run(input_root, output, config_path, datasets, reference_root, raw_root):
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    if config != EXPECTED:
        raise ValueError("Version any category protocol change")
    if output.exists():
        raise FileExistsError("Use a new output directory")
    reference = read_verified_reference(reference_root)
    rows, acceptances, metadata_checks = [], [], []
    for dataset in datasets:
        directory = input_root / dataset
        print(f"{dataset}: verifying exact split delivery and leakage", flush=True)
        accepted = accept_dataset(directory)
        expected_hashes = {r["data_manifest_sha256"] for r in reference if r["dataset"] == dataset}
        if expected_hashes != {accepted["data_manifest_sha256"]}:
            raise ValueError("Inputs differ from exact Trung Chien split snapshot")
        for seed in config["split_seeds"]:
            print(f"{dataset}: seed {seed}, reconstructing allowed category mapping", flush=True)
            mapping, checks = verify_mapping(directory, seed, raw_root)
            checks["dataset"] = dataset
            metadata_checks.append(checks)
            seed_dir = directory / f"splits/seed-{seed}"
            counts = train_counts(seed_dir / "train.parquet")
            candidates = pq.read_table(seed_dir / "candidates.parquet", columns=["item_id"])
            model = CategoryPopularity(
                counts, candidates.column(0).to_pylist(), mapping, config["k"]
            )
            split_id = f"{dataset}-P0-v2-{accepted['data_manifest_sha256'][:16]}-seed-{seed}"
            for window in config["evaluation_splits"]:
                print(f"{dataset}: seed {seed}, {window}, four-model comparison", flush=True)
                events = directory / f"splits/{window}.parquet"
                base = evaluate_window(
                    events,
                    seed_dir / "candidates.parquet",
                    counts,
                    dataset=dataset,
                    split_seed=seed,
                    model_seeds=config["random_model_seeds"],
                    window=window,
                    k=model.k,
                )
                verify_baseline_rows(base, reference)
                for row in base:
                    row.update(
                        cohort="full-primary",
                        oracle=False,
                        n_eligible=row["n"],
                        support_fraction=1.0 if row["n"] else None,
                        fallback_queries=0,
                    )
                category_rows = evaluate_categories(
                    events,
                    seed_dir / "candidates.parquet",
                    model,
                    dataset=dataset,
                    split_seed=seed,
                    model_seeds=config["random_model_seeds"],
                    window=window,
                )
                for row in base + category_rows:
                    row.update(
                        data_version="P0-data-v2",
                        split_id=split_id,
                        data_manifest_sha256=accepted["data_manifest_sha256"],
                    )
                rows.extend(base + category_rows)
        acceptances.append(accepted)
    output.mkdir(parents=True)
    write_json(output / "runs.json", rows)
    with (output / "runs.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_json(output / "summary.json", category_summary(rows))
    write_json(output / "paired_differences.json", paired_differences(rows))
    write_json(output / "split_acceptance.json", acceptances)
    write_json(output / "metadata_checks.json", metadata_checks)
    write_json(
        output / "baseline_reproduction.json",
        {
            "status": "passed",
            "reference_manifest_sha256": sha256(reference_root / "manifest.json"),
            "result_rows_equal": sum(r["cohort"] == "full-primary" for r in rows),
        },
    )
    repo = Path(__file__).resolve().parents[1]
    sources = [
        Path(__file__).resolve(),
        config_path.resolve(),
        *[
            repo / f"src/recommender/{name}.py"
            for name in (
                "category",
                "category_evaluation",
                "category_metadata",
                "evaluation",
                "metrics",
                "baselines_v2",
            )
        ],
        repo / "src/recommender/data/examples_v2.py",
        repo / "src/recommender/splits/acceptance.py",
    ]
    manifest = {
        "kind": "P0-category-four-model-results",
        "protocol": config,
        "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_code_sha256": {p.relative_to(repo).as_posix(): sha256(p) for p in sources},
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {p: importlib.metadata.version(p) for p in ("duckdb", "pyarrow")},
        },
        "dependency_locks_sha256": {
            p: sha256(repo / p) for p in ("requirements-dev.txt", "requirements-audit.txt")
        },
        "inputs": [
            {"dataset": a["dataset"], "data_manifest_sha256": a["data_manifest_sha256"]}
            for a in acceptances
        ],
        "files": [
            {"path": p.name, "bytes": p.stat().st_size, "sha256": sha256(p)}
            for p in sorted(output.iterdir())
            if p.is_file()
        ],
        "review_status": "executed-awaiting-independent-review",
        "human_protocol_approval": False,
    }
    write_json(output / "manifest.json", manifest)
    print(f"Completed {len(rows)} result rows: {output}", flush=True)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("data/protocol_v2"))
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--reference-root", type=Path, default=Path("docs/splits/v2"))
    parser.add_argument("--config", type=Path, default=Path("configs/category_v2.toml"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset", choices=["all", "diginetica", "yoochoose"], default="all")
    args = parser.parse_args(argv)
    datasets = ["diginetica", "yoochoose"] if args.dataset == "all" else [args.dataset]
    run(args.input_root, args.output_dir, args.config, datasets, args.reference_root, args.raw_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
