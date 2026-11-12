"""Require work branches -> personal staging -> dev -> reviewed promotion to main."""

import argparse
import json
import os
import tomllib
from pathlib import Path, PurePosixPath

PERSONAL_BRANCHES = {"bao-long", "ba-chien", "trung-chien"}
WORK_BRANCHES = {
    "bao-long": "baolong-dev",
    "ba-chien": "bachien-dev",
    "trung-chien": "trungchien-dev",
}
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
        portable_path = PurePosixPath(relative)
        path = root / relative
        if (
            portable_path.is_absolute()
            or ".." in portable_path.parts
            or "\\" in relative
            or ":" in relative
            or not path.resolve().is_relative_to(root.resolve())
            or not path.is_file()
            or path.stat().st_size == 0
        ):
            raise ValueError(f"Evidence must be a non-empty file within the repository: {name}")
    protocol = tomllib.loads((root / "configs/protocol.toml").read_text(encoding="utf-8"))
    if protocol["research"]["status"] != "approved" or protocol["research"]["open_decisions"]:
        raise ValueError("Approve the shared protocol and resolve its open decisions first.")


def validate_event(event_name: str, event: dict, repository: str, root: Path) -> None:
    if event_name not in {"pull_request", "pull_request_target"}:
        return
    pr = event["pull_request"]
    if (pr["head"].get("repo") or {}).get("full_name") != repository:
        raise ValueError("Use a branch in this repository for the shared team workflow.")
    source, target = pr["head"]["ref"], pr["base"]["ref"]
    if (
        target == "bao-long"
        and pr.get("user", {}).get("login") == "dependabot[bot]"
        and source.startswith("dependabot/")
    ):
        return
    if target in WORK_BRANCHES:
        if source != WORK_BRANCHES[target]:
            raise ValueError(f"Personal staging {target} only accepts {WORK_BRANCHES[target]}.")
    elif target == "dev":
        if source not in PERSONAL_BRANCHES:
            raise ValueError("PRs into dev must come from bao-long, ba-chien or trung-chien.")
    elif target == "main":
        if source != "dev":
            raise ValueError("Only dev may be promoted to main; send personal work to dev first.")
        validate_research_readiness(root)
    else:
        raise ValueError("The shared workflow targets dev/main or Dependabot staging on bao-long.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-path", type=Path, default=os.environ.get("GITHUB_EVENT_PATH"))
    args = parser.parse_args()
    if args.event_path is None:
        parser.error("--event-path or GITHUB_EVENT_PATH is required")
    event = json.loads(args.event_path.read_text(encoding="utf-8"))
    validate_event(
        os.environ["GITHUB_EVENT_NAME"], event, os.environ["GITHUB_REPOSITORY"], Path.cwd()
    )
    print("Branch policy passed. Research content still requires human review.")


if __name__ == "__main__":
    main()
