"""Dataset baseline correctness, leakage rejection and independently seeded reproducibility."""

import json
import math
import runpy
import zipfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from recommender.baselines_v2 import evaluate_window, popularity_topk, random_topk, summarise
from recommender.splits.acceptance import accept_dataset, sha256

ROOT = Path(__file__).resolve().parents[1]


def test_popularity_train_counts_and_ties():
    # Lexicographic IDs deliberately differ from numeric order; cold has zero support.
    assert popularity_topk({"2": 5, "10": 5}, ["cold", "2", "10"], 20) == ["10", "2", "cold"]
    with pytest.raises(ValueError):
        popularity_topk({}, ["a", "a"], 1)


def test_random_query_identity_never_reads_label_and_is_order_independent():
    candidates = [str(i) for i in range(100)]
    kwargs = dict(dataset="yoochoose", split_seed=42, model_seed=43, window="test")
    query = {"session_id": "s", "raw_row_index": 7, "target": "10"}
    first = random_topk(candidates, 20, query=query, **kwargs)
    assert first == random_topk(candidates, 20, query={**query, "target": "80"}, **kwargs)
    assert first != random_topk(candidates, 20, query={**query, "raw_row_index": 8}, **kwargs)
    assert first != random_topk(candidates, 20, query=query, **{**kwargs, "model_seed": 44})
    assert len(set(first)) == 20 and set(first) <= set(candidates)
    assert len(random_topk(candidates, 200, query=query, **kwargs)) == 100


def test_streaming_metrics_match_hand_calculation_and_exclude_oov_targets(tmp_path):
    events = tmp_path / "events.parquet"
    candidates = tmp_path / "candidates.parquet"
    pq.write_table(
        pa.table(
            {
                "session_id": ["s"] * 4,
                "item_id": ["a", "oov", "b", "c"],
                "timestamp_ms": [1, 2, 3, 4],
                "raw_row_index": [0, 1, 2, 3],
            }
        ),
        events,
    )
    pq.write_table(
        pa.table({"item_id": ["a", "b", "c"], "group": ["warm", "warm", "cold"]}), candidates
    )
    rows = evaluate_window(
        events,
        candidates,
        {"a": 10, "b": 5},
        dataset="yoochoose",
        split_seed=42,
        model_seeds=[42, 43, 44],
        window="test",
        k=3,
    )
    pop = {r["group"]: r for r in rows if r["model"] == "Popularity"}
    assert pop["overall"]["n"] == 2
    assert pop["overall"]["hr"] == 1
    assert pop["overall"]["mrr"] == pytest.approx((1 / 2 + 1 / 3) / 2)
    assert pop["overall"]["ndcg"] == pytest.approx((1 / math.log2(3) + 0.5) / 2)
    assert pop["cold"]["mrr"] == pytest.approx(1 / 3)
    # Changing evaluation multiplicity cannot change train-fitted popularity.
    assert pop["warm"]["mrr"] == 0.5


def test_summary_uses_split_means_not_nine_independent_runs():
    rows = []
    for split, values in [(42, [0.0, 0.0, 0.0]), (43, [0.5, 0.5, 0.5]), (44, [1.0, 1.0, 1.0])]:
        for model_seed, value in zip([42, 43, 44], values, strict=True):
            rows.append(
                dict(
                    dataset="diginetica",
                    evaluation_split="test",
                    model="Random",
                    k=20,
                    group="warm",
                    split_seed=split,
                    model_seed=model_seed,
                    n=10,
                    hr=value,
                    mrr=value,
                    ndcg=value,
                )
            )
    summary = summarise(rows)[0]
    assert summary["metrics"]["hr"] == {"mean": 0.5, "sample_std": 0.5, "contributing_splits": 3}
    assert [s["metrics"]["hr"]["sample_std"] for s in summary["splits"]] == [0.0, 0.0, 0.0]
    for row in rows:
        row.update(n=0, hr=None, mrr=None, ndcg=None)
    assert summarise(rows)[0]["metrics"]["hr"]["mean"] is None


