"""Download pinned Kaggle v1 inputs and verify raw checksums before staging them."""

import argparse
import hashlib
import os
import shutil
from pathlib import Path

SOURCES = {
    "yoochoose": (
        "phhasian0710/yoochoose/versions/1",
        {
            "yoochoose-clicks.dat": (
                "0deaf041a4f60955928fe8430e525a1dbf38e9013c7482420973e4aa492fa762"
            ),
        },
    ),
    "diginetica": (
        "profalbusdumbledore/diginetica-dataset/versions/1",
        {
            "train-item-views.csv": (
                "0b9edf1b7960bb855a2248972f8ed593f18721f321b976b2077c9f782fb43e38"
            ),
            "product-categories.csv": (
                "9e9566e34548e5d1b8d05ed6dd0222fbb8a7b7b2a8a18cdf28c1a4eba8f9e42c"
            ),
        },
    ),
}


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def fetch_raw(dataset, raw_root, download_fn=None):
    handle, files = SOURCES[dataset]
    output = Path(raw_root) / dataset
    output.mkdir(parents=True, exist_ok=True)
    missing = []
    for name, expected in files.items():
        target = output / name
        if target.exists():
            if sha256(target) != expected:
                raise ValueError(f"Existing raw checksum mismatch: {target}")
        else:
            missing.append(name)
    if not missing:
        return output
    if download_fn is None:
        import kagglehub

        download_fn = kagglehub.dataset_download
    cache = Path(download_fn(handle))
    for name in missing:
        paths = sorted(cache.rglob(name), key=lambda p: (len(p.parts), p.as_posix()))
        if not paths:
            raise FileNotFoundError(f"Required file missing: {name}")
        source = paths[0]
        if sha256(source) != files[name]:
            raise ValueError(f"Downloaded raw checksum mismatch: {name}")
        target = output / name
        partial = target.with_name(target.name + ".partial")
        created = False
        try:
            # Exclusive staging prevents overwriting an unrelated interrupted download.
            with source.open("rb") as inp, partial.open("xb") as out:
                created = True
                shutil.copyfileobj(inp, out, 1 << 20)
            if sha256(partial) != files[name]:
                raise ValueError(f"Staged raw checksum mismatch: {name}")
            if target.exists():
                raise FileExistsError(target)
            target.hardlink_to(partial)
        finally:
            if created:
                partial.unlink(missing_ok=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=[*SOURCES, "all"], default="all")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()
    if args.cache_dir:
        os.environ["KAGGLEHUB_CACHE"] = str(args.cache_dir.resolve())
    for dataset in SOURCES if args.dataset == "all" else [args.dataset]:
        print(f"Verified {dataset}: {fetch_raw(dataset, args.raw_dir)}", flush=True)


if __name__ == "__main__":
    main()
