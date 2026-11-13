"""Create reproducible P0 v2 event/session/item/category statistics and long-tail plots."""

import argparse
import csv
import json
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt


def literal(path):
    return "'" + str(Path(path).resolve()).replace("'", "''") + "'"


def sha256(path):
    import hashlib

    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def dataset_stats(dataset_dir):
    dataset_dir = Path(dataset_dir)
    neutral = dataset_dir / "neutral.parquet"
    manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    with duckdb.connect() as con:
        con.execute("SET threads=2")
        con.execute("SET memory_limit='2GB'")
        relation = f"read_parquet({literal(neutral)})"
        events, sessions, items, categories, duplicate_rows = con.execute(
            f"SELECT count(*), count(DISTINCT session_id), count(DISTINCT item_id), "
            f"count(DISTINCT NULLIF(category_id,'UNK')), count(*) FILTER(WHERE exact_duplicate) "
            f"FROM {relation}"
        ).fetchone()
        lengths = con.execute(
            f"SELECT count(*) n FROM (SELECT session_id,count(*) length "
            f"FROM {relation} GROUP BY session_id)"
        ).fetchone()[0]
        minimum, median, mean, p90, p99, maximum = con.execute(
            f"SELECT min(length), median(length), avg(length), quantile_cont(length, .90), "
            f"quantile_cont(length, .99), max(length) FROM "
            f"(SELECT session_id,count(*) length FROM {relation} GROUP BY session_id)"
        ).fetchone()
        frequencies = con.execute(
            f"SELECT item_id,count(*) frequency FROM {relation} GROUP BY item_id "
            f"ORDER BY frequency DESC,item_id"
        ).fetchall()
    total = sum(row[1] for row in frequencies)
    cumulative = 0
    items_for_80 = 0
    for _rank, (_, frequency) in enumerate(frequencies, start=1):
        items_for_80 = _rank
        cumulative += frequency
        if cumulative >= 0.8 * total:
            break
    top10 = sum(freq for _, freq in frequencies[: max(1, int(len(frequencies) * 0.1))]) / total
    weighted = sum(
        (2 * index - len(frequencies) - 1) * freq
        for index, (_, freq) in enumerate(sorted(frequencies, key=lambda row: row[1]), start=1)
    )
    gini = weighted / (len(frequencies) * total) if total else None
    return {
        "dataset": manifest["dataset"],
        "data_protocol": manifest["protocol_version"],
        "manifest_sha256": sha256(dataset_dir / "manifest.json"),
        "events": int(events),
        "sessions": int(sessions),
        "items": int(items),
        "known_categories": int(categories),
        "flagged_duplicate_rows": int(duplicate_rows),
        "session_length": {
            "n": int(lengths),
            "min": int(minimum),
            "median": float(median),
            "mean": float(mean),
            "p90": float(p90),
            "p99": float(p99),
            "max": int(maximum),
        },
        "item_frequency": {
            "items_for_80_percent": int(items_for_80),
            "fraction_items_for_80_percent": items_for_80 / len(frequencies),
            "top_10_percent_event_share": top10,
            "gini": gini,
            "top_items": [
                {"item_id": item, "frequency": int(freq)} for item, freq in frequencies[:20]
            ],
        },
    }, frequencies


def write_outputs(input_root, output_root):
    output_root = Path(output_root)
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Use a new statistics output directory: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    all_stats, all_frequencies = [], {}
    for dataset in ("diginetica", "yoochoose"):
        stats, frequencies = dataset_stats(Path(input_root) / dataset)
        all_stats.append(stats)
        all_frequencies[dataset] = frequencies
        with (output_root / f"{dataset}_item_frequency.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.writer(handle)
            writer.writerow(["rank", "item_id", "frequency", "cumulative_share"])
            cumulative = 0
            total = sum(row[1] for row in frequencies)
            for rank, (item, frequency) in enumerate(frequencies, start=1):
                cumulative += frequency
                writer.writerow([rank, item, frequency, cumulative / total])
        plt.figure(figsize=(8, 5))
        plt.loglog(range(1, len(frequencies) + 1), [row[1] for row in frequencies], linewidth=1)
        plt.xlabel("Item rank (log scale)")
        plt.ylabel("Event frequency (log scale)")
        plt.title(f"{dataset}: item-frequency long tail")
        plt.grid(True, which="both", alpha=0.25)
        plt.tight_layout()
        plt.savefig(output_root / f"{dataset}_item_long_tail.png", dpi=160)
        plt.close()
    (output_root / "statistics.json").write_text(
        json.dumps({"protocol": "P0-data-v2", "datasets": all_stats}, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    lines = [
        "# P0 v2 data statistics",
        "",
        "Generated by `scripts/describe_protocol_v2.py` from neutral Parquet.",
        "The figures describe neutral data before train-only support filtering "
        "and cold intervention.",
        "",
        "| Dataset | Events | Sessions | Items | Categories | Mean | Median | P90 | P99 | Gini |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for stats in all_stats:
        length = stats["session_length"]
        lines.append(
            f"| {stats['dataset']} | {stats['events']:,} | {stats['sessions']:,} | "
            f"{stats['items']:,} | {stats['known_categories']:,} | {length['mean']:.3f} | "
            f"{length['median']:.1f} | {length['p90']:.1f} | {length['p99']:.1f} | "
            f"{stats['item_frequency']['gini']:.6f} |"
        )
    lines += [
        "",
        "Raw and neutral manifests preserve invalid-row counts, duplicate flags and source hashes.",
        "CSV/PNG figures are descriptive evidence, not model results or acceptance thresholds.",
        "",
    ]
    (output_root / "README.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    write_outputs(args.input_root, args.output_dir)


if __name__ == "__main__":
    main()
