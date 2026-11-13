"""Recompress existing, session-sorted Parquet files without changing their values."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def session_batches(source, batch_size):
    """Yield complete sessions, rejecting input that is not sorted by session ID."""
    pending = None
    previous = None
    for batch in pq.ParquetFile(source).iter_batches(batch_size=batch_size):
        table = pa.Table.from_batches([batch])
        ids = table["session_id"].combine_chunks()
        if ids.null_count or (
            len(ids) > 1
            and not pc.all(pc.less_equal(ids.slice(0, len(ids) - 1), ids.slice(1))).as_py()
        ):
            raise ValueError("Input must have non-null session IDs sorted lexicographically")
        if previous is not None and ids[0].as_py() < previous:
            raise ValueError("Input must be sorted by session_id")
        previous = ids[-1].as_py()
        if pending is not None:
            table = pa.concat_tables([pending, table])
        ids = table["session_id"].combine_chunks()
        # Keep the final session until the next batch proves that it is complete.
        boundaries = pc.indices_nonzero(pc.not_equal(ids, ids[-1]))
        if len(boundaries):
            cut = boundaries[-1].as_py() + 1
            yield table.slice(0, cut)
            pending = table.slice(cut)
        else:
            pending = table
    if pending is not None:
        yield pending


def verify_values(source, parts):
    """Compare every value in order, independent of Parquet row-group boundaries."""

    def batches(paths):
        for path in paths:
            for batch in pq.ParquetFile(path).iter_batches(batch_size=65_536):
                yield pa.Table.from_batches([batch])

    left_iter, right_iter = batches([source]), batches(parts)
    left, right = next(left_iter, None), next(right_iter, None)
    while left is not None and right is not None:
        size = min(len(left), len(right))
        if not left.slice(0, size).equals(right.slice(0, size), check_metadata=True):
            raise ValueError(f"Repacked values differ from {source}")
        left = left.slice(size) if size < len(left) else next(left_iter, None)
        right = right.slice(size) if size < len(right) else next(right_iter, None)
    if left is not None or right is not None:
        raise ValueError(f"Repacked row count differs from {source}")


def package_file(source, output, metadata, target_bytes, batch_size=250_000):
    if sha256(source) != metadata["sha256"]:
        raise ValueError(f"Source checksum mismatch: {source.name}")
    output.mkdir(parents=True, exist_ok=False)
    parts = []
    writer = None
    handle = None
    rows = sessions = 0
    items = set()
    part_rows = part_sessions = 0
    part_first = part_last = None
    schema = pq.ParquetFile(source).schema_arrow

    def finish_part():
        nonlocal writer, handle
        writer.close()
        handle.close()
        parts.append(
            {
                "asset": target.name,
                "local_path": f"{source.stem}/part-{len(parts):03d}.parquet",
                "bytes": target.stat().st_size,
                "sha256": sha256(target),
                "rows": part_rows,
                "sessions": part_sessions,
                "first_session_id": part_first,
                "last_session_id": part_last,
            }
        )
        writer = handle = None

    try:
        for table in session_batches(source, batch_size):
            if writer is None:
                target = output / f"{source.stem}-part-{len(parts):03d}.parquet"
                handle = target.open("wb")
                writer = pq.ParquetWriter(handle, schema, compression="zstd", compression_level=6)
                part_rows = part_sessions = 0
                part_first = table["session_id"][0].as_py()
            ids = table["session_id"].combine_chunks()
            count = (
                1
                + pc.sum(
                    pc.cast(pc.not_equal(ids.slice(0, len(ids) - 1), ids.slice(1)), pa.int64())
                ).as_py()
                if len(ids) > 1
                else 1
            )
            items.update(pc.unique(table["item_id"]).to_pylist())
            rows += len(table)
            sessions += count
            part_rows += len(table)
            part_sessions += count
            part_last = ids[-1].as_py()
            writer.write_table(table, row_group_size=batch_size)
            if handle.tell() >= target_bytes:
                finish_part()
        if writer is not None:
            finish_part()
    finally:
        if writer is not None:
            writer.close()
        if handle is not None:
            handle.close()
    actual = {"rows": rows, "sessions": sessions, "items": len(items)}
    if any(actual[key] != metadata[key] for key in actual):
        raise ValueError(f"Counts differ from source manifest: {actual}")
    paths = [output / part["asset"] for part in parts]
    verify_values(source, paths)
    return {
        "source_file": source.name,
        "source_sha256": metadata["sha256"],
        "source_bytes": source.stat().st_size,
        **actual,
        "schema": [{"name": field.name, "type": str(field.type)} for field in schema],
        "source_provenance": metadata,
        "verification": "all values, row order, schema and metadata equal to source",
        "parts": parts,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--target-mib", type=float, default=256)
    args = parser.parse_args()
    if args.target_mib <= 0:
        parser.error("--target-mib must be positive")
    if args.output_dir.exists():
        parser.error("--output-dir must be new; existing packages are never overwritten")
    manifest_path = args.input_dir / "manifest.json"
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True)
    release_url = f"https://github.com/baolong06/recommender_system/releases/tag/{args.tag}"
    manifest = {
        "format_version": "1.0",
        "release_tag": args.tag,
        "release_url": release_url,
        "created_at": datetime.now(UTC).isoformat(),
        "review_status": "legacy-seconds-requires-rerun",
        "processing_note": "Repack only. No raw-data cleaning rerun or millisecond recovery.",
        "compression": {"codec": "zstd", "level": 6},
        "target_part_bytes": int(args.target_mib * 1024**2),
        "partitioning": "session boundaries; a complete batch/session may exceed target size",
        "packaging_environment": {"pyarrow": pa.__version__},
        "datasets": {},
    }
    for name, metadata in sorted(source_manifest.items()):
        if Path(name).name != name or not name.endswith(".parquet"):
            raise ValueError(f"Invalid source filename: {name}")
        print(f"Packaging {name}", flush=True)
        result = package_file(
            args.input_dir / name,
            args.output_dir / Path(name).stem,
            metadata,
            manifest["target_part_bytes"],
        )
        for part in result["parts"]:
            part["url"] = (
                f"https://github.com/baolong06/recommender_system/releases/download/"
                f"{args.tag}/{part['asset']}"
            )
        manifest["datasets"][Path(name).stem] = result
        print(f"Verified {result['rows']:,} rows in {len(result['parts'])} part(s)", flush=True)
    (args.output_dir / "source-manifest.json").write_bytes(manifest_path.read_bytes())
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
