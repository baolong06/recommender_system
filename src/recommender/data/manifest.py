"""Build a data manifest following docs/data/data_manifest.example.json."""

import csv
import hashlib
import json
import subprocess
from pathlib import Path


def sha256_of(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def count_lines(path: str | Path, *, has_header: bool = False) -> int:
    """Count CSV records, including the last record without a newline; exclude headers."""
    with open(path, newline="", encoding="utf-8") as handle:
        records = csv.reader(handle)
        if has_header:
            next(records, None)
        return sum(1 for row in records if row)


def file_entry(
    path: str | Path, location: str, rows: int | None = None, *, has_header: bool = False
) -> dict:
    return {
        "path": Path(path).as_posix(),
        "location": location,
        "sha256": sha256_of(path),
        "rows": count_lines(path, has_header=has_header) if rows is None else rows,
    }


def code_commit() -> str:
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return output.strip()


def build_manifest(
    *,
    kind: str,
    dataset: str,
    dataset_version: str,
    source_reference: str,
    config_path: str,
    raw_files: list[dict],
    processed_files: list[dict],
    steps: list[dict],
    reproduce_command: str,
) -> dict:
    counts = {"events": None, "sessions": None, "items": None}
    return {
        "kind": kind,
        "owner": "ba-chien",
        "dataset": dataset,
        "dataset_version": dataset_version,
        "source_reference": source_reference,
        "code_commit": code_commit(),
        "config_path": config_path,
        "raw_files": raw_files,
        "processed_files": processed_files,
        "counts_before": {**counts, **_counts(steps[0])},
        "counts_after": {**counts, **_counts(steps[-1])},
        "filter_steps": steps,
        "schema_reference": "docs/data/schema.md",
        "reproduce_command": reproduce_command,
        "review_status": "draft",
    }


def _counts(step: dict) -> dict:
    return {key: step[key] for key in ["events", "sessions", "items"]}


def write_manifest(manifest: dict, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
