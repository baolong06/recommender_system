"""Disk-backed temporal splits and train-only filtering for P0 data protocol v2."""

import math
from pathlib import Path

import duckdb

DAY_MS = 86_400_000
MAX_CORE_ITERATIONS = 100


def _literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _counts(con, table):
    row = con.execute(
        f"SELECT count(*), count(DISTINCT parent_session_id), count(DISTINCT item_id) FROM {table}"
    ).fetchone()
    return dict(zip(("events", "parent_sessions", "items"), map(int, row), strict=True))


def _copy(con, query, path):
    con.execute(f"COPY ({query}) TO {_literal(path)} (FORMAT PARQUET, COMPRESSION ZSTD)")
    return str(path)


def _segment(con, source, destination):
    # event_pos is the position in the ORIGINAL session. A gap from any earlier
    # pruning pass must remain a boundary in subsequent iterations.
    con.execute(
        f"""CREATE OR REPLACE TABLE {destination} AS
        WITH numbered AS (
            SELECT *, event_pos-row_number() OVER (
                PARTITION BY parent_session_id ORDER BY event_pos
            ) AS gap FROM {source}
        ), segments AS (
            SELECT * EXCLUDE(gap),
                min(event_pos) OVER(PARTITION BY parent_session_id,gap) AS segment_start,
                count(*) OVER(PARTITION BY parent_session_id,gap) AS segment_length
            FROM numbered
        ) SELECT * EXCLUDE(segment_start,segment_length),
            parent_session_id || '::segment::' || segment_start::VARCHAR AS session_id
        FROM segments WHERE segment_length>=2"""
    )


