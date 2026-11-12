import json
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from recommender.data.cleaning import clean_events  # noqa: E402
from recommender.data.manifest import build_manifest, file_entry  # noqa: E402
from recommender.data.readers import (  # noqa: E402
    EVENT_COLUMNS,
    read_diginetica,
    read_yoochoose,
    validate_events,
)

ROOT = Path(__file__).resolve().parents[1]


def test_fixture_short_session_removed():
    events = pd.read_csv(ROOT / "tests/fixtures/raw_events.example.csv", dtype=str)
    events["timestamp"] = events["timestamp"].astype("int64")
    cleaned, _ = clean_events(events, min_session_length=2, min_item_frequency=1)
    assert "session-short" not in set(cleaned["session_id"])
    assert set(cleaned["session_id"]) == {"session-a", "session-b"}


def test_iterative_filter_stabilises_and_logs_steps():
    events = pd.DataFrame(
        {
            "session_id": ["a", "a", "b", "b", "c", "c"],
            "item_id": ["1", "2", "2", "3", "1", "2"],
            "timestamp": [1, 2, 3, 4, 5, 6],
            "category_id": ["x"] * 6,
        }
    )
    cleaned, steps = clean_events(events, min_session_length=2, min_item_frequency=2)
    assert set(cleaned["item_id"]) == {"1", "2"}
    assert set(cleaned["session_id"]) == {"a", "c"}
    assert steps[0]["step"] == "raw" and steps[0]["events"] == 6
    assert steps[-1]["events"] == len(cleaned)


def test_read_yoochoose(tmp_path):
    path = tmp_path / "clicks.dat"
    path.write_text(
        "1,2014-04-07T10:51:09.277Z,0123,0\n"
        "1,2014-04-07T10:54:09.868Z,9,1\n"
        "2,2014-04-07T10:55:00.000Z,9,2\n"
        "3,2014-04-07T10:56:00.000Z,9,2\n"
        "3,2014-04-07T10:57:00.000Z,77,\n",
        encoding="utf-8",
    )
    events = read_yoochoose(path)
    validate_events(events)
    assert list(events.columns) == EVENT_COLUMNS
    assert events.loc[0, "item_id"] == "0123"
    assert events.loc[0, "timestamp"] == 1396867869
    assert set(events.loc[events["item_id"] == "9", "category_id"]) == {"2"}
    assert events.loc[events["item_id"] == "77", "category_id"].iloc[0] == "UNK"


def test_read_diginetica(tmp_path):
    views = tmp_path / "views.csv"
    views.write_text(
        "sessionId;userId;itemId;timeframe;eventdate\n"
        "1;NA;0081;526309;2016-05-09\n"
        "1;NA;31331;1031018;2016-05-09\n",
        encoding="utf-8",
    )
    categories = tmp_path / "cats.csv"
    categories.write_text("itemId;categoryId\n0081;1096\n", encoding="utf-8")
    events = read_diginetica(views, categories)
    validate_events(events)
    day = int(pd.Timestamp("2016-05-09", tz="UTC").timestamp())
    assert events.loc[0, "item_id"] == "0081"
    assert events.loc[0, "timestamp"] == day + 526
    assert events.loc[1, "category_id"] == "UNK"


def test_manifest_matches_template_keys(tmp_path):
    raw = tmp_path / "raw.csv"
    raw.write_text("a\nb\n", encoding="utf-8")
    steps = [
        {"step": "raw", "events": 2, "sessions": 1, "items": 2},
        {"step": "final", "events": 1, "sessions": 1, "items": 1},
    ]
    manifest = build_manifest(
        kind="research-run",
        dataset="demo",
        dataset_version="v0",
        source_reference="local",
        config_path="configs/data.toml",
        raw_files=[file_entry(raw, "local")],
        processed_files=[],
        steps=steps,
        reproduce_command="python scripts/run_clean.py --dataset demo",
    )
    template = json.loads((ROOT / "docs/data/data_manifest.example.json").read_text("utf-8"))
    assert set(manifest) == set(template)
    assert len(manifest["raw_files"][0]["sha256"]) == 64
    assert manifest["raw_files"][0]["rows"] == 2
