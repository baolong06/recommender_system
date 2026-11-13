"""Add distribution metadata without changing the provenance of executed data code."""

import hashlib
import importlib.metadata
import platform
import sys
from pathlib import Path

import pyarrow.parquet as pq


def _sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def enrich_manifest(manifest, output_dir, repo_root, reporting_commit=None):
    """Read Parquet footers and dependency provenance; preserve execution identifiers.

    The caller must use the same Python environment that executed the pipeline.
    ``reporting_commit`` identifies metadata/report publication only; it is never
    substituted for the original code_commit or original source_code_sha256.
    Existing file hashes and byte sizes are verified before enrichment so that
    a changed payload cannot inherit a successful data-validation report.
    """
    output_dir, repo_root = Path(output_dir).resolve(), Path(repo_root).resolve()
    enriched_files = []
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        path = (output_dir / relative).resolve()
        if relative.is_absolute() or not path.is_relative_to(output_dir):
            raise ValueError("Manifest payload must remain inside the output directory")
        if path.stat().st_size != entry["bytes"] or _sha256(path) != entry["sha256"]:
            raise ValueError(f"Payload changed since data validation: {entry['path']}")
        parquet = pq.ParquetFile(path)
        enriched_files.append(
            {
                **entry,
                "rows": parquet.metadata.num_rows,
                "schema": [
                    {
                        "name": field.name,
                        "type": str(field.type),
                        "nullable": field.nullable,
                    }
                    for field in parquet.schema_arrow
                ],
            }
        )
    runtime = {
        "python": sys.version,
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("duckdb", "pandas", "pyarrow", "kagglehub")
        },
        "environment_capture": "same interpreter/environment as the data pipeline",
    }
    locks = {
        name: _sha256(repo_root / name)
        for name in ("requirements-dev.txt", "requirements-audit.txt")
    }
    # Publish only after all payloads and dependencies have been checked.
    manifest["files"] = enriched_files
    manifest["runtime_environment"] = runtime
    manifest["dependency_locks_sha256"] = locks
    if reporting_commit is not None:
        manifest["metadata_reporting_commit"] = reporting_commit
    return manifest
