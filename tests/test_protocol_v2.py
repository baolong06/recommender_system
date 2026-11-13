import hashlib
import math

import pandas as pd
import pytest

from recommender.data.protocol_v2 import DAY_MS, build_splits


def write_neutral(path, sessions):
    rows = []
    for session, day, items in sessions:
        for position, item in enumerate(items):
            clock = day * DAY_MS + position
            rows.append(
                {
                    "session_id": session,
                    "item_id": item,
                    "timestamp_ms": clock,
                    "timestamp": clock // 1000,
                    "raw_row_index": len(rows),
                    "raw_context": "2",
                    "category_id": "UNK",
                }
            )
    pd.DataFrame(rows).to_parquet(path, index=False)


def stable_sessions(items=("a", "b", "c", "d", "e"), day=1):
    return [(f"train-{item}-{n}", day, [item, item]) for item in items for n in range(3)]


def read(path):
    return pd.read_parquet(path)


def run(tmp_path, sessions, dataset="yoochoose", name="split", seeds=(42, 43, 44)):
    path = tmp_path / f"{name}.parquet"
    write_neutral(path, sessions)
    return build_splits(path, tmp_path / name, dataset, seeds=seeds)


def test_future_counts_do_not_fit_train_and_holdout_prefixes_are_preserved(tmp_path):
    audit = run(
        tmp_path,
        stable_sessions()
        + [
            ("rare-train", 1, ["a", "future"]),
            ("validation", 9, ["future"] * 8),
            ("test", 10, ["future", "a", "future"]),
        ],
    )
    universe = set(read(audit["preholdout_items_path"])["item_id"])
    assert universe == {"a", "b", "c", "d", "e"}
    assert read(audit["holdout_paths"]["test"])["item_id"].tolist() == ["future", "a", "future"]
    for seed in audit["seeds"]:
        assert seed["coverage"]["test"]["all_targets"] == 2
        assert seed["coverage"]["test"]["excluded_targets"] == 1
        assert seed["coverage"]["validation"]["excluded_targets"] == 7


@pytest.mark.parametrize(
    "dataset,validation_day,test_day", [("yoochoose", 19, 20), ("diginetica", 7, 14)]
)
def test_global_windows_and_crossing_session_purge(tmp_path, dataset, validation_day, test_day):
    sessions = stable_sessions() + [
        ("validation", validation_day, ["a", "b"]),
        ("test", test_day, ["a", "b"]),
        ("last", 20, ["a", "b"]),
    ]
    path = tmp_path / "raw.parquet"
    write_neutral(path, sessions)
    df = read(path)
    cross = pd.DataFrame(
        [
            {
                "session_id": "cross",
                "item_id": "a",
                "timestamp_ms": validation_day * DAY_MS - 1,
                "timestamp": (validation_day * DAY_MS - 1) // 1000,
                "raw_row_index": len(df),
                "raw_context": "2",
                "category_id": "UNK",
            },
            {
                "session_id": "cross",
                "item_id": "b",
                "timestamp_ms": validation_day * DAY_MS,
                "timestamp": validation_day * DAY_MS // 1000,
                "raw_row_index": len(df) + 1,
                "raw_context": "2",
                "category_id": "UNK",
            },
        ]
    )
    pd.concat([df, cross], ignore_index=True).to_parquet(path, index=False)
    audit = build_splits(path, tmp_path / "split", dataset, seeds=(42,))
    assert audit["temporal_counts"]["crossing"] == {"sessions": 1, "events": 2}
    assert audit["windows_utc_ms"]["validation_start_inclusive"] == validation_day * DAY_MS
    assert audit["windows_utc_ms"]["test_start_inclusive"] == test_day * DAY_MS
    for holdout in audit["holdout_paths"].values():
        assert "cross" not in set(read(holdout)["session_id"])
    assert "cross" not in set(read(audit["seeds"][0]["paths"]["train"])["parent_session_id"])


def test_filtering_never_bridges_a_removed_rare_event(tmp_path):
    audit = run(
        tmp_path,
        stable_sessions()
        + [
            ("bridge", 1, ["a", "rare", "b"]),
            ("validation", 9, ["a", "b"]),
            ("test", 10, ["a", "b"]),
        ],
    )
    for seed in audit["seeds"]:
        train = read(seed["paths"]["train"])
        assert "bridge" not in set(train["parent_session_id"])
        for _, group in train.groupby("session_id"):
            assert len(group) >= 2
            assert group["event_pos"].diff().dropna().eq(1).all()


