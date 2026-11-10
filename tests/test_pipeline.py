import json
import subprocess
import sys
from pathlib import Path

import pytest

from recommender.smoke import run_fixture


@pytest.mark.smoke
def test_fixture_to_metrics_and_three_seed_report(tmp_path):
    output = tmp_path / "smoke.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "recommender.smoke",
            "--seeds",
            "42",
            "43",
            "44",
            "--output",
            str(output),
        ],
        check=True,
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["kind"] == "synthetic-ci-check-not-research-results"
    assert [run["seed"] for run in report["runs"]] == [42, 43, 44]
    for run in report["runs"]:
        popularity = run["models"]["popularity"]
        assert popularity["warm"]["metrics"]["mrr"] == 0.5
        assert popularity["cold"]["metrics"]["hr"] == 0
        assert popularity["overall"]["n"] == popularity["warm"]["n"] + popularity["cold"]["n"]
    assert report["summary"]["popularity"]["overall"]["hr"] == {"mean": 0.5, "sample_std": 0}
    repeated = run_fixture(
        Path("tests/fixtures/session_dataset.json"), Path("configs/protocol.toml"), [42, 43, 44]
    )
    assert report == repeated
