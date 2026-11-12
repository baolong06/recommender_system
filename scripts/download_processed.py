"""Download the versioned release parts and verify SHA-256 without extra dependencies."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.request import urlopen


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def download_part(part, output):
    target = output / part["local_path"]
    if not target.resolve().is_relative_to(output.resolve()):
        raise ValueError("Part path escapes output directory")
    if target.exists():
        if target.stat().st_size == part["bytes"] and sha256(target) == part["sha256"]:
            print(f"Verified existing {target}", flush=True)
            return target
        raise ValueError(
            f"Existing file has wrong size/checksum: {target}; move it before retrying"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".parquet.partial")
    digest = hashlib.sha256()
    total = 0
    created = False
    try:
        with urlopen(part["url"], timeout=120) as response, temporary.open("xb") as handle:
            created = True
            while block := response.read(1 << 20):
                handle.write(block)
                digest.update(block)
                total += len(block)
        if total != part["bytes"] or digest.hexdigest() != part["sha256"]:
            raise ValueError(f"Download size/checksum mismatch: {part['asset']}")
        os.replace(temporary, target)
    except BaseException:
        # Only remove the partial file created by this invocation.
        if created and temporary.exists():
            temporary.unlink()
        raise
    print(f"Downloaded and verified {target} ({total:,} bytes)", flush=True)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/processed/manifest.json"))
    parser.add_argument("--dataset", default="all")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    datasets = manifest["datasets"]
    names = list(datasets) if args.dataset == "all" else [args.dataset]
    if any(name not in datasets for name in names):
        parser.error(f"--dataset must be all or one of: {', '.join(datasets)}")
    for name in names:
        for part in datasets[name]["parts"]:
            download_part(part, args.output_dir)


if __name__ == "__main__":
    main()
