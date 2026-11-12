"""Read raw datasets, retaining invalid rows for the logged cleaning stage."""

from pathlib import Path

import pandas as pd

EVENT_COLUMNS = ["session_id", "item_id", "timestamp", "category_id"]
PRECISE_COLUMNS = [*EVENT_COLUMNS, "timestamp_ms"]
MISSING_CATEGORY = "UNK"


def to_unix_milliseconds(values: pd.Series) -> pd.Series:
    """Invalid/missing dates become NA; UTC milliseconds preserve click order."""
    moments = pd.to_datetime(values, utc=True, errors="coerce", format="mixed")
    return moments.dt.as_unit("ms").astype("int64").astype("Int64").mask(moments.isna())


def to_unix_seconds(values: pd.Series) -> pd.Series:
    return to_unix_milliseconds(values) // 1000


def most_frequent_category(events: pd.DataFrame) -> pd.Series:
    """One category per item; ties use lexicographic category ID order."""
    counts = events.groupby(["item_id", "category_id"]).size().reset_index(name="n")
    counts = counts.sort_values(["item_id", "n", "category_id"], ascending=[True, False, True])
    return counts.drop_duplicates("item_id").set_index("item_id")["category_id"]


def read_yoochoose(path: str | Path, nrows: int | None = None) -> pd.DataFrame:
    """Raw columns: session, ISO timestamp, item, category; no header."""
    if nrows is not None and nrows <= 0:
        raise ValueError("nrows must be positive")
    events = pd.read_csv(
        path,
        header=None,
        nrows=nrows,
        names=["session_id", "ts", "item_id", "category_id"],
        dtype=str,
    )
    events["timestamp_ms"] = to_unix_milliseconds(events["ts"])
    events["timestamp"] = events["timestamp_ms"] // 1000
    events["category_id"] = events["category_id"].fillna(MISSING_CATEGORY)
    events["category_id"] = events["item_id"].map(most_frequent_category(events))
    return events[PRECISE_COLUMNS]


def read_diginetica(views_path: str | Path, categories_path: str | Path) -> pd.DataFrame:
    """Combine UTC eventdate with timeframe in milliseconds; malformed values become NA."""
    views = pd.read_csv(views_path, sep=";", dtype=str)
    categories = pd.read_csv(categories_path, sep=";", dtype=str).drop_duplicates("itemId")
    timeframe = pd.to_numeric(views["timeframe"], errors="coerce")
    valid = timeframe.ge(0) & timeframe.mod(1).eq(0)
    timeframe = timeframe.where(valid).astype("Int64")
    views["timestamp_ms"] = to_unix_milliseconds(views["eventdate"]) + timeframe
    views["timestamp"] = views["timestamp_ms"] // 1000
    events = views.merge(categories, on="itemId", how="left")
    events = events.rename(
        columns={"sessionId": "session_id", "itemId": "item_id", "categoryId": "category_id"}
    )
    events["category_id"] = events["category_id"].fillna(MISSING_CATEGORY)
    return events[PRECISE_COLUMNS]


def validate_events(events: pd.DataFrame) -> None:
    if list(events.columns) not in [EVENT_COLUMNS, PRECISE_COLUMNS]:
        raise ValueError(f"columns must be {EVENT_COLUMNS}, optionally followed by timestamp_ms")
    for column in ["session_id", "item_id", "category_id"]:
        if events[column].isna().any() or events[column].str.strip().eq("").any():
            raise ValueError(f"{column} contains missing or empty values")
    for column in ["timestamp", *(["timestamp_ms"] if "timestamp_ms" in events else [])]:
        if str(events[column].dtype) not in {"int64", "Int64"} or (
            events[column].isna().any() or (events[column] < 0).any()
        ):
            raise ValueError(f"{column} must be non-negative int64 without missing values")
    if (
        "timestamp_ms" in events
        and not (events["timestamp_ms"] // 1000).eq(events["timestamp"]).all()
    ):
        raise ValueError("timestamp and timestamp_ms must describe the same instant")
