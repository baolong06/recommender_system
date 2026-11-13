"""Run neutral data -> temporal/train-only filtering -> controlled cold holdout."""

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from recommender.data.category_v2 import fit_category_mapping
from recommender.data.neutral import normalize_dataset
from recommender.data.protocol_v2 import build_splits

EXPECTED = {
    "protocol_version": "P0-data-v2",
    "seeds": [42, 43, 44],
    "cold_item_fraction": 0.20,
    "min_session_events": 2,
    "min_item_support": 5,
    "max_filter_iterations": 100,
    "support_fit": "train-before-cold-intervention",
    "duplicate_policy": "keep-and-flag",
    "recore_after_cold_intervention": False,
    "candidate_policy": "final-warm-union-fixed-controlled-cold",
}


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def connection(directory):
    directory.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET memory_limit='2GB'")
    con.execute("SET threads=2")
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"SET temp_directory={literal(directory)}")
    return con


def flag_duplicates(source, target, temp):
    """Flag all members of an ambiguous tuple while retaining every valid event."""
    if Path(target).exists():
        raise FileExistsError(target)
    with connection(temp) as con:
        con.execute(
            f"COPY (SELECT *,count(*) OVER (PARTITION BY session_id,item_id,timestamp_ms)>1 "
            f"AS exact_duplicate FROM read_parquet({literal(source)}) ORDER BY raw_row_index) "
            f"TO {literal(target)} (FORMAT PARQUET,COMPRESSION ZSTD)"
        )
        row = con.execute(
            f"SELECT count(*),count(*) FILTER(WHERE exact_duplicate),"
            f"count(*)-count(DISTINCT (session_id,item_id,timestamp_ms)) "
            f"FROM read_parquet({literal(target)})"
        ).fetchone()
    return dict(zip(("rows", "flagged_rows", "duplicate_tuple_excess_rows"), row, strict=True))


def _parquet(path):
    return f"read_parquet({literal(path)})"


def validate_outputs(neutral, splits, categories, directory):
    """Independent readback of actual clocks, segments, cold IDs and target coverage."""
    with connection(directory / ".validation-spill") as con:
        n = _parquet(neutral)
        rows, unique, invalid = con.execute(
            "SELECT count(*),count(DISTINCT raw_row_index),count(*) FILTER(WHERE "
            "session_id IS NULL OR trim(session_id)='' OR item_id IS NULL OR trim(item_id)='' "
            "OR timestamp_ms IS NULL OR timestamp_ms<0 OR timestamp IS NULL "
            f"OR timestamp_ms//1000<>timestamp) FROM {n}"
        ).fetchone()
        if rows != unique or invalid:
            raise ValueError("Invalid neutral row identity/time/schema")
        holdouts = {name: _parquet(path) for name, path in splits["holdout_paths"].items()}
        val, test = holdouts["validation"], holdouts["test"]
        if con.execute(
            f"SELECT count(*) FROM (SELECT DISTINCT session_id FROM {val}) v "
            f"JOIN (SELECT DISTINCT session_id FROM {test}) t USING(session_id)"
        ).fetchone()[0]:
            raise ValueError("Validation/test session leakage")
        windows = splits["windows_utc_ms"]
        for name, relation in holdouts.items():
            lo, hi = windows[f"{name}_start_inclusive"], windows[f"{name}_end_exclusive"]
            if con.execute(
                f"SELECT count(*) FROM {relation} WHERE timestamp_ms<{lo} OR timestamp_ms>={hi}"
            ).fetchone()[0]:
                raise ValueError("Holdout timestamp crosses its global window")
        universe = [
            r[0]
            for r in con.execute(
                f"SELECT item_id FROM {_parquet(splits['preholdout_items_path'])}"
            ).fetchall()
        ]
        verified = []
        for info, mapping in zip(splits["seeds"], categories, strict=True):
            seed, paths = info["seed"], info["paths"]
            train, cold, candidates = (
                _parquet(paths[name]) for name in ("train", "cold_items", "candidates")
            )
            actual = {r[0] for r in con.execute(f"SELECT item_id FROM {cold}").fetchall()}
            ordered = sorted(
                universe,
                key=lambda i: (
                    hashlib.sha256(f"{splits['dataset']}:{seed}:{i}".encode()).hexdigest(),
                    i,
                ),
            )
            if actual != set(ordered[: math.ceil(0.2 * len(universe))]):
                raise ValueError("Cold IDs do not match deterministic selection")
            if con.execute(f"SELECT count(*) FROM {train} JOIN {cold} USING(item_id)").fetchone()[
                0
            ]:
                raise ValueError("Controlled cold event leaked into train")
            if con.execute(
                f"SELECT count(*) FROM {train} WHERE timestamp_ms>={windows['train_end_exclusive']}"
            ).fetchone()[0]:
                raise ValueError("Training contains future event")
            for relation in holdouts.values():
                if con.execute(
                    f"SELECT count(*) FROM (SELECT DISTINCT parent_session_id FROM {train}) t "
                    f"JOIN (SELECT DISTINCT session_id FROM {relation}) h "
                    "ON t.parent_session_id=h.session_id"
                ).fetchone()[0]:
                    raise ValueError("Parent session shared between train and holdout")
            if con.execute(
                f"SELECT count(*) FROM (SELECT session_id,count(*) n FROM {train} "
                "GROUP BY session_id) WHERE n<2"
            ).fetchone()[0]:
                raise ValueError("Training contains short segment")
            if con.execute(
                "WITH seq AS (SELECT event_pos,timestamp_ms,lag(event_pos) OVER w prev_pos,"
                f"lag(timestamp_ms) OVER w prev_time FROM {train} "
                "WINDOW w AS (PARTITION BY session_id ORDER BY event_pos)) "
                "SELECT count(*) FROM seq WHERE event_pos-prev_pos<>1 OR timestamp_ms<prev_time"
            ).fetchone()[0]:
                raise ValueError("Training segment bridges removed event or reverses time")
            for name, relation in holdouts.items():
                row = con.execute(
                    "WITH seq AS (SELECT *,row_number() OVER (PARTITION BY session_id "
                    f"ORDER BY timestamp_ms,raw_row_index) pos FROM {relation}) "
                    "SELECT count(*),count(*) FILTER(WHERE c.\"group\"='warm'),"
                    "count(*) FILTER(WHERE c.\"group\"='cold') "
                    f"FROM seq LEFT JOIN {candidates} c USING(item_id) WHERE pos>1"
                ).fetchone()
                audit = info["coverage"][name]
                if tuple(row) != tuple(
                    audit[k] for k in ("all_targets", "warm_targets", "cold_targets")
                ):
                    raise ValueError("Actual target coverage differs from split audit")
            if mapping["dataset"] == "yoochoose" and mapping["coverage"]["cold"]["known"]:
                raise ValueError("Yoochoose cold category must remain unknown without catalog")
            verified.append(seed)
        return {
            "neutral_rows": rows,
            "unique_raw_row_index": unique,
            "verified_seeds": verified,
            "independent_parquet_readback": True,
            "no_controlled_cold_in_train": True,
            "global_time_windows_disjoint": True,
            "parent_sessions_disjoint": True,
            "no_training_transition_across_removed_event": True,
            "cold_selection_sha256_reproduced": True,
            "target_coverage_recomputed": True,
        }