def build_splits(neutral_path, output_dir, dataset, seeds=(42, 43, 44), connection=None):
    """Export unchanged holdout streams, seed-specific training segments and catalogs.

    Input needs session_id, item_id, timestamp_ms, raw_row_index; extra fields survive.
    Holdout target eligibility is reported separately, so excluding an OOV target
    never deletes that event from another target's original observed prefix.
    Existing nonempty output directories are rejected to preserve data versions.
    """
    if dataset not in {"yoochoose", "diginetica"}:
        raise ValueError("dataset must be yoochoose or diginetica")
    seeds = tuple(seeds)
    if not seeds or any(type(s) is not int for s in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be distinct integers")
    neutral_path, output_dir = Path(neutral_path), Path(output_dir)
    if not neutral_path.is_file():
        raise FileNotFoundError(neutral_path)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Use a new output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    temp = output_dir / ".tmp"
    temp.mkdir()
    owned = connection is None
    con = connection or duckdb.connect(str(temp / "protocol.duckdb"))
    if owned:
        con.execute("SET memory_limit='2GB'")
        con.execute("SET threads=2")
        con.execute("SET preserve_insertion_order=false")
        con.execute(f"SET temp_directory={_literal(temp / 'spill')}")
    try:
        con.execute(
            "CREATE OR REPLACE VIEW neutral AS SELECT * FROM "
            f"read_parquet({_literal(neutral_path)})"
        )
        columns = {row[0] for row in con.execute("DESCRIBE neutral").fetchall()}
        required = {"session_id", "item_id", "timestamp_ms", "raw_row_index"}
        if not required <= columns:
            raise ValueError(f"neutral input missing {sorted(required - columns)}")
        reserved = {"parent_session_id", "event_pos", "gap", "segment_start", "segment_length"}
        if columns & reserved:
            raise ValueError("neutral input contains reserved helper columns")
        maximum = con.execute("SELECT max(timestamp_ms) FROM neutral").fetchone()[0]
        if maximum is None:
            raise ValueError("neutral input must not be empty")
        invalid = con.execute(
            "SELECT count(*) FROM neutral WHERE session_id IS NULL OR trim(session_id)='' "
            "OR item_id IS NULL OR trim(item_id)='' OR timestamp_ms IS NULL "
            "OR timestamp_ms<0 OR raw_row_index IS NULL OR raw_row_index<0"
        ).fetchone()[0]
        if invalid:
            raise ValueError("neutral input has invalid identifiers, clocks or row indexes")
        if con.execute("SELECT count(*)-count(DISTINCT raw_row_index) FROM neutral").fetchone()[0]:
            raise ValueError("raw_row_index must be globally unique")
        day = int(maximum) // DAY_MS * DAY_MS
        test_start = day if dataset == "yoochoose" else day - 6 * DAY_MS
        validation_start = test_start - (DAY_MS if dataset == "yoochoose" else 7 * DAY_MS)
        test_end = day + DAY_MS
        con.execute(
            "CREATE OR REPLACE TABLE session_windows AS SELECT session_id,count(*) n,"
            "min(timestamp_ms) first_ms,max(timestamp_ms) last_ms FROM neutral GROUP BY session_id"
        )
        con.execute(
            f"""CREATE OR REPLACE TABLE assignments AS SELECT *,CASE
            WHEN n<2 THEN 'singleton'
            WHEN (first_ms<{validation_start} AND last_ms>={validation_start})
              OR (first_ms<{test_start} AND last_ms>={test_start}) THEN 'crossing'
            WHEN last_ms<{validation_start} THEN 'train'
            WHEN first_ms>={validation_start} AND last_ms<{test_start} THEN 'validation'
            WHEN first_ms>={test_start} AND last_ms<{test_end} THEN 'test'
            ELSE 'outside' END AS split FROM session_windows"""
        )
        temporal = {
            split: {"sessions": int(sessions), "events": int(events)}
            for split, sessions, events in con.execute(
                "SELECT split,count(*),sum(n) FROM assignments GROUP BY split ORDER BY split"
            ).fetchall()
        }
        con.execute(
            "CREATE OR REPLACE TABLE train_base AS SELECT n.* EXCLUDE(session_id),"
            "n.session_id parent_session_id,row_number() OVER(PARTITION BY n.session_id "
            "ORDER BY timestamp_ms,raw_row_index) event_pos FROM neutral n "
            "JOIN assignments a USING(session_id) WHERE a.split='train'"
        )
        before = _counts(con, "train_base")
        con.execute("CREATE OR REPLACE TABLE core AS SELECT * FROM train_base")
        steps = []
        previous = before["events"]
        for iteration in range(1, MAX_CORE_ITERATIONS + 1):
            projection = "c.* EXCLUDE(session_id)" if iteration > 1 else "c.*"
            con.execute(
                f"CREATE OR REPLACE TABLE supported AS SELECT {projection} FROM core c "
                "JOIN (SELECT item_id FROM core GROUP BY item_id HAVING count(*)>=5) i "
                "USING(item_id)"
            )
            supported = int(con.execute("SELECT count(*) FROM supported").fetchone()[0])
            _segment(con, "supported", "next_core")
            current = _counts(con, "next_core")
            steps.append(
                {"iteration": iteration, "after_item_support_events": supported, **current}
            )
            con.execute("DROP TABLE core")
            con.execute("ALTER TABLE next_core RENAME TO core")
            if current["events"] == previous:
                break
            previous = current["events"]
        else:
            raise RuntimeError("Train filtering did not stabilize within 100 iterations")
        con.execute("CREATE OR REPLACE TABLE u0 AS SELECT DISTINCT item_id FROM core")
        size = int(con.execute("SELECT count(*) FROM u0").fetchone()[0])
        if not size:
            raise ValueError("Train-only filtering produced an empty item universe")
        universe_path = _copy(
            con, "SELECT * FROM u0 ORDER BY item_id", output_dir / "preholdout_items.parquet"
        )
        holdout_paths = {}
        for split in ("validation", "test"):
            con.execute(
                f"CREATE OR REPLACE VIEW {split}_rows AS SELECT n.* FROM neutral n "
                f"JOIN assignments a USING(session_id) WHERE a.split={_literal(split)}"
            )
            holdout_paths[split] = _copy(
                con,
                f"SELECT * FROM {split}_rows ORDER BY session_id,timestamp_ms,raw_row_index",
                output_dir / f"{split}.parquet",
            )
        pre_support = int(
            con.execute(
                "SELECT min(n) FROM (SELECT count(*) n FROM core GROUP BY item_id)"
            ).fetchone()[0]
        )
        seed_audits = []
        for seed in seeds:
            seed_dir = output_dir / f"seed-{seed}"
            seed_dir.mkdir()
            cold_count = math.ceil(0.2 * size)
            prefix = _literal(f"{dataset}:{seed}:")
            con.execute(
                "CREATE OR REPLACE TABLE cold AS SELECT item_id,"
                f"sha256({prefix}||item_id) selection_sha256 FROM u0 "
                f"ORDER BY selection_sha256,item_id LIMIT {cold_count}"
            )
            con.execute(
                "CREATE OR REPLACE TABLE warm_survivors AS SELECT c.* EXCLUDE(session_id) "
                "FROM core c ANTI JOIN cold USING(item_id)"
            )
            masked_count = int(con.execute("SELECT count(*) FROM warm_survivors").fetchone()[0])
            _segment(con, "warm_survivors", "final_train")
            con.execute(
                "CREATE OR REPLACE TABLE warm AS SELECT item_id,count(*) support "
                "FROM final_train GROUP BY item_id"
            )
            con.execute(
                "CREATE OR REPLACE TABLE incidental AS SELECT item_id FROM u0 "
                "ANTI JOIN cold USING(item_id) ANTI JOIN warm USING(item_id)"
            )
            con.execute(
                "CREATE OR REPLACE TABLE candidates AS SELECT item_id,'warm' AS \"group\",support "
                "FROM warm UNION ALL SELECT item_id,'cold',0 FROM cold"
            )
            paths = {
                "train": _copy(
                    con,
                    "SELECT * FROM final_train ORDER BY parent_session_id,event_pos",
                    seed_dir / "train.parquet",
                ),
                "cold_items": _copy(
                    con, "SELECT * FROM cold ORDER BY item_id", seed_dir / "cold_items.parquet"
                ),
                "incidental_items": _copy(
                    con,
                    "SELECT * FROM incidental ORDER BY item_id",
                    seed_dir / "incidental_items.parquet",
                ),
                "candidates": _copy(
                    con,
                    "SELECT * FROM candidates ORDER BY item_id",
                    seed_dir / "candidates.parquet",
                ),
            }
            coverage = {}
            for split in ("validation", "test"):
                row = con.execute(
                    f"""WITH numbered AS(SELECT *,row_number() OVER(PARTITION BY session_id
                    ORDER BY timestamp_ms,raw_row_index) position FROM {split}_rows),
                    targets AS(SELECT * FROM numbered WHERE position>1)
                    SELECT count(*),count(*) FILTER(WHERE c."group"='warm'),
                    count(*) FILTER(WHERE c."group"='cold'),
                    count(*) FILTER(WHERE c.item_id IS NULL),
                    count(*) FILTER(WHERE i.item_id IS NOT NULL)
                    FROM targets t LEFT JOIN candidates c USING(item_id)
                    LEFT JOIN incidental i USING(item_id)"""
                ).fetchone()
                coverage[split] = dict(
                    zip(
                        (
                            "all_targets",
                            "warm_targets",
                            "cold_targets",
                            "excluded_targets",
                            "incidental_targets",
                        ),
                        map(int, row),
                        strict=True,
                    )
                )
                coverage[split]["primary_target_coverage"] = (
                    (row[1] + row[2]) / row[0] if row[0] else None
                )
            final = _counts(con, "final_train")
            minimum = con.execute("SELECT min(support) FROM warm").fetchone()[0]
            seed_audits.append(
                {
                    "seed": seed,
                    "cold_items": cold_count,
                    "cold_fraction_denominator": size,
                    "selection": "sha256(dataset:seed:item_id), then item_id; first ceil(0.20*U0)",
                    "after_mask_before_short_segment_filter_events": masked_count,
                    "short_segment_events_removed": masked_count - final["events"],
                    "final_train": final,
                    "training_segments": int(
                        con.execute(
                            "SELECT count(DISTINCT session_id) FROM final_train"
                        ).fetchone()[0]
                    ),
                    "warm_items": int(con.execute("SELECT count(*) FROM warm").fetchone()[0]),
                    "incidental_items": int(
                        con.execute("SELECT count(*) FROM incidental").fetchone()[0]
                    ),
                    "postholdout_min_item_support": int(minimum) if minimum is not None else None,
                    "support_recore_after_holdout": False,
                    "coverage": coverage,
                    "paths": paths,
                }
            )
        return {
            "dataset": dataset,
            "protocol": "P0-v2",
            "windows_utc_ms": {
                "train_end_exclusive": validation_start,
                "validation_start_inclusive": validation_start,
                "validation_end_exclusive": test_start,
                "test_start_inclusive": test_start,
                "test_end_exclusive": test_end,
            },
            "temporal_counts": temporal,
            "train_before_filtering": before,
            "train_filter_steps": steps,
            "preholdout_item_universe": size,
            "preholdout_min_item_support": pre_support,
            "preholdout_items_path": universe_path,
            "holdout_paths": holdout_paths,
            "category_metadata_policy": (
                "separate final-train mapper; no future category aggregation"
            ),
            "seeds": seed_audits,
        }
    finally:
        if owned:
            con.close()