def test_fixed_point_removes_item_whose_support_was_only_in_lost_segments(tmp_path):
    sessions = stable_sessions() + [(f"cascade-{i}", 1, ["z", f"rare-{i}"]) for i in range(5)]
    audit = run(tmp_path, sessions + [("validation", 9, ["a", "b"]), ("test", 10, ["a", "b"])])
    assert "z" not in set(read(audit["preholdout_items_path"])["item_id"])
    assert len(audit["train_filter_steps"]) >= 2
    assert audit["preholdout_min_item_support"] >= 5


def test_cold_ids_are_deterministic_and_do_not_depend_on_future_targets(tmp_path):
    sessions = stable_sessions() + [("validation", 9, ["a", "b"]), ("test", 10, ["a", "b"])]
    first = run(tmp_path, sessions, name="one")
    second = run(tmp_path, sessions + [("new-future", 10, ["e"] * 10)], name="two")
    universe = sorted(read(first["preholdout_items_path"])["item_id"])
    for before, after in zip(first["seeds"], second["seeds"], strict=True):
        expected = sorted(
            universe,
            key=lambda item: (
                hashlib.sha256(f"yoochoose:{before['seed']}:{item}".encode()).hexdigest(),
                item,
            ),
        )[: math.ceil(0.2 * len(universe))]
        actual = set(read(before["paths"]["cold_items"])["item_id"])
        assert actual == set(expected) == set(read(after["paths"]["cold_items"])["item_id"])
        assert not actual & set(read(before["paths"]["train"])["item_id"])


def test_post_mask_support_is_not_recored(tmp_path):
    items = ["a", "b", "c", "d", "e"]
    cold = min(items, key=lambda item: hashlib.sha256(f"yoochoose:42:{item}".encode()).hexdigest())
    victim = next(item for item in items if item != cold)
    sessions = stable_sessions([item for item in items if item != victim])
    sessions += [("victim-survives", 1, [victim, victim])]
    sessions += [(f"victim-lost-{i}", 1, [victim, cold, cold]) for i in range(3)]
    audit = run(tmp_path, sessions + [("validation", 9, items), ("test", 10, items)], seeds=(42,))
    seed = audit["seeds"][0]
    counts = read(seed["paths"]["train"])["item_id"].value_counts()
    assert counts[victim] == 2
    assert seed["postholdout_min_item_support"] == 2
    assert seed["support_recore_after_holdout"] is False


def test_refuses_overwriting_versioned_outputs(tmp_path):
    source = tmp_path / "input.parquet"
    write_neutral(source, stable_sessions() + [("test", 10, ["a", "b"])])
    output = tmp_path / "output"
    build_splits(source, output, "yoochoose", seeds=(42,))
    with pytest.raises(FileExistsError):
        build_splits(source, output, "yoochoose", seeds=(42,))


def test_row_indexes_must_be_unique(tmp_path):
    source = tmp_path / "input.parquet"
    write_neutral(source, stable_sessions())
    frame = read(source)
    frame["raw_row_index"] = 0
    frame.to_parquet(source, index=False)
    with pytest.raises(ValueError, match="unique"):
        build_splits(source, tmp_path / "output", "yoochoose")


def test_incidental_unseen_is_not_mislabeled_warm(tmp_path):
    items = ["a", "b", "c", "d", "e"]
    cold = min(items, key=lambda item: hashlib.sha256(f"yoochoose:42:{item}".encode()).hexdigest())
    victim = next(item for item in items if item != cold)
    survivor = next(item for item in items if item not in {cold, victim})
    sessions = stable_sessions([item for item in items if item != victim])
    sessions += [(f"incidental-{i}", 1, [victim, cold, victim]) for i in range(3)]
    audit = run(
        tmp_path,
        sessions + [("validation", 9, [survivor, victim]), ("test", 10, [survivor, victim])],
        seeds=(42,),
    )
    seed = audit["seeds"][0]
    assert victim in set(read(seed["paths"]["incidental_items"])["item_id"])
    assert victim not in set(read(seed["paths"]["candidates"])["item_id"])
    assert seed["coverage"]["test"]["incidental_targets"] == 1
    assert seed["coverage"]["test"]["excluded_targets"] == 1
    assert seed["coverage"]["test"]["cold_targets"] == 0
    assert seed["cold_items"] == 1