def run_dataset(dataset, raw_root, output_root, config_path, batch_size=500000):
    directory = Path(output_root) / dataset
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError(f"Use a new directory to preserve versions: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    raw = Path(raw_root) / dataset
    unflagged, neutral = directory / "neutral.unflagged.parquet", directory / "neutral.parquet"
    print(f"{dataset}: normalizing raw events", flush=True)
    normalization = normalize_dataset(dataset, raw, unflagged, batch_size=batch_size)
    print(f"{dataset}: retaining and flagging duplicate tuples", flush=True)
    duplicates = flag_duplicates(unflagged, neutral, directory / ".neutral-spill")
    if duplicates["rows"] != normalization["valid_rows"]:
        raise ValueError("Duplicate flagging changed the number of valid events")
    unflagged.unlink()
    print(f"{dataset}: temporal split and controlled cold seeds 42/43/44", flush=True)
    splits = build_splits(neutral, directory / "splits", dataset)
    categories = []
    for info in splits["seeds"]:
        paths = info["paths"]
        mapping_path = Path(paths["train"]).parent / "category_mapping.parquet"
        categories.append(
            fit_category_mapping(
                Path(paths["train"]),
                Path(paths["candidates"]),
                dataset,
                mapping_path,
                raw / "product-categories.csv" if dataset == "diginetica" else None,
            )
        )
    print(f"{dataset}: independent output readback", flush=True)
    checks = validate_outputs(neutral, splits, categories, directory)
    for path in (
        directory / ".neutral-spill",
        directory / ".validation-spill",
        directory / "splits/.tmp",
    ):
        if path.exists():
            shutil.rmtree(path)
    sources = [
        Path(__file__),
        *Path("src/recommender/data").glob("*v2.py"),
        Path("src/recommender/data/neutral.py"),
        Path(config_path),
    ]
    files = [
        {"path": str(p.relative_to(directory)), "bytes": p.stat().st_size, "sha256": sha256(p)}
        for p in sorted(directory.rglob("*.parquet"))
    ]
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    manifest = {
        "protocol_version": "P0-data-v2",
        "dataset": dataset,
        "created_at": datetime.now(UTC).isoformat(),
        "code_commit": commit,
        "source_code_sha256": {str(p): sha256(p) for p in sorted(set(sources))},
        "config_sha256": sha256(config_path),
        "normalization_before_duplicate_flag": normalization,
        "duplicate_flags": duplicates,
        "split_audit": splits,
        "category_audits": categories,
        "verification": checks,
        "files": files,
        "review_status": "data-verified-research-incomplete",
        "catpop_scorer_implemented": False,
    }

    def portable(value):
        if isinstance(value, dict):
            return {k: portable(v) for k, v in value.items()}
        if isinstance(value, list):
            return [portable(v) for v in value]
        if isinstance(value, str) and value.startswith(str(directory) + "/"):
            return value[len(str(directory)) + 1 :]
        return value

    manifest = portable(manifest)
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"{dataset}: verified {checks['neutral_rows']:,} neutral events", flush=True)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=["all", "diginetica", "yoochoose"], default="all")
    parser.add_argument("--config", type=Path, default=Path("configs/data_v2.toml"))
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--batch-size", type=int, default=500000)
    args = parser.parse_args(argv)
    config = tomllib.loads(args.config.read_text())
    for key, expected in EXPECTED.items():
        if config.get(key) != expected:
            parser.error(f"This protocol requires {key}={expected!r}; version any change")
    if args.batch_size < 1:
        parser.error("batch size must be positive")
    raw = (args.raw_dir or Path(config["raw_directory"])).resolve()
    output = (args.output_dir or Path(config["output_directory"])).resolve()
    if output == raw or output.is_relative_to(raw) or raw.is_relative_to(output):
        parser.error("Raw and output directories must be separate trees")
    for dataset in ["diginetica", "yoochoose"] if args.dataset == "all" else [args.dataset]:
        run_dataset(dataset, raw, output, args.config, args.batch_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