@pytest.fixture
def small_dataset(tmp_path):
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
    runpy.run_path(str(ROOT / "scripts/run_protocol_v2.py"))["run_dataset"](
        "yoochoose", tmp_path / "raw", tmp_path / "data", ROOT / "configs/data_v2.toml", 7
    )
    return tmp_path / "data"


def test_complete_runner_and_reproducible_results(small_dataset, tmp_path):
    run = runpy.run_path(str(ROOT / "scripts/run_baselines_v2.py"))["run"]
    config = ROOT / "configs/baselines_v2.toml"
    first, second = tmp_path / "first", tmp_path / "second"
    run(small_dataset, first, config, ["yoochoose"])
    run(small_dataset, second, config, ["yoochoose"])
    assert (first / "runs.json").read_bytes() == (second / "runs.json").read_bytes()
    assert (first / "summary.json").read_bytes() == (second / "summary.json").read_bytes()
    rows = json.loads((first / "runs.json").read_text())
    assert len(rows) == 72
    assert {r["model_seed"] for r in rows if r["model"] == "Popularity"} == {None}
    assert {r["n"] for r in rows if r["group"] == "overall"} == {5}
    with pytest.raises(FileExistsError):
        run(small_dataset, first, config, ["yoochoose"])


def test_corrupt_payload_and_forged_candidate_support_are_rejected(small_dataset):
    directory = small_dataset / "yoochoose"
    assert accept_dataset(directory)["status"] == "passed"
    path = directory / "splits/seed-42/candidates.parquet"
    table = pq.read_table(path)
    table = table.set_column(
        table.schema.get_field_index("support"), "support", pa.array([999] * len(table))
    )
    pq.write_table(table, path)
    with pytest.raises(ValueError, match="SHA-256"):
        accept_dataset(directory)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["files"]:
        if Path(entry["path"]).name == "candidates.parquet" and "seed-42" in entry["path"]:
            entry.update(sha256=sha256(path), bytes=path.stat().st_size)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="support mismatch"):
        accept_dataset(directory)


def test_split_bundle_roundtrip_preserves_exact_manifest_and_payloads(small_dataset, tmp_path):
    package = runpy.run_path(str(ROOT / "scripts/package_splits_v2.py"))["package"]
    downloader = runpy.run_path(str(ROOT / "scripts/download_splits_v2.py"))
    packages = tmp_path / "packages"
    delivery = package(small_dataset, packages, "test-only", ["yoochoose"])
    bundle = delivery["bundles"][0]
    bundle["url"] = (packages / bundle["asset"]).as_uri()
    manifest = tmp_path / "delivery.json"
    manifest.write_text(json.dumps(delivery))
    destination = tmp_path / "downloaded"
    downloader["main"](
        [
            "--manifest",
            str(manifest),
            "--output-dir",
            str(destination),
            "--cache-dir",
            str(tmp_path / "cache"),
        ]
    )
    assert (destination / "yoochoose/manifest.json").read_bytes() == (
        small_dataset / "yoochoose/manifest.json"
    ).read_bytes()
    assert accept_dataset(destination / "yoochoose")["status"] == "passed"
    with pytest.raises(FileExistsError):
        downloader["main"](["--manifest", str(manifest), "--output-dir", str(destination)])


def test_bundle_rejects_path_escape(tmp_path):
    downloader = runpy.run_path(str(ROOT / "scripts/download_splits_v2.py"))
    path = tmp_path / "bad.zip"
    with zipfile.ZipFile(path, "w") as handle:
        handle.writestr("../outside", b"x")
    bundle = {"files": [{"path": "../outside", "bytes": 1}]}
    with pytest.raises(ValueError, match="Unsafe ZIP path"):
        downloader["extract_bundle"](path, bundle, tmp_path / "output")
