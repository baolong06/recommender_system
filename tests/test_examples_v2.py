from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from recommender.data.examples_v2 import iter_examples


def save(path: Path, values):
    pq.write_table(pa.Table.from_pylist(values), path)


def test_oov_target_still_remains_in_later_prefix_and_target_has_no_category(tmp_path):
    events, candidates = tmp_path / "events.parquet", tmp_path / "candidates.parquet"
    save(candidates, [{"item_id": "a", "group": "warm"}, {"item_id": "b", "group": "cold"}])
    save(
        events,
        [
            {
                "session_id": "s",
                "item_id": item,
                "timestamp_ms": i,
                "raw_row_index": i,
                "category_id": "TARGET_SECRET",
            }
            for i, item in enumerate(["a", "x", "b", "a"])
        ],
    )
    examples = list(iter_examples(events, candidates))
    assert [e["target"] for e in examples] == ["b", "a"]
    assert examples[0]["prefix"] == ["a", "__OOV__"]
    assert examples[1]["prefix"] == ["a", "__OOV__", "b"]
    assert examples[0]["group"] == "cold"
    assert "category" not in str(examples[0])


def test_unsorted_evaluation_file_is_rejected(tmp_path):
    events, candidates = tmp_path / "events.parquet", tmp_path / "candidates.parquet"
    save(candidates, [{"item_id": "a", "group": "warm"}])
    save(
        events,
        [
            {"session_id": "s", "item_id": "a", "timestamp_ms": i, "raw_row_index": i}
            for i in [2, 1]
        ],
    )
    with pytest.raises(ValueError, match="sorted"):
        list(iter_examples(events, candidates))
