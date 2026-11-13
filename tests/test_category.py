"""Hand-checked ranking, oracle boundaries, metadata sources and partial cohort metrics."""

import inspect
import json
import runpy
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from recommender.category import CategoryPopularity
from recommender.category_evaluation import (
    category_summary,
    evaluate_categories,
    paired_differences,
)
from recommender.category_metadata import verify_mapping
from recommender.evaluation import GroupMetrics, evaluate_groups

ROOT = Path(__file__).resolve().parents[1]


def tiny_model(k=2):
    return CategoryPopularity(
        {"a": 10, "b": 5}, ["a", "b", "cold"], {"a": "X", "b": "Y", "cold": "Y"}, k
    )


def test_category_priority_order_cold_zero_and_global_fill():
    model = tiny_model()
    assert model.predict_non_oracle(["b"]) == ["b", "cold"]
    assert model.predict_oracle("Y") == ["b", "cold"]
    assert model.predict_non_oracle(["a"]) == ["a", "b"]
    assert model.predict_non_oracle(["__OOV__"]) == ["a", "b"]
    assert model.predict_oracle("UNK") is None
    assert model.counts.get("cold", 0) == 0
    assert len(set(tiny_model(10).predict_oracle("Y"))) == 3
    with pytest.raises(ValueError, match="allowed"):
        model.predict_oracle("future-category")


def test_non_oracle_modal_category_tie_uses_latest_and_never_takes_target():
    model = tiny_model()
    assert model.select_category(["a", "b"]) == "Y"
    assert model.select_category(["a", "b", "a"]) == "X"
    assert model.select_category(["a", "b", "__OOV__"]) == "Y"
    assert list(inspect.signature(model.predict_non_oracle).parameters) == ["prefix"]
    assert list(inspect.signature(model.predict_oracle).parameters) == ["target_category"]
    first = model.predict_non_oracle(["a", "b"])
    first.clear()
    assert model.predict_non_oracle(["a", "b"]) == ["b", "cold"]


def test_group_metrics_are_target_based_micro_average_and_explicit_na():
    result = evaluate_groups([{"target": "a"}] * 3 + [{"target": "cold"}], [["a"]] * 4, {"cold"}, 1)
    assert result["overall"]["metrics"]["hr"] == 0.75
    acc = GroupMetrics(1)
    acc.add("a", ["a"], "warm")
    acc.add("cold", None, "cold", "no catalog")
    rows = acc.result()
    assert rows["overall"]["n"] == 1 and rows["overall"]["n_eligible"] == 2
    assert rows["overall"]["support_fraction"] == 0.5
    assert rows["overall"]["status"] == "partial"
    assert rows["cold"]["metrics"]["hr"] is None and rows["cold"]["status"] == "N/A"
    assert rows["cold"]["unsupported"] == {"no catalog": 1}
    for k in [0, -1, True, 1.2]:
        with pytest.raises(ValueError):
            GroupMetrics(k)
    with pytest.raises(ValueError):
        acc.add("x", None, "cold")
    with pytest.raises(ValueError):
        acc.add("x", ["x"], "invalid")


def write_events(tmp_path, targets):
    events = tmp_path / "events.parquet"
    pq.write_table(
        pa.table(
            {
                "session_id": ["s"] * len(targets),
                "item_id": targets,
                "timestamp_ms": list(range(len(targets))),
                "raw_row_index": list(range(len(targets))),
            }
        ),
        events,
    )
    candidates = tmp_path / "candidates.parquet"
    pq.write_table(
        pa.table({"item_id": ["a", "b", "cold"], "group": ["warm", "warm", "cold"]}), candidates
    )
    return events, candidates


def test_yoochoose_cold_is_na_and_matched_references_have_identical_support(tmp_path):
    events, candidates = write_events(tmp_path, ["a", "cold", "b"])
    model = CategoryPopularity(
        {"a": 10, "b": 5}, ["a", "b", "cold"], {"a": "X", "b": "UNK", "cold": "UNK"}, 2
    )
    rows = evaluate_categories(
        events,
        candidates,
        model,
        dataset="yoochoose",
        split_seed=42,
        model_seeds=[42, 43, 44],
        window="test",
    )
    for row in rows:
        if row["group"] == "cold":
            assert row["n"] == 0 and row["hr"] is None and row["n_eligible"] == 1
        if row["cohort"] == "oracle-supported":
            assert row["n"] == 0
        elif row["group"] == "overall":
            assert row["n"] == 1 and row["n_eligible"] == 2 and row["status"] == "partial"
    # Oracle unknown warm targets are N/A; non-oracle scores them without knowing their category.
    assert all(
        r["metrics"]["hr"]["mean_difference"] is None
        for r in paired_differences(rows)
        if r["cohort"] == "oracle-supported"
    )
    assert all(
        r["metrics"]["hr"]["mean"] is None
        for r in category_summary(rows)
        if r["cohort"] == "oracle-supported"
    )


