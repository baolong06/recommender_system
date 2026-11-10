"""Require personal branches -> dev -> reviewed research promotion to main."""

import json
import os
import tomllib
from pathlib import Path

PERSONAL_BRANCHES = {"bao-long", "ba-chien", "trung-chien"}
RESEARCH_CHECKS = {
    "data_and_splits_verified",
    "metrics_verified",
    "baselines_complete",
    "three_seed_results_recorded",
    "report_reviewed",
}
EVIDENCE_FILES = {"data_manifest", "split_manifest", "results_manifest", "report"}


def validate_research_readiness(root: Path) -> None:
    readiness = json.loads((root / "docs/research-readiness.json").read_text(encoding="utf-8"))
    if readiness.get("status") != "complete":
        raise ValueError("Research is not complete; keep integrating on dev.")
    checks = readiness.get("checks", {})
    if any(checks.get(check) is not True for check in RESEARCH_CHECKS):
        raise ValueError("Complete all research checks before promoting dev to main.")
    if not isinstance(readiness.get("summary"), str) or not readiness["summary"].strip():
        raise ValueError("Provide a research summary for the reviewer.")
    evidence = readiness.get("evidence", {})
    for name in EVIDENCE_FILES:
        relative = evidence.get(name)
        if not isinstance(relative, str) or not relative.strip():
            raise ValueError(f"Missing evidence file: {name}")
        path = root / relative
        if (
            Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or not path.resolve().is_relative_to(root.resolve())
            or not path.is_file()
            or path.stat().st_size == 0
        ):
            raise ValueError(f"Evidence must be a non-empty file within the repository: {name}")
    protocol = tomllib.loads((root / "configs/protocol.toml").read_text(encoding="utf-8"))
    if protocol["research"]["status"] != "approved" or protocol["research"]["open_decisions"]:
        raise ValueError("Approve the shared protocol and resolve its open decisions first.")


def validate_event(event_name: str, event: dict, repository: str, root: Path) -> None:
    if event_name != "pull_request":
        return
    pr = event["pull_request"]
    if (pr["head"].get("repo") or {}).get("full_name") != repository:
        raise ValueError("Use a branch in this repository for the shared team workflow.")
    source, target = pr["head"]["ref"], pr["base"]["ref"]
    if target == "dev":
        if source not in PERSONAL_BRANCHES:
            raise ValueError("PRs into dev must come from bao-long, ba-chien or trung-chien.")
    elif target == "main":
        if source != "dev":
            raise ValueError("Only dev may be promoted to main; send personal work to dev first.")
        validate_research_readiness(root)
    else:
        raise ValueError("The shared workflow targets dev or main.")


def main() -> None:
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    validate_event(
        os.environ["GITHUB_EVENT_NAME"], event, os.environ["GITHUB_REPOSITORY"], Path.cwd()
    )
    print("Branch policy passed. Research content still requires human review.")


if __name__ == "__main__":
    main()
