"""Verify handed-off files and independently check leakage before fitting baselines."""

import hashlib
import json
import math
from pathlib import Path

import duckdb


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def payload(root, relative):
    path = (Path(root) / relative.replace("\\", "/")).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError("Manifest payload escapes dataset directory")
    return path


def relation(path):
    return "read_parquet('" + str(path).replace("'", "''") + "')"


def accept_dataset(root, expected_seeds=(42, 43, 44)):
    root = Path(root).resolve()
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["protocol_version"] != "P0-data-v2":
        raise ValueError("Require P0-data-v2 inputs")
    dataset = manifest["dataset"]
    if dataset not in {"diginetica", "yoochoose"}:
        raise ValueError("Unknown dataset")
    files = {}
    for entry in manifest["files"]:
        name = entry["path"].replace("\\", "/")
        path = payload(root, name)
        if (
            name in files
            or path.stat().st_size != entry["bytes"]
            or sha256(path) != entry["sha256"]
        ):
            raise ValueError(f"Input size/SHA-256/identity mismatch: {name}")
        files[name] = entry
    audit = manifest["split_audit"]
    if [s["seed"] for s in audit["seeds"]] != list(expected_seeds):
        raise ValueError("Require all three fixed split seeds")
    windows = audit["windows_utc_ms"]
    if not (
        windows["train_end_exclusive"]
        == windows["validation_start_inclusive"]
        < windows["validation_end_exclusive"]
        == windows["test_start_inclusive"]
        < windows["test_end_exclusive"]
    ):
        raise ValueError("Invalid temporal windows")
    verified = []
    with duckdb.connect() as con:
        con.execute("SET threads=2")
        con.execute("SET memory_limit='2GB'")

        def load(name, path):
            if path not in files:
                raise ValueError(f"Missing payload from manifest: {path}")
            con.execute(
                f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM {relation(payload(root, path))}"
            )

        def zero(query, message):
            if con.execute(query).fetchone()[0]:
                raise ValueError(message)

        load("universe", "splits/preholdout_items.parquet")
        universe = [r[0] for r in con.execute("SELECT item_id FROM universe").fetchall()]
        if (
            len(universe) != len(set(universe))
            or len(universe) != audit["preholdout_item_universe"]
        ):
            raise ValueError("Invalid U0 universe")
        for window in ("validation", "test"):
            load(window, f"splits/{window}.parquet")
            lo, hi = windows[f"{window}_start_inclusive"], windows[f"{window}_end_exclusive"]
            zero(
                f"SELECT count(*) FROM {window} WHERE timestamp_ms<{lo} OR timestamp_ms>={hi}",
                "Holdout violates temporal window",
            )
        zero(
            "SELECT count(*) FROM (SELECT DISTINCT session_id FROM validation) v "
            "JOIN (SELECT DISTINCT session_id FROM test) t USING(session_id)",
            "Holdout overlap",
        )
        for info in audit["seeds"]:
            seed = info["seed"]
            for name in ("train", "cold_items", "candidates", "incidental_items"):
                load(name, f"splits/seed-{seed}/{name}.parquet")
            ordered = sorted(
                universe,
                key=lambda i: (hashlib.sha256(f"{dataset}:{seed}:{i}".encode()).hexdigest(), i),
            )
            cold = [r[0] for r in con.execute("SELECT item_id FROM cold_items").fetchall()]
            if len(cold) != len(set(cold)) or set(cold) != set(
                ordered[: math.ceil(0.2 * len(universe))]
            ):
                raise ValueError("Controlled cold selection differs from protocol")
            zero(
                "SELECT count(*) FROM train JOIN cold_items USING(item_id)", "Cold leaked into fit"
            )
            zero(
                f"SELECT count(*) FROM train WHERE timestamp_ms>={windows['train_end_exclusive']}",
                "Train contains future events",
            )
            for window in ("validation", "test"):
                zero(
                    "SELECT count(*) FROM (SELECT DISTINCT parent_session_id FROM train) t "
                    f"JOIN (SELECT DISTINCT session_id FROM {window}) h "
                    "ON t.parent_session_id=h.session_id",
                    "Train/holdout parent session overlap",
                )
            zero(
                "SELECT count(*) FROM (SELECT session_id,count(*) n FROM train "
                "GROUP BY session_id) WHERE n<2",
                "Short training segment",
            )
            zero(
                "WITH seq AS (SELECT event_pos,timestamp_ms,lag(event_pos) OVER w p,"
                "lag(timestamp_ms) OVER w t FROM train WINDOW w AS (PARTITION BY session_id "
                "ORDER BY event_pos)) SELECT count(*) FROM seq "
                "WHERE event_pos-p<>1 OR timestamp_ms<t",
                "Segment crosses a removed event",
            )
            con.execute(
                "CREATE OR REPLACE TEMP TABLE actual_support AS "
                "SELECT item_id,count(*) support FROM train GROUP BY item_id"
            )
            zero(
                "SELECT count(*) FROM actual_support ANTI JOIN universe USING(item_id)",
                "Train item outside preholdout universe",
            )
            con.execute(
                "CREATE OR REPLACE TEMP TABLE expected_candidates AS "
                "SELECT item_id,'warm' AS \"group\",support FROM actual_support UNION ALL "
                "SELECT item_id,'cold',0 FROM cold_items"
            )
            zero(
                "SELECT count(*) FROM ((SELECT * FROM expected_candidates EXCEPT ALL "
                'SELECT item_id,"group",support FROM candidates) UNION ALL '
                '(SELECT item_id,"group",support FROM candidates EXCEPT ALL '
                "SELECT * FROM expected_candidates))",
                "Candidate membership/support mismatch",
            )
            con.execute(
                "CREATE OR REPLACE TEMP TABLE expected_incidental AS "
                "SELECT item_id FROM universe EXCEPT "
                "(SELECT item_id FROM actual_support UNION SELECT item_id FROM cold_items)"
            )
            zero(
                "SELECT count(*) FROM ((SELECT item_id FROM expected_incidental EXCEPT ALL "
                "SELECT item_id FROM incidental_items) UNION ALL "
                "(SELECT item_id FROM incidental_items EXCEPT ALL "
                "SELECT item_id FROM expected_incidental))",
                "Incidental item mismatch",
            )
            events, parents, items = con.execute(
                "SELECT count(*),count(DISTINCT parent_session_id),"
                "count(DISTINCT item_id) FROM train"
            ).fetchone()
            if dict(events=events, parent_sessions=parents, items=items) != info["final_train"]:
                raise ValueError("Training counts differ from manifest")
            coverage = {}
            for window in ("validation", "test"):
                row = con.execute(
                    "WITH seq AS (SELECT item_id,row_number() OVER (PARTITION BY session_id "
                    f"ORDER BY timestamp_ms,raw_row_index) pos FROM {window}) "
                    "SELECT count(*),count(*) FILTER(WHERE c.\"group\"='warm'),"
                    "count(*) FILTER(WHERE c.\"group\"='cold'),"
                    "count(*) FILTER(WHERE c.item_id IS NULL) FROM seq "
                    "LEFT JOIN candidates c USING(item_id) WHERE pos>1"
                ).fetchone()
                coverage[window] = dict(
                    zip(
                        ("all_targets", "warm_targets", "cold_targets", "excluded_targets"),
                        row,
                        strict=True,
                    )
                )
                if any(info["coverage"][window][k] != v for k, v in coverage[window].items()):
                    raise ValueError("Evaluation target coverage mismatch")
            verified.append(
                {
                    "seed": seed,
                    "train_events": events,
                    "warm_items": items,
                    "cold_items": len(cold),
                    "coverage": coverage,
                    "checks": "passed",
                }
            )
    return {
        "dataset": dataset,
        "data_version": manifest["protocol_version"],
        "data_manifest_sha256": sha256(manifest_path),
        "payload_files_verified": len(files),
        "windows_utc_ms": windows,
        "checks": [
            "all payload sizes and SHA-256",
            "fixed cold SHA-256 selection and ceil20%",
            "cold absent from fit",
            "train/holdout windows and parent sessions disjoint",
            "segments min2 and no bridges across removed events",
            "candidate membership and support equal actual final train plus cold",
            "incidental set exact",
            "coverage recounted from observed targets",
        ],
        "seeds": verified,
        "status": "passed",
    }
