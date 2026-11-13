"""Accept P0 v2 split artifacts and evaluate Random/Popularity without refitting on holdout."""

import argparse
import csv
import importlib.metadata
import json
import platform
import subprocess
import tomllib
from pathlib import Path

from recommender.baselines_v2 import evaluate_window, summarise, train_counts
from recommender.splits.acceptance import accept_dataset, sha256

EXPECTED = {
    "protocol_version": "P0-baselines-v2",
    "data_protocol_version": "P0-data-v2",
    "split_seeds": [42, 43, 44],
    "model_seeds": [42, 43, 44],
    "k": 20,
    "evaluation_splits": ["validation", "test"],
    "candidate_policy": "final-warm-union-fixed-controlled-cold",
    "popularity_tie_break": "item_id ascending (lexicographic)",
    "random_policy": "per-query sha256 seed + Python Random.sample sorted candidates",
    "seen_items": "keep",
    "refit_on_validation": False,
}


def compare_handoff(manifest, reference):
    """Compare semantic split audits; Parquet file encodings may differ across platforms."""

    def counts_only(value):
        if isinstance(value, dict):
            return {
                k: counts_only(v)
                for k, v in value.items()
                if k not in {"paths", "holdout_paths", "preholdout_items_path"}
            }
        if isinstance(value, list):
            return [counts_only(v) for v in value]
        return value

    if counts_only(manifest["split_audit"]) != counts_only(reference["split_audit"]):
        raise ValueError("Local split audit differs from dev handoff")

    def raw_hashes(m):
        return sorted(f["sha256"] for f in m["normalization_before_duplicate_flag"]["raw_files"])

    if raw_hashes(manifest) != raw_hashes(reference):
        raise ValueError("Local raw hashes differ from dev handoff")


def run(input_root, output, config_path, datasets, reference_root=None):
    config = tomllib.loads(Path(config_path).read_text(encoding="utf-8"))
    if config != EXPECTED:
        raise ValueError("Baseline protocol config differs; version any protocol change")
    if output.exists():
        raise FileExistsError(f"Use a new output directory: {output}")
    rows, acceptances = [], []
    for dataset in datasets:
        directory = input_root / dataset
        print(f"{dataset}: verifying payload hashes and leakage", flush=True)
        accepted = accept_dataset(directory)
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if reference_root is not None:
            reference_path = reference_root / f"{dataset}_manifest.json"
            compare_handoff(manifest, json.loads(reference_path.read_text(encoding="utf-8")))
            accepted["dev_handoff_comparison"] = {
                "reference": reference_path.as_posix(),
                "sha256": sha256(reference_path),
                "raw_hashes_and_split_audit_equal": True,
            }
        for seed_info in accepted["seeds"]:
            seed = seed_info["seed"]
            seed_dir = directory / f"splits/seed-{seed}"
            counts = train_counts(seed_dir / "train.parquet")
            split_id = f"{dataset}-P0-v2-{accepted['data_manifest_sha256'][:16]}-seed-{seed}"
            for window in config["evaluation_splits"]:
                print(f"{dataset}: seed {seed}, {window}, Random/Popularity@20", flush=True)
                scored = evaluate_window(
                    directory / f"splits/{window}.parquet",
                    seed_dir / "candidates.parquet",
                    counts,
                    dataset=dataset,
                    split_seed=seed,
                    model_seeds=config["model_seeds"],
                    window=window,
                    k=config["k"],
                )
                observed = {r["group"]: r["n"] for r in scored}
                coverage = seed_info["coverage"][window]
                if (observed["warm"], observed["cold"], observed["overall"]) != (
                    coverage["warm_targets"],
                    coverage["cold_targets"],
                    coverage["warm_targets"] + coverage["cold_targets"],
                ):
                    raise ValueError("Example iterator coverage differs from independent audit")
                for row in scored:
                    row.update(
                        data_version="P0-data-v2",
                        split_id=split_id,
                        data_manifest_sha256=accepted["data_manifest_sha256"],
                    )
                rows.extend(scored)
        acceptances.append(accepted)
    output.mkdir(parents=True)
    (output / "runs.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    with (output / "runs.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = summarise(rows)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "split_acceptance.json").write_text(
        json.dumps(acceptances, indent=2) + "\n", encoding="utf-8"
    )
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    repo = Path(__file__).resolve().parents[1]
    sources = [
        repo / "scripts/run_baselines_v2.py",
        repo / "src/recommender/baselines_v2.py",
        repo / "src/recommender/splits/acceptance.py",
        repo / "src/recommender/metrics.py",
        repo / "src/recommender/data/examples_v2.py",
        Path(config_path).resolve(),
    ]
    result_manifest = {
        "kind": "P0-Random-Popularity-baseline-results",
        "protocol": config,
        "code_commit": commit,
        "source_code_sha256": {p.relative_to(repo).as_posix(): sha256(p) for p in sources},
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {p: importlib.metadata.version(p) for p in ("pyarrow", "duckdb")},
        },
        "dependency_locks_sha256": {
            p: sha256(repo / p) for p in ("requirements-dev.txt", "requirements-audit.txt")
        },
        "inputs": [
            {"dataset": a["dataset"], "data_manifest_sha256": a["data_manifest_sha256"]}
            for a in acceptances
        ],
        "files": [
            {"path": p.name, "sha256": sha256(p), "bytes": p.stat().st_size}
            for p in sorted(output.iterdir())
            if p.is_file()
        ],
        "review_status": "executed-awaiting-independent-review",
        "catpop_implemented": False,
        "aggregation": "Random model-seed means within split, then 3 split means; ddof=1",
    }
    (output / "manifest.json").write_text(
        json.dumps(result_manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Completed {len(rows)} result rows: {output}", flush=True)
    return result_manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("data/protocol_v2"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/baselines_v2.toml"))
    parser.add_argument("--dataset", choices=["all", "diginetica", "yoochoose"], default="all")
    parser.add_argument("--reference-root", type=Path)
    args = parser.parse_args(argv)
    datasets = ["diginetica", "yoochoose"] if args.dataset == "all" else [args.dataset]
    run(args.input_root, args.output_dir, args.config, datasets, args.reference_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
