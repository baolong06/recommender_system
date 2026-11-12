import json
from pathlib import Path

import pandas as pd
import pytest

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
    assert list(events.columns) == [*EVENT_COLUMNS, "timestamp_ms"]
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


def test_cleaning_preserves_subsecond_clicks_and_chronology(tmp_path):
    path = tmp_path / "clicks.dat"
    path.write_text(
        "1,2014-04-07T10:51:09.900Z,9,1\n"
        "1,2014-04-07T10:51:09.100Z,9,1\n"
        "1,2014-04-07T10:51:09.100Z,9,1\n",
        encoding="utf-8",
    )
    cleaned, steps = clean_events(read_yoochoose(path), 2, 1)
    validate_events(cleaned)
    assert len(cleaned) == 2
    assert cleaned["timestamp"].nunique() == 1
    assert cleaned["timestamp_ms"].tolist() == [1396867869100, 1396867869900]
    assert next(s for s in steps if s["step"] == "drop_duplicates")["events"] == 2


def test_invalid_yoochoose_rows_are_logged_and_removed(tmp_path):
    path = tmp_path / "clicks.dat"
    path.write_text(
        "1,2014-04-07T10:51:09.100Z,9,1\n"
        "1,2014-04-07T10:51:09.900Z,10,1\n"
        ",2014-04-07T10:51:10Z,9,1\n"
        "1,not-a-date,9,1\n"
        "1,,9,1\n"
        "1,2014-04-07T10:51:10Z, ,1\n"
        "1,1960-01-01T00:00:00Z,9,1\n",
        encoding="utf-8",
    )
    cleaned, steps = clean_events(read_yoochoose(path), 2, 1)
    validate_events(cleaned)
    assert len(cleaned) == 2
    assert steps[0]["events"] == 7
    assert next(s for s in steps if s["step"] == "drop_missing")["events"] == 3
    assert next(s for s in steps if s["step"] == "drop_invalid_timestamp")["events"] == 2


def test_invalid_diginetica_dates_and_offsets_are_cleaned(tmp_path):
    views, cats = tmp_path / "views.csv", tmp_path / "cats.csv"
    views.write_text(
        "sessionId;userId;itemId;timeframe;eventdate\n"
        "1;NA;1;100;2016-05-09\n1;NA;2;900;2016-05-09\n"
        "1;NA;3;bad;2016-05-09\n1;NA;4;-1;2016-05-09\n"
        "1;NA;5;1;bad-date\n1;NA;6;1.5;2016-05-09\n",
        encoding="utf-8",
    )
    cats.write_text("itemId;categoryId\n1;7\n", encoding="utf-8")
    cleaned, steps = clean_events(read_diginetica(views, cats), 2, 1)
    validate_events(cleaned)
    assert cleaned["item_id"].tolist() == ["1", "2"]
    assert steps[1]["events"] == 2


def test_record_count_excludes_header_and_handles_final_record(tmp_path):
    path = tmp_path / "records.csv"
    path.write_text('id,value\n1,"multi\nline"\n2,end', encoding="utf-8")
    assert file_entry(path, "local", has_header=True)["rows"] == 2
    assert file_entry(path, "local")["rows"] == 3


@pytest.mark.parametrize("dataset", ["yoochoose", "diginetica"])
def test_clean_cli_exports_parquet_and_replayable_manifest(tmp_path, dataset):
    import shlex
    import subprocess
    import sys

    raw = tmp_path / "raw" / dataset
    raw.mkdir(parents=True)
    if dataset == "yoochoose":
        (raw / "yoochoose-clicks.dat").write_text(
            "1,2014-04-07T10:51:09.900Z,9,1\n1,2014-04-07T10:51:09.100Z,9,1\n1,broken,9,1\n",
            encoding="utf-8",
        )
    else:
        (raw / "train-item-views.csv").write_text(
            "sessionId;userId;itemId;timeframe;eventdate\n"
            "1;NA;9;900;2016-05-09\n1;NA;9;100;2016-05-09\n"
            "1;NA;9;bad;2016-05-09",
            encoding="utf-8",
        )
        (raw / "product-categories.csv").write_text("itemId;categoryId\n9;1", encoding="utf-8")
    config = tmp_path / "data config.toml"
    config.write_text(
        f'kind = "research-run"\n[input]\nraw_directory = "{(tmp_path / "raw").as_posix()}"\n'
        f'[output]\nprocessed_directory = "{(tmp_path / "processed").as_posix()}"\n'
        f'manifest_directory = "{(tmp_path / "manifests").as_posix()}"\n'
        "[cleaning]\nmin_session_length = 2\nmin_item_frequency = 1\n"
        "repeat_until_stable = true\nmax_iterations = 10\n",
        encoding="utf-8",
    )
    arguments = [
        "--dataset",
        dataset,
        "--config",
        str(config),
        "--source-reference",
        "Kaggle sample with spaces",
    ]
    subprocess.run([sys.executable, "scripts/run_clean.py", *arguments], cwd=ROOT, check=True)
    manifest = json.loads((tmp_path / "manifests" / f"{dataset}_manifest.json").read_text())
    cleaned = pd.read_parquet(tmp_path / "processed" / f"{dataset}_clean.parquet")
    validate_events(cleaned)
    assert len(cleaned) == 2
    assert cleaned["timestamp_ms"].is_monotonic_increasing
    assert manifest["counts_before"]["events"] == 3
    assert manifest["counts_after"]["events"] == 2
    assert manifest["raw_files"][0]["rows"] == 3
    assert shlex.split(manifest["reproduce_command"]) == [
        "python",
        "scripts/run_clean.py",
        *arguments,
    ]
    assert (
        file_entry(manifest["processed_files"][0]["path"], "local", rows=2)["sha256"]
        == (manifest["processed_files"][0]["sha256"])
    )
    # Invoke the same main(argv) API with unrelated process argv to guard against sys.argv leakage.
    import runpy

    main = runpy.run_path(str(ROOT / "scripts/run_clean.py"))["main"]
    assert main(arguments) == 0
    replayed = json.loads((tmp_path / "manifests" / f"{dataset}_manifest.json").read_text())
    assert replayed["reproduce_command"] == manifest["reproduce_command"]
