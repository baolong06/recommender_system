"""Read raw Yoochoose and Diginetica files into the shared event schema."""

from pathlib import Path

import pandas as pd

EVENT_COLUMNS = ["session_id", "item_id", "timestamp", "category_id"]
MISSING_CATEGORY = "UNK"
_EPOCH = pd.Timestamp("1970-01-01", tz="UTC")


def to_unix_seconds(values: pd.Series) -> pd.Series:
    """Convert date strings (UTC) to integer Unix seconds, truncating sub-second parts."""
    moments = pd.to_datetime(values, utc=True)
    return ((moments - _EPOCH) // pd.Timedelta(seconds=1)).astype("int64")


def most_frequent_category(events: pd.DataFrame) -> pd.Series:
    """One category per item: the most frequent one, ties broken by smaller category ID."""
    counts = events.groupby(["item_id", "category_id"]).size().reset_index(name="n")
    counts = counts.sort_values(["item_id", "n", "category_id"], ascending=[True, False, True])
    return counts.drop_duplicates("item_id").set_index("item_id")["category_id"]


def read_yoochoose(path: str | Path, nrows: int | None = None) -> pd.DataFrame:
    """Raw columns: session, ISO timestamp, item, category. No header, comma separated."""
    events = pd.read_csv(
        path,
        header=None,
        nrows=nrows,
        names=["session_id", "ts", "item_id", "category_id"],
        dtype=str,
    )
    events["timestamp"] = to_unix_seconds(events["ts"])
    events["category_id"] = events["category_id"].fillna(MISSING_CATEGORY)
    events["category_id"] = events["item_id"].map(most_frequent_category(events))
    return events[EVENT_COLUMNS]


def read_diginetica(views_path: str | Path, categories_path: str | Path) -> pd.DataFrame:
    """Views: sessionId;userId;itemId;timeframe;eventdate. Categories: itemId;categoryId."""
    views = pd.read_csv(views_path, sep=";", dtype=str)
    categories = pd.read_csv(categories_path, sep=";", dtype=str)
    categories = categories.drop_duplicates("itemId")
    timeframe_ms = pd.to_numeric(views["timeframe"]).astype("int64")
    views["timestamp"] = to_unix_seconds(views["eventdate"]) + timeframe_ms // 1000
    events = views.merge(categories, on="itemId", how="left")
    events = events.rename(
        columns={"sessionId": "session_id", "itemId": "item_id", "categoryId": "category_id"}
    )
    events["category_id"] = events["category_id"].fillna(MISSING_CATEGORY)
    return events[EVENT_COLUMNS]


def validate_events(events: pd.DataFrame) -> None:
    if list(events.columns) != EVENT_COLUMNS:
        raise ValueError(f"columns must be {EVENT_COLUMNS}")
    for column in ["session_id", "item_id", "category_id"]:
        if events[column].isna().any() or (events[column] == "").any():
            raise ValueError(f"{column} contains missing or empty values")
    if events["timestamp"].dtype != "int64" or (events["timestamp"] < 0).any():
        raise ValueError("timestamp must be non-negative int64 Unix seconds")
