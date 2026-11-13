"""Fit category metadata from allowed inputs only; never derive Yoochoose cold labels."""

import os
import uuid
from pathlib import Path

import duckdb
import pyarrow as pa

from recommender.data.neutral import read_catalog


def _literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def fit_category_mapping(
    train_parquet,
    candidates_parquet,
    dataset,
    output_path,
    static_catalog_path=None,
    connection=None,
):
    if dataset not in {"yoochoose", "diginetica"}:
        raise ValueError("Unknown dataset")
    output_path = Path(output_path)
    inputs = [Path(train_parquet), Path(candidates_parquet)]
    if static_catalog_path is not None:
        inputs.append(Path(static_catalog_path))
    if output_path.resolve() in {p.resolve() for p in inputs}:
        raise ValueError("Output cannot replace input data")
    if output_path.exists():
        raise FileExistsError(output_path)
    owned = connection is None
    con = connection or duckdb.connect()
    if owned:
        con.execute("SET memory_limit='2GB'")
        con.execute("SET threads=2")
    prefix = "category_" + uuid.uuid4().hex
    candidates, train, mapping = (prefix + suffix for suffix in ["_c", "_t", "_m"])
    created = []
    registered = None
    temporary = None
    duplicates = 0
    try:
        con.execute(
            f"CREATE TEMP TABLE {candidates} AS SELECT * "
            f"FROM read_parquet({_literal(candidates_parquet)})"
        )
        created.append(candidates)
        columns = {row[0] for row in con.execute(f"DESCRIBE {candidates}").fetchall()}
        if not {"item_id", "group"}.issubset(columns):
            raise ValueError("Candidates require item_id and group")
        invalid = con.execute(
            f"SELECT count(*) FROM {candidates} WHERE item_id IS NULL "
            "OR trim(item_id)='' OR \"group\" IS NULL "
            "OR \"group\" NOT IN ('warm','cold')"
        ).fetchall()[0][0]
        n, unique = con.execute(
            f"SELECT count(*),count(DISTINCT item_id) FROM {candidates}"
        ).fetchall()[0]
        if invalid or n != unique:
            raise ValueError("Candidate IDs must be unique and groups warm/cold")
        con.execute(
            f"CREATE TEMP TABLE {train} AS SELECT item_id"
            f"{',raw_context' if dataset == 'yoochoose' else ''} "
            f"FROM read_parquet({_literal(train_parquet)})"
        )
        created.append(train)
        if con.execute(
            f"SELECT count(*) FROM {train} t JOIN {candidates} c USING(item_id) "
            "WHERE c.\"group\"='cold'"
        ).fetchall()[0][0]:
            raise ValueError("Controlled cold item leaked into final train")
        if dataset == "yoochoose":
            con.execute(f"""CREATE TEMP TABLE {mapping} AS
                WITH counts AS (SELECT item_id,raw_context AS category_id,count(*) n
                FROM {train} WHERE raw_context IN
                ('1','2','3','4','5','6','7','8','9','10','11','12')
                GROUP BY item_id,raw_context), ranked AS (SELECT *,row_number() OVER
                (PARTITION BY item_id ORDER BY n DESC,cast(category_id AS INTEGER)) r FROM counts)
                SELECT item_id,category_id FROM ranked WHERE r=1""")
        else:
            if static_catalog_path is None:
                raise ValueError("Diginetica requires static catalog")
            catalog, duplicates = read_catalog(static_catalog_path)
            registered = prefix + "_raw"
            con.register(registered, pa.Table.from_pandas(catalog, preserve_index=False))
            con.execute(
                f"CREATE TEMP TABLE {mapping} AS SELECT itemId AS item_id,"
                f"categoryId AS category_id FROM {registered}"
            )
        created.append(mapping)
        query = (
            f"SELECT c.item_id,coalesce(m.category_id,'UNK') AS category_id,c.\"group\" "
            f"FROM {candidates} c LEFT JOIN {mapping} m USING(item_id)"
        )
        coverage = {
            g: {"n": 0, "known": 0, "unknown": 0, "fraction_known": None} for g in ["warm", "cold"]
        }
        for group, n, known in con.execute(
            "SELECT \"group\",count(*),count(*) FILTER(WHERE category_id<>'UNK') "
            f'FROM ({query}) GROUP BY "group"'
        ).fetchall():
            coverage[group] = {
                "n": n,
                "known": known,
                "unknown": n - known,
                "fraction_known": known / n if n else None,
            }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_name(output_path.name + "." + uuid.uuid4().hex + ".partial")
        con.execute(
            f"COPY (SELECT item_id,category_id FROM ({query}) ORDER BY item_id) "
            f"TO {_literal(temporary)} (FORMAT PARQUET,COMPRESSION ZSTD)"
        )
        os.link(temporary, output_path)
        temporary.unlink()
        has_cold = dataset == "diginetica" and coverage["cold"]["known"] > 0
        return {
            "dataset": dataset,
            "mapping_path": str(output_path),
            "coverage": coverage,
            "metadata_policy": "final-train-only-genuine-context"
            if dataset == "yoochoose"
            else "static-catalog-known-at-inference-assumption",
            "cold_category_available": has_cold,
            "cold_catpop_status": "available" if has_cold else "N/A",
            "identical_catalog_duplicates_collapsed": duplicates,
            "heldout_interactions_read": False,
            "oracle_target_access": False,
            "oracle_scorer_implemented": False,
            "historical_catalog_availability_verified": False,
        }
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        for table in reversed(created):
            con.execute(f"DROP TABLE IF EXISTS {table}")
        if registered is not None:
            con.unregister(registered)
        if owned:
            con.close()