def test_non_oracle_same_prefix_same_prediction_after_changing_target(tmp_path):
    events, candidates = write_events(tmp_path, ["a", "b"])
    model = tiny_model()
    seen = []
    original = model.predict_non_oracle

    def spy(prefix):
        ranking = original(prefix)
        seen.append((list(prefix), ranking))
        return ranking

    model.predict_non_oracle = spy
    kwargs = dict(dataset="diginetica", split_seed=42, model_seeds=[42], window="test")
    evaluate_categories(events, candidates, model, **kwargs)
    events, _ = write_events(tmp_path, ["a", "cold"])
    evaluate_categories(events, candidates, model, **kwargs)
    assert seen[0] == seen[1] == (["a"], ["a", "b"])
    assert model.counts == {"a": 10, "b": 5}


@pytest.fixture
def experiment(tmp_path):
    raw = tmp_path / "raw/yoochoose"
    raw.mkdir(parents=True)
    lines = []
    for sid in range(10):
        for pos, item in enumerate(["1", "2", "3", "4", "5"] * 2):
            lines.append(f"{sid},2020-01-01T00:00:00.{pos:03d}Z,{item},{item}\n")
    for sid, day in [("v", 29), ("t", 30)]:
        for pos, item in enumerate(["outside", "1", "2", "3", "4", "5"]):
            lines.append(f"{sid},2020-01-{day:02d}T00:00:00.{pos:03d}Z,{item},S\n")
    (raw / "yoochoose-clicks.dat").write_text("".join(lines))
    data = tmp_path / "data"
    runpy.run_path(str(ROOT / "scripts/run_protocol_v2.py"))["run_dataset"](
        "yoochoose", tmp_path / "raw", data, ROOT / "configs/data_v2.toml", 7
    )
    reference = tmp_path / "reference"
    runpy.run_path(str(ROOT / "scripts/run_baselines_v2.py"))["run"](
        data, reference, ROOT / "configs/baselines_v2.toml", ["yoochoose"]
    )
    return data, reference, tmp_path / "raw"


def test_end_to_end_reproducibility_and_three_model_seeds(experiment, tmp_path):
    data, reference, raw = experiment
    run = runpy.run_path(str(ROOT / "scripts/run_category_v2.py"))["run"]
    for name in ["first", "second"]:
        run(data, tmp_path / name, ROOT / "configs/category_v2.toml", ["yoochoose"], reference, raw)
    for name in ["runs.json", "summary.json", "paired_differences.json"]:
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()
    rows = json.loads((tmp_path / "first/runs.json").read_text())
    assert len(rows) == 252
    assert {r["model_seed"] for r in rows if r["model"] == "Random"} == {42, 43, 44}
    assert all(
        r["hr"] is None
        for r in rows
        if r["group"] == "cold" and r["model"].startswith("CatPopularity")
    )
    report = runpy.run_path(str(ROOT / "scripts/verify_category_results.py"))["verify"](
        data, tmp_path / "first/runs.json", tmp_path / "independent-check.json"
    )
    assert report["category_and_matched_popularity_rows"] == 72
    assert not report["shared_prediction_or_metric_code_used"]
    with pytest.raises(FileExistsError):
        run(
            data,
            tmp_path / "first",
            ROOT / "configs/category_v2.toml",
            ["yoochoose"],
            reference,
            raw,
        )


def test_mapping_must_equal_train_only_source_and_reference_tamper_fails(experiment):
    data, reference, _ = experiment
    mapping, report = verify_mapping(data / "yoochoose", 42)
    assert report["allowed_source_reconstruction_equal"]
    path = data / "yoochoose/splits/seed-42/category_mapping.parquet"
    table = pq.read_table(path)
    table = table.set_column(1, "category_id", pa.array(["12"] * len(table)))
    pq.write_table(table, path)
    with pytest.raises(ValueError, match="allowed source"):
        verify_mapping(data / "yoochoose", 42)
    (reference / "runs.json").write_text("[]")
    with pytest.raises(ValueError, match="hash mismatch"):
        runpy.run_path(str(ROOT / "scripts/run_category_v2.py"))["read_verified_reference"](
            reference
        )


def test_diginetica_catalog_hash_and_mapping_are_checked(tmp_path):
    from recommender.splits.acceptance import sha256

    directory = tmp_path / "data/diginetica"
    seed = directory / "splits/seed-42"
    seed.mkdir(parents=True)
    raw = tmp_path / "raw/diginetica"
    raw.mkdir(parents=True)
    catalog = raw / "product-categories.csv"
    catalog.write_text("itemId;categoryId\na;X\nb;Y\ncold;Y\n")
    pq.write_table(
        pa.table({"item_id": ["a", "b", "cold"], "group": ["warm", "warm", "cold"]}),
        seed / "candidates.parquet",
    )
    pq.write_table(
        pa.table({"item_id": ["a", "b", "cold"], "category_id": ["X", "Y", "Y"]}),
        seed / "category_mapping.parquet",
    )
    manifest = {
        "dataset": "diginetica",
        "normalization_before_duplicate_flag": {
            "raw_files": [{"path": "product-categories.csv", "sha256": sha256(catalog)}]
        },
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    mapping, report = verify_mapping(directory, 42, tmp_path / "raw")
    assert mapping["cold"] == "Y" and report["coverage"]["cold"]["known"] == 1
    assert not report["historical_catalog_availability_verified"]
    with pytest.raises(ValueError, match="requires"):
        verify_mapping(directory, 42)
    catalog.write_text(catalog.read_text() + "future;Z\n")
    with pytest.raises(ValueError, match="SHA-256"):
        verify_mapping(directory, 42, tmp_path / "raw")
