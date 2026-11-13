"""Stream raw event logs without fitting support or category statistics on heldout data."""

import hashlib
import os
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

SCHEMA = pa.schema(
    [
        ("session_id", pa.string()),
        ("item_id", pa.string()),
        ("timestamp", pa.int64()),
        ("category_id", pa.string()),
        ("timestamp_ms", pa.int64()),
        ("raw_row_index", pa.int64()),
        ("raw_context", pa.string()),
    ]
)
MAX_INT64 = 9223372036854775807


def _hash(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_catalog(path):
    """Read a static catalog, rejecting missing IDs and ambiguous item mappings."""
    catalog = pd.read_csv(path, sep=";", dtype="string[pyarrow]", keep_default_na=False)
    if not isinstance(catalog.index, pd.RangeIndex):
        raise ValueError("Malformed static catalog CSV structure")
    if not {"itemId", "categoryId"}.issubset(catalog.columns):
        raise ValueError("Static catalog requires itemId and categoryId")
    catalog = catalog[["itemId", "categoryId"]].copy()
    catalog["itemId"] = catalog["itemId"].str.strip()
    catalog["categoryId"] = catalog["categoryId"].str.strip()
    if catalog.isna().any().any() or catalog.eq("").any().any():
        raise ValueError("Static catalog contains missing item/category IDs")
    if catalog.groupby("itemId")["categoryId"].nunique().gt(1).any():
        raise ValueError("Static catalog contains conflicting category mappings")
    duplicate_rows = int(catalog.duplicated("itemId").sum())
    catalog = catalog.drop_duplicates("itemId")
    return catalog, duplicate_rows


def _milliseconds(values):
    moments = pd.to_datetime(values, utc=True, errors="coerce", format="mixed")
    return moments.dt.as_unit("ms").astype("int64").astype("Int64").mask(moments.isna())


def _offsets(values):
    text = values.astype("string").str.strip()
    # Compare normalized decimal text before conversion to avoid overflow/float rounding.
    normalized = text.str.lstrip("0").replace("", "0")
    valid = text.str.fullmatch(r"[0-9]+", na=False)
    valid &= normalized.str.len().lt(19) | (
        normalized.str.len().eq(19) & normalized.le(str(MAX_INT64))
    )
    return pd.Series(pd.array(normalized.where(valid), dtype="Int64"), index=values.index)


def normalize_dataset(dataset, raw_dir, output, batch_size=500000):
    """Keep every valid source event, millisecond clock, context, and original row identity."""
    if dataset not in {"yoochoose", "diginetica"}:
        raise ValueError("Unknown dataset")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    raw_dir, output = Path(raw_dir), Path(output)
    source = raw_dir / (
        "yoochoose-clicks.dat" if dataset == "yoochoose" else "train-item-views.csv"
    )
    raw_files = [source]
    mapping = None
    identical = 0
    if dataset == "diginetica":
        catalog_path = raw_dir / "product-categories.csv"
        raw_files.append(catalog_path)
        catalog, identical = read_catalog(catalog_path)
        mapping = catalog.set_index("itemId")["categoryId"]
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".partial")
    if temporary.exists():
        raise FileExistsError(temporary)
    reasons = {
        name: 0
        for name in [
            "missing_session_or_item",
            "invalid_date",
            "invalid_timeframe",
            "negative_timestamp",
        ]
    }
    audit = {
        "dataset": dataset,
        "raw_rows": 0,
        "valid_rows": 0,
        "dropped_reasons": reasons,
        "raw_files": [
            {"path": str(p), "sha256": _hash(p), "bytes": p.stat().st_size} for p in raw_files
        ],
        "duplicate_policy": "keep-all-valid-events; global flag added by runner",
        "support_filter_applied": False,
        "identical_catalog_duplicates_collapsed": identical,
    }
    kwargs = {"dtype": "string[pyarrow]", "keep_default_na": False, "chunksize": batch_size}
    if dataset == "yoochoose":
        kwargs.update(header=None, names=["session_id", "date", "item_id", "raw_context"])
    else:
        kwargs.update(sep=";")
    reader = pd.read_csv(source, **kwargs)
    created = False
    try:
        with temporary.open("xb") as handle:
            created = True
            with pq.ParquetWriter(handle, SCHEMA, compression="zstd") as writer:
                for chunk in reader:
                    if not isinstance(chunk.index, pd.RangeIndex):
                        raise ValueError(
                            "Malformed CSV structure: implicit index from excess columns"
                        )
                    if dataset == "diginetica":
                        required = {"sessionId", "itemId", "eventdate", "timeframe"}
                        if not required.issubset(chunk.columns):
                            raise ValueError("Diginetica views missing required columns")
                        chunk = chunk.rename(
                            columns={
                                "sessionId": "session_id",
                                "itemId": "item_id",
                                "eventdate": "date",
                            }
                        )
                    for field in ("session_id", "item_id"):
                        chunk[field] = chunk[field].str.strip()
                    chunk["raw_row_index"] = range(
                        audit["raw_rows"], audit["raw_rows"] + len(chunk)
                    )
                    audit["raw_rows"] += len(chunk)
                    dates = _milliseconds(chunk["date"])
                    remaining = pd.Series(True, index=chunk.index)

                    def reject(reason, bad):
                        nonlocal remaining
                        bad = bad.fillna(True) & remaining
                        reasons[reason] += int(bad.sum())
                        remaining &= ~bad

                    reject(
                        "missing_session_or_item",
                        chunk["session_id"].eq("") | chunk["item_id"].eq(""),
                    )
                    reject("invalid_date", dates.isna())
                    if dataset == "diginetica":
                        offsets = _offsets(chunk["timeframe"])
                        overflow = offsets.gt(MAX_INT64 - dates.clip(lower=0))
                        reject("invalid_timeframe", offsets.isna() | overflow)
                        clock = dates.where(remaining, 0) + offsets.where(remaining, 0)
                        chunk["category_id"] = chunk["item_id"].map(mapping).fillna("UNK")
                        chunk["raw_context"] = ""
                    else:
                        clock = dates
                        chunk["category_id"] = "UNK"
                    reject("negative_timestamp", dates.lt(0) | clock.lt(0))
                    valid = chunk.loc[remaining].copy()
                    valid["timestamp_ms"] = clock.loc[remaining].astype("int64")
                    valid["timestamp"] = valid["timestamp_ms"] // 1000
                    writer.write_table(
                        pa.Table.from_pandas(
                            valid[SCHEMA.names], schema=SCHEMA, preserve_index=False
                        )
                    )
                    audit["valid_rows"] += len(valid)
        os.link(temporary, output)
        temporary.unlink()
    except BaseException:
        if created:
            temporary.unlink(missing_ok=True)
        raise
    finally:
        reader.close()
    audit["dropped_rows"] = sum(reasons.values())
    assert audit["raw_rows"] == audit["valid_rows"] + audit["dropped_rows"]
    audit["output_sha256"] = _hash(output)
    audit["output_bytes"] = output.stat().st_size
    return audit
