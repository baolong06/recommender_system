"""Iterative cleaning with a before/after record for every filter step."""

import pandas as pd


def count_events(events: pd.DataFrame) -> dict[str, int]:
    return {
        "events": int(len(events)),
        "sessions": int(events["session_id"].nunique()),
        "items": int(events["item_id"].nunique()),
    }


def clean_events(
    events: pd.DataFrame,
    min_session_length: int,
    min_item_frequency: int,
    repeat_until_stable: bool = True,
    max_iterations: int = 10,
) -> tuple[pd.DataFrame, list[dict]]:
    """Order: drop missing, drop duplicates, then item frequency and session length.

    The last two steps repeat until the number of events stops changing.
    """
    if min_session_length < 1 or min_item_frequency < 1 or max_iterations < 1:
        raise ValueError("cleaning thresholds and max_iterations must be positive")
    events = events.copy()
    steps: list[dict] = [{"step": "raw", **count_events(events)}]

    for column in ["session_id", "item_id"]:
        events[column] = events[column].astype("string").str.strip().replace("", pd.NA)
    clock = "timestamp_ms" if "timestamp_ms" in events else "timestamp"
    events = events.dropna(subset=["session_id", "item_id", "timestamp", clock])
    steps.append({"step": "drop_missing", **count_events(events)})
    events = events[(events["timestamp"] >= 0) & (events[clock] >= 0)]
    steps.append({"step": "drop_invalid_timestamp", **count_events(events)})
    events = events.drop_duplicates(["session_id", "item_id", clock])
    steps.append({"step": "drop_duplicates", **count_events(events)})

    for iteration in range(1, max_iterations + 1):
        events_before = len(events)
        counts = events["item_id"].value_counts()
        frequent = counts.index[counts >= min_item_frequency]
        events = events[events["item_id"].isin(frequent)]
        steps.append({"step": f"item_frequency_{iteration}", **count_events(events)})

        lengths = events.groupby("session_id")["item_id"].transform("size")
        events = events[lengths >= min_session_length]
        steps.append({"step": f"session_length_{iteration}", **count_events(events)})

        if not repeat_until_stable or len(events) == events_before:
            break
    else:
        raise RuntimeError("filtering did not stabilise within max_iterations")

    events = events.sort_values(["session_id", clock], kind="stable")
    for column in {"timestamp", clock}:
        events[column] = events[column].astype("int64")
    return events.reset_index(drop=True), steps
