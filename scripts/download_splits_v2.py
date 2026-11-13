"""Download exact shared v2 splits, verify every file and extract into a new directory."""

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from urllib.request import urlopen


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def extract_bundle(archive, bundle, output):
    expected = {e["path"]: e for e in bundle["files"]}
    with zipfile.ZipFile(archive) as handle:
        names = handle.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError("ZIP file list differs from delivery inventory")
        for entry in handle.infolist():
            dest = output / entry.filename
            if not dest.resolve().is_relative_to(output.resolve()):
                raise ValueError("Unsafe ZIP path")
            if entry.file_size != expected[entry.filename]["bytes"]:
                raise ValueError("ZIP expanded size differs from inventory")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with handle.open(entry) as source, dest.open("xb") as target:
                shutil.copyfileobj(source, target, 1 << 20)
            if sha256(dest) != expected[entry.filename]["sha256"]:
                raise ValueError(f"Extracted checksum mismatch: {entry.filename}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("docs/splits/v2/delivery.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/protocol_v2"))
    parser.add_argument("--dataset", choices=["all", "diginetica", "yoochoose"], default="all")
    parser.add_argument("--cache-dir", type=Path, default=Path("artifacts/split-downloads"))
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    selected = [b for b in manifest["bundles"] if args.dataset in {"all", b["dataset"]}]
    if not selected:
        raise ValueError("No bundle selected")
    for bundle in selected:
        if (args.output_dir / bundle["dataset"]).exists():
            raise FileExistsError("Dataset output exists; choose a new directory")
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    for bundle in selected:
        archive = args.cache_dir / bundle["asset"]
        if not archive.resolve().is_relative_to(args.cache_dir.resolve()):
            raise ValueError("Unsafe archive name")
        if not archive.exists():
            partial = archive.with_suffix(".partial")
            with urlopen(bundle["url"], timeout=120) as response, partial.open("xb") as handle:
                shutil.copyfileobj(response, handle, 1 << 20)
            if partial.stat().st_size != bundle["bytes"] or sha256(partial) != bundle["sha256"]:
                raise ValueError("Download size/SHA-256 mismatch")
            partial.rename(archive)
        elif archive.stat().st_size != bundle["bytes"] or sha256(archive) != bundle["sha256"]:
            raise ValueError("Cached ZIP size/SHA-256 mismatch")
        extract_bundle(archive, bundle, args.output_dir)
        print(f"Downloaded, extracted and verified {bundle['dataset']}", flush=True)
    return 0


if __name__ == "__main__":
    main()
