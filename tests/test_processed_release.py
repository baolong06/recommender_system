"""Release packaging must preserve events and keep entire sessions in a single part."""

import hashlib
import importlib.util
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, Path("scripts") / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_packaging_preserves_long_sessions_and_all_values(tmp_path):
    pack = load_script("package_processed")
    table = pa.table(
        {
            "session_id": ["001"] * 7 + ["002"] * 4 + ["003"] * 5,
            "item_id": [f"{i:03}" for i in range(16)],
            "timestamp": list(range(16)),
            "category": ["UNK"] * 16,
        }
    )
    source = tmp_path / "clean.parquet"
    pq.write_table(table, source, row_group_size=4)
    metadata = {"sha256": pack.sha256(source), "rows": 16, "sessions": 3, "items": 16}
    result = pack.package_file(source, tmp_path / "parts", metadata, 1, batch_size=3)
    parts = [tmp_path / "parts" / part["asset"] for part in result["parts"]]
    combined = pa.concat_tables([pq.ParquetFile(path).read() for path in parts])
    assert combined.equals(table)
    assert len(parts) > 1
    seen = set()
    for path in parts:
        sessions = set(pq.ParquetFile(path).read()["session_id"].to_pylist())
        assert not sessions & seen
        seen.update(sessions)
    assert seen == {"001", "002", "003"}
    with pytest.raises(ValueError, match="checksum"):
        pack.package_file(source, tmp_path / "bad", {**metadata, "sha256": "0" * 64}, 1)


def test_packaging_rejects_unsorted_sessions(tmp_path):
    pack = load_script("package_processed")
    source = tmp_path / "unsorted.parquet"
    pq.write_table(pa.table({"session_id": ["b", "a"]}), source)
    with pytest.raises(ValueError, match="sorted"):
        list(pack.session_batches(source, 1))


def test_download_verifies_content_and_rejects_corruption(tmp_path):
    download = load_script("download_processed")
    source = tmp_path / "asset.parquet"
    source.write_bytes(b"release asset")
    part = {
        "asset": source.name,
        "local_path": "sample/part-000.parquet",
        "url": source.as_uri(),
        "bytes": source.stat().st_size,
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    output = tmp_path / "downloads"
    target = download.download_part(part, output)
    assert target.read_bytes() == source.read_bytes()
    assert download.download_part(part, output) == target
    target.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum"):
        download.download_part(part, output)
    with pytest.raises(ValueError, match="checksum"):
        download.download_part({**part, "sha256": "0" * 64}, tmp_path / "bad-download")
