"""Independently reconstruct handed-off mappings only from permitted sources."""

import json
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

from recommender.splits.acceptance import relation, sha256


def verify_mapping(directory, seed, raw_root=None):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    dataset = manifest["dataset"]
    seed_dir = directory / f"splits/seed-{seed}"
    table = pq.read_table(seed_dir / "category_mapping.parquet").to_pydict()
    items, categories = table["item_id"], table["category_id"]
    if len(items) != len(set(items)) or any(c is None or not c.strip() for c in categories):
        raise ValueError("Invalid category mapping")
    candidates = pq.read_table(seed_dir / "candidates.parquet").to_pydict()
    if set(items) != set(candidates["item_id"]):
        raise ValueError("Mapping must contain exactly all candidates")
    mapping = dict(zip(items, categories, strict=True))
    train = relation(seed_dir / "train.parquet")
    source_hash = None
    with duckdb.connect() as con:
        con.execute("SET threads=2")
        if dataset == "yoochoose":
            reconstructed = dict(
                con.execute(
                    "WITH counts AS (SELECT item_id,raw_context category,count(*) n "
                    f"FROM {train} WHERE raw_context IN "
                    "('1','2','3','4','5','6','7','8','9','10','11','12') "
                    "GROUP BY item_id,raw_context),"
                    "ranks AS (SELECT *,row_number() OVER(PARTITION BY item_id ORDER BY "
                    "n DESC,cast(category AS INTEGER)) r FROM counts) "
                    "SELECT item_id,category FROM ranks WHERE r=1"
                ).fetchall()
            )
            policy = "final-train-only-genuine-context"
        elif dataset == "diginetica":
            if raw_root is None:
                raise ValueError("Diginetica mapping verification requires allowed raw catalog")
            catalog = Path(raw_root) / "diginetica/product-categories.csv"
            source_hash = sha256(catalog)
            expected = [
                f["sha256"]
                for f in manifest["normalization_before_duplicate_flag"]["raw_files"]
                if Path(f["path"].replace("\\", "/")).name == catalog.name
            ]
            if expected != [source_hash]:
                raise ValueError("Catalog SHA-256 differs from original data source")
            import csv

            reconstructed = {}
            with catalog.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle, delimiter=";"):
                    item, category = row["itemId"], row["categoryId"]
                    if not item.strip() or not category.strip():
                        raise ValueError("Empty catalog item/category")
                    if item in reconstructed and reconstructed[item] != category:
                        raise ValueError("Conflicting catalog categories")
                    reconstructed[item] = category
            policy = "static-catalog-known-at-inference-assumption"
        else:
            raise ValueError("Unknown dataset")
    if any(mapping[item] != reconstructed.get(item, "UNK") for item in items):
        raise ValueError("Handed-off category mapping differs from allowed source")
    groups = dict(zip(candidates["item_id"], candidates["group"], strict=True))
    coverage = {
        g: {
            "items": sum(groups[i] == g for i in items),
            "known": sum(groups[i] == g and mapping[i] != "UNK" for i in items),
        }
        for g in ("warm", "cold")
    }
    if dataset == "yoochoose" and coverage["cold"]["known"]:
        raise ValueError("Yoochoose cold category leakage")
    return mapping, {
        "seed": seed,
        "metadata_policy": policy,
        "coverage": coverage,
        "allowed_source_reconstruction_equal": True,
        "mapping_sha256": sha256(seed_dir / "category_mapping.parquet"),
        "static_catalog_sha256": source_hash,
        "historical_catalog_availability_verified": False,
    }
