"""Package exact, verified v2 payloads and manifest for transfer to another machine."""

import argparse
import json
import zipfile
from pathlib import Path

from recommender.splits.acceptance import payload, sha256


def package(input_root, output, tag, datasets):
    output.mkdir(parents=True, exist_ok=False)
    bundles = []
    for dataset in datasets:
        root = input_root / dataset
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["dataset"] != dataset or manifest["protocol_version"] != "P0-data-v2":
            raise ValueError("Unexpected dataset manifest")
        entries = [
            *manifest["files"],
            {
                "path": "manifest.json",
                "sha256": sha256(manifest_path),
                "bytes": manifest_path.stat().st_size,
            },
        ]
        target = output / f"{dataset}-P0-v2-all-seeds.zip"
        print(f"Packaging {dataset}", flush=True)
        with zipfile.ZipFile(
            target, "w", compression=zipfile.ZIP_STORED, allowZip64=True
        ) as archive:
            for entry in entries:
                path = payload(root, entry["path"])
                if path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
                    raise ValueError(f"Payload changed: {path}")
                archive.write(path, f"{dataset}/{entry['path'].replace(chr(92), '/')}")
        if target.stat().st_size >= 2 * 1024**3:
            raise ValueError("Bundle exceeds GitHub asset limit; split by seed before publishing")
        bundles.append(
            {
                "dataset": dataset,
                "asset": target.name,
                "sha256": sha256(target),
                "bytes": target.stat().st_size,
                "data_manifest_sha256": sha256(manifest_path),
                "url": f"https://github.com/baolong06/recommender_system/releases/download/{tag}/{target.name}",
                "files": [
                    {
                        "path": f"{dataset}/{e['path'].replace(chr(92), '/')}",
                        "bytes": e["bytes"],
                        "sha256": e["sha256"],
                    }
                    for e in entries
                ],
            }
        )
    delivery = {
        "kind": "P0-v2-shared-splits",
        "release_tag": tag,
        "release_url": f"https://github.com/baolong06/recommender_system/releases/tag/{tag}",
        "bundles": bundles,
    }
    (output / "delivery.json").write_text(json.dumps(delivery, indent=2) + "\n", encoding="utf-8")
    return delivery


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    package(args.input_root, args.output_dir, args.tag, ["diginetica", "yoochoose"])


if __name__ == "__main__":
    main()
