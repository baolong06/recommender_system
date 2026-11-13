"""Stream next-item examples without deleting OOV positions from the prefix."""

from pathlib import Path

import pyarrow.parquet as pq


def iter_examples(events_path: Path, candidates_path: Path, oov_token: str = "__OOV__"):
    """Yield eligible target examples from a session/time/raw-index sorted event file.

    All preceding observations, including targets excluded from the primary metric,
    remain prefix positions. No target category or future suffix is exposed.
    """
    catalog = pq.read_table(candidates_path, columns=["item_id", "group"]).to_pydict()
    pairs = list(zip(catalog["item_id"], catalog["group"], strict=True))
    groups = dict(pairs)
    if len(groups) != len(pairs) or any(group not in {"warm", "cold"} for group in groups.values()):
        raise ValueError("Candidates require unique IDs and warm/cold groups")
    if oov_token in groups:
        raise ValueError("OOV token conflicts with a candidate ID")
    previous_key = None
    session = None
    prefix = []
    for batch in pq.ParquetFile(events_path).iter_batches(
        batch_size=20000, columns=["session_id", "item_id", "timestamp_ms", "raw_row_index"]
    ):
        values = batch.to_pydict()
        for sid, item, clock, raw_index in zip(
            values["session_id"],
            values["item_id"],
            values["timestamp_ms"],
            values["raw_row_index"],
            strict=True,
        ):
            key = (sid, clock, raw_index)
            if previous_key is not None and key < previous_key:
                raise ValueError("Evaluation events must be sorted by session, time and source row")
            previous_key = key
            if sid != session:
                session, prefix = sid, []
            if prefix and item in groups:
                yield {
                    "session_id": sid,
                    "prefix": list(prefix),
                    "target": item,
                    "group": groups[item],
                    "timestamp_ms": clock,
                    "raw_row_index": raw_index,
                }
            prefix.append(item if item in groups else oov_token)
