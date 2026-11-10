import json

import pytest

from recommender.branch_policy import validate_event

REPOSITORY = "baolong06/recommender_system"


def pull_request(source, target, repository=REPOSITORY):
    return {
        "pull_request": {
            "head": {"ref": source, "repo": {"full_name": repository}},
            "base": {"ref": target},
        }
    }


@pytest.mark.parametrize("source", ["bao-long", "ba-chien", "trung-chien"])
def test_personal_work_targets_dev(source, tmp_path):
    validate_event("pull_request", pull_request(source, "dev"), REPOSITORY, tmp_path)


@pytest.mark.parametrize("source", ["bao-long", "ba-chien", "trung-chien"])
def test_personal_work_cannot_skip_dev(source, tmp_path):
    with pytest.raises(ValueError, match="Only dev"):
        validate_event("pull_request", pull_request(source, "main"), REPOSITORY, tmp_path)


def test_same_named_branch_in_fork_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="this repository"):
        validate_event(
            "pull_request", pull_request("dev", "main", "someone/fork"), REPOSITORY, tmp_path
        )


def test_unapproved_source_cannot_target_dev(tmp_path):
    with pytest.raises(ValueError, match="PRs into dev"):
        validate_event("pull_request", pull_request("other", "dev"), REPOSITORY, tmp_path)


@pytest.fixture
def research_tree(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "configs").mkdir()
    checks = {
        "data_and_splits_verified": True,
        "metrics_verified": True,
        "baselines_complete": True,
        "three_seed_results_recorded": True,
        "report_reviewed": True,
    }
    readiness = {"status": "complete", "summary": "Ready for human review", "checks": checks}
    readiness["evidence"] = {}
    for name in ["data_manifest", "split_manifest", "results_manifest", "report"]:
        path = f"docs/{name}.md"
        (tmp_path / path).write_text("Evidence contents reviewed separately", encoding="utf-8")
        readiness["evidence"][name] = path
    (tmp_path / "docs/research-readiness.json").write_text(json.dumps(readiness), encoding="utf-8")
    (tmp_path / "configs/protocol.toml").write_text(
        '[research]\nstatus = "approved"\nopen_decisions = []\n', encoding="utf-8"
    )
    return tmp_path, readiness


def test_incomplete_research_blocks_main(research_tree):
    root, readiness = research_tree
    readiness["status"] = "in_progress"
    (root / "docs/research-readiness.json").write_text(json.dumps(readiness), encoding="utf-8")
    with pytest.raises(ValueError, match="not complete"):
        validate_event("pull_request", pull_request("dev", "main"), REPOSITORY, root)


def test_complete_evidence_allows_promotion_to_be_reviewed(research_tree):
    root, _ = research_tree
    validate_event("pull_request", pull_request("dev", "main"), REPOSITORY, root)


def test_missing_evidence_blocks_main(research_tree):
    root, _ = research_tree
    (root / "docs/results_manifest.md").unlink()
    with pytest.raises(ValueError, match="Evidence"):
        validate_event("pull_request", pull_request("dev", "main"), REPOSITORY, root)


def test_unresolved_protocol_blocks_main(research_tree):
    root, _ = research_tree
    (root / "configs/protocol.toml").write_text(
        '[research]\nstatus = "pending-team-agreement"\nopen_decisions = ["candidate set"]\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="protocol"):
        validate_event("pull_request", pull_request("dev", "main"), REPOSITORY, root)


def test_push_on_dev_does_not_require_finished_research(tmp_path):
    validate_event("push", {}, REPOSITORY, tmp_path)
