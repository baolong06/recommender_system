# P0 v2 promotion readiness review

Date: 2026-11-13 (Asia/Saigon)

This review records the technical evidence requested by the project owner before promoting
the integrated `dev` branch to `main`. It checks the repository's promotion contract against
the executed artifacts. It does not claim external peer review, supervisor sign-off or
statistical significance; those are documented limitations of the research result.

## Scope and evidence

The integrated head contains the three contributions: Bá Chiến's P0-data-v2 pipeline,
Trung Chiến's exact split and Random/Popularity baseline handoff, and Bảo Long's
group-wise/Cat-Popularity experiment. The input source hashes and output manifests are:

- data statistics: [P0 v2 statistics](../data/protocol_v2_stats/README.md), generated from
  neutral Parquet by `scripts/describe_protocol_v2.py`;
- split evidence: [split delivery](../splits/v2/delivery.json) and [split results](../splits/v2/RESULTS.md);
- model evidence: [category manifest](../category/v2/manifest.json), [category results](../category/v2/RESULTS.md),
  and [independent check](../category/v2/independent_check.json).

The publication artifacts preserve source/config/dependency hashes. The full data payloads
remain in the versioned Releases and are downloaded by their checksum-verifying scripts.

## Acceptance checks

| Check | Evidence | Result |
| --- | --- | --- |
| Data and splits verified | raw SHA-256, neutral manifests, three seed split audits | PASS |
| Shared metric verified | 122 Python tests, including hand-calculated HR/MRR/NDCG and group metrics | PASS |
| Baselines complete | 144 Random/Popularity rows; independent reproduction of all 144 | PASS |
| Three seeds recorded | split seeds 42/43/44 and Random model seeds 42/43/44 | PASS |
| Category experiment complete | 504 rows, oracle/non-oracle, matched cohorts, coverage and N/A reasons | PASS |
| Technical report reviewed | this review plus independent analytical checker at 1e-12 tolerance | PASS |
| Quality gates | quality, unit-tests, pipeline-smoke, dependency-audit and branch-policy on integrated dev head | PASS |

## Resolved protocol decisions

The decisions previously listed as open are now recorded in `configs/protocol.toml` and
implemented by `configs/data_v2.toml`, `configs/baselines_v2.toml`, `configs/category_v2.toml`
and their runners. They are: U0 and `ceil(20% * |U0|)`, UTC whole-session windows,
train-only stabilization before cold intervention, W union C candidates, previously seen
items retained, deterministic popularity/category tie-breaks, three split/model seeds,
K=20, prefix-only non-oracle, privileged target-category oracle and explicit N/A support.

The protocol is approved for repository integration because these rules are implemented,
executed and reproduced. Changing a rule requires a new protocol/data/result version; it
must not edit the existing counts or checksums in place.

## Limitations retained in the report

Yoochoose's last-day test window contains 479 sessions and 1,452 observed targets; its
cold category coverage is N/A without an independent catalog. Diginetica primary target
coverage is about 76.3%, and its static catalog availability is an explicit assumption.
Oracle category access is privileged and not deployable. The result tables describe
observed behavior and do not recommend a production model or claim external benchmark
comparability.

The project owner requested promotion after this technical review. Academic/supervisor
approval is a separate human decision and remains visible in these limitations; the
repository gate records technical completion for this release.

## Promotion decision

`docs/research-readiness.json` is set to `complete`; all required checks are true; the
evidence paths are small, repository-relative, non-empty files; and `configs/protocol.toml`
has `research.status = "approved"` with no open decisions. The `dev -> main` policy
preflight should therefore pass on the exact head associated with this review.
