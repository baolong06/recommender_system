"""Clean one raw dataset. Run from the repository root."""

import argparse
import sys
import tomllib
from pathlib import Path

from recommender.data.cleaning import clean_events
from recommender.data.manifest import build_manifest, file_entry, write_manifest
from recommender.data.readers import read_diginetica, read_yoochoose, validate_events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["yoochoose", "diginetica"], required=True)
    parser.add_argument("--config", default="configs/data.toml")
    parser.add_argument("--dataset-version", default="unspecified")
    parser.add_argument("--source-reference", default="")
    parser.add_argument("--nrows", type=int, default=None, help="Yoochoose only: quick trial")
    args = parser.parse_args(argv)

    config = tomllib.loads(Path(args.config).read_text(encoding="utf-8"))
    raw_dir = Path(config["input"]["raw_directory"]) / args.dataset
    if args.dataset == "yoochoose":
        raw_paths = [raw_dir / "yoochoose-clicks.dat"]
        events = read_yoochoose(raw_paths[0], nrows=args.nrows)
    else:
        raw_paths = [raw_dir / "train-item-views.csv", raw_dir / "product-categories.csv"]
        events = read_diginetica(*raw_paths)
    validate_events(events)

    rules = config["cleaning"]
    events, steps = clean_events(
        events,
        min_session_length=rules["min_session_length"],
        min_item_frequency=rules["min_item_frequency"],
        repeat_until_stable=rules["repeat_until_stable"],
        max_iterations=rules["max_iterations"],
    )

    suffix = f"_nrows{args.nrows}" if args.nrows else ""
    out_dir = Path(config["output"]["processed_directory"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.dataset}_clean{suffix}.parquet"
    events.to_parquet(out_path, index=False)

    kind = "partial-run-not-for-research" if args.nrows else config["kind"]
    manifest = build_manifest(
        kind=kind,
        dataset=args.dataset,
        dataset_version=args.dataset_version,
        source_reference=args.source_reference,
        config_path=args.config,
        raw_files=[file_entry(p, args.source_reference) for p in raw_paths],
        processed_files=[file_entry(out_path, "local: data/processed", rows=len(events))],
        steps=steps,
        reproduce_command="python scripts/run_clean.py " + " ".join(sys.argv[1:]),
    )
    manifest_path = Path(config["output"]["manifest_directory"])
    write_manifest(manifest, manifest_path / f"{args.dataset}{suffix}_manifest.json")

    for step in steps:
        print(step)
    print("Done:", len(events), "events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
