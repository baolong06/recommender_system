import hashlib
import json
import runpy
from pathlib import Path

import pyarrow.parquet as pq
import pytest

ROOT = Path(__file__).resolve().parents[1]


def runner():
    return runpy.run_path(str(ROOT / "scripts/run_protocol_v2.py"))


def test_cli_end_to_end_keeps_duplicate_events_and_emits_portable_verified_manifest(tmp_path):
    raw = tmp_path / "raw" / "yoochoose"
    raw.mkdir(parents=True)
    lines = []
    for sid in range(10):
        for event, item in enumerate(["1", "2", "3", "4", "5"] * 2):
            lines.append(f"{sid},2020-01-01T00:00:00.{event:03d}Z,{item},{item}\n")
    lines.append(lines[0])
    for sid, day in [("v", 29), ("t", 30)]:
        for event, item in enumerate(["1", "2", "3", "4", "5"]):
            lines.append(f"{sid},2020-01-{day:02d}T00:00:00.{event:03d}Z,{item},S\n")
    (raw / "yoochoose-clicks.dat").write_text("".join(lines))
    output = tmp_path / "out"
    main = runner()["main"]
    assert (
        main(
            [
                "--dataset",
                "yoochoose",
                "--config",
                str(ROOT / "configs/data_v2.toml"),
                "--raw-dir",
                str(tmp_path / "raw"),
                "--output-dir",
                str(output),
                "--batch-size",
                "7",
            ]
        )
        == 0
    )
    manifest = json.loads((output / "yoochoose/manifest.json").read_text())
    assert manifest["verification"]["verified_seeds"] == [42, 43, 44]
    assert manifest["verification"]["neutral_rows"] == 111
    assert manifest["duplicate_flags"]["flagged_rows"] == 2
    assert manifest["duplicate_flags"]["duplicate_tuple_excess_rows"] == 1
    assert manifest["normalization_before_duplicate_flag"]["valid_rows"] == 111
    assert all(a["cold_catpop_status"] == "N/A" for a in manifest["category_audits"])
    assert not any(Path(f["path"]).is_absolute() for f in manifest["files"])
    for f in manifest["files"]:
        path = output / "yoochoose" / f["path"]
        assert path.stat().st_size == f["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == f["sha256"]
    neutral = pq.read_table(output / "yoochoose/neutral.parquet")
    assert neutral.num_rows == 111
    with pytest.raises(FileExistsError, match="preserve"):
        main(
            [
                "--dataset",
                "yoochoose",
                "--config",
                str(ROOT / "configs/data_v2.toml"),
                "--raw-dir",
                str(tmp_path / "raw"),
                "--output-dir",
                str(output),
            ]
        )


def test_config_changes_cannot_silently_change_protocol(tmp_path):
    config = tmp_path / "bad.toml"
    config.write_text(
        (ROOT / "configs/data_v2.toml")
        .read_text()
        .replace("min_item_support = 5", "min_item_support = 4")
    )
    with pytest.raises(SystemExit):
        runner()["main"](["--config", str(config)])
