import hashlib

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from recommender.data.provenance_v2 import enrich_manifest


def test_metadata_preserves_execution_provenance_and_rejects_changed_payload(tmp_path):
    payload = tmp_path / "payload.parquet"
    pq.write_table(pa.table({"item_id": ["001", "002"]}), payload)
    for name in ("requirements-dev.txt", "requirements-audit.txt"):
        (tmp_path / name).write_text("pandas==2.3.3\n")
    manifest = {
        "code_commit": "executed",
        "source_code_sha256": {"runner": "original"},
        "files": [
            {
                "path": payload.name,
                "bytes": payload.stat().st_size,
                "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
            }
        ],
    }
    enriched = enrich_manifest(manifest, tmp_path, tmp_path, "reporting")
    assert enriched["code_commit"] == "executed"
    assert enriched["source_code_sha256"] == {"runner": "original"}
    assert enriched["metadata_reporting_commit"] == "reporting"
    assert enriched["files"][0]["rows"] == 2
    assert enriched["files"][0]["schema"] == [
        {"name": "item_id", "type": "string", "nullable": True}
    ]
    payload.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Payload changed"):
        enrich_manifest(manifest, tmp_path, tmp_path)
