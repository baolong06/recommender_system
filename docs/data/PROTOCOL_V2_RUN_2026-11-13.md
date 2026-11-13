# P0 data protocol v2 — full raw rerun, 2026-11-13

Branch: `ba-chien`. Data execution commit: `471458d58378d68e12413f00b77e884f2a512902`.

Both pinned Kaggle v1 raw datasets were downloaded, SHA-256 checked, and processed with the new pipeline. All three seeds passed independent Parquet readback: disjoint session/time windows, no controlled cold items in train, no transitions across removed events, reproducible cold selection and recomputed target coverage.

## Actual output

| Dataset | Neutral events | U0 before cold selection | Controlled cold items / seed | Test sessions | All test targets |
|---|---:|---:|---:|---:|---:|
| diginetica | 1,235,380 | 34,555 | 6,911 | 17,154 | 71,289 |
| yoochoose | 33,003,944 | 36,872 | 7,375 | 479 | 1,452 |

| Dataset | Seed | Final train events | Warm items | Test warm targets | Test cold targets | Excluded targets | Target coverage |
|---|---:|---:|---:|---:|---:|---:|---:|
| diginetica | 42 | 559,881 | 27,642 | 43,184 | 11,215 | 16,890 | 76.3077% |
| diginetica | 43 | 569,213 | 27,639 | 44,040 | 10,357 | 16,892 | 76.3049% |
| diginetica | 44 | 562,041 | 27,641 | 43,448 | 10,951 | 16,890 | 76.3077% |
| yoochoose | 42 | 22,830,238 | 29,493 | 1,138 | 311 | 3 | 99.7934% |
| yoochoose | 43 | 22,811,988 | 29,497 | 1,142 | 307 | 3 | 99.7934% |
| yoochoose | 44 | 23,154,210 | 29,496 | 1,221 | 228 | 3 | 99.7934% |

## Interpretation and limits

- Cold fraction is `ceil(20% × U0)`, with U0 derived only from the filtered train before cold removal. Final warm support may be below 5 because the protocol deliberately does not re-core after the intervention.
- Yoochoose: 137 rows belong to duplicate tuples (69 excess rows); all were retained and flagged. Diginetica: zero duplicate tuples. No invalid raw rows were dropped in either source.
- Yoochoose cold category coverage is 0% for all seeds: cold CatPopularity is **N/A**. Warm category coverage is recorded separately per seed in the manifests.
- Diginetica warm/cold category coverage is 100% for all seeds under the static-catalog-known-at-inference assumption. Historical catalog availability has not been established.
- Yoochoose test is the last UTC calendar day, 2014-09-30: only 479 sessions / 1,452 prediction targets. This is the specified fixed window, but its small size limits statistical confidence. Do not claim benchmark comparability or silently move the cutoff; any alternative window requires a new protocol version.
- Target coverage is the fraction of observed next-item targets inside W ∪ C, not an accuracy score. Excluded targets remain counted; OOV observations retain their prefix positions.
- CatPopularity/model scoring is executed in the Bảo Long handoff on the exact split manifests;
  this file remains the data-run report and does not duplicate those model tables. See
  `docs/category/v2/RESULTS.md`. The repository promotion readiness review records the combined+  technical evidence and preserves the limitations of the model run.

## Reproduction

```bash
python scripts/download_raw.py --help
PYTHONPATH=src python scripts/run_protocol_v2.py --dataset all
```

Use the pinned dependencies and a new empty output directory. See [PROTOCOL_V2.md](https://github.com/baolong06/recommender_system/blob/ba-chien/docs/data/PROTOCOL_V2.md) for full usage. Each published manifest preserves the actual execution commit and source hashes; subsequently added distribution metadata includes runtime, dependency-lock hashes, row counts and schema.

## Packaged files

- `P0_v2_diginetica_all_seeds.zip`: complete Diginetica outputs, all seeds.
- `P0_v2_yoochoose_neutral.zip`: common neutral events and manifest.
- `P0_v2_yoochoose_seed42.zip`, `seed43.zip`, `seed44.zip`: selected seed train/candidate/category files plus common validation/test/U0 and manifest.
- Each ZIP has a `BUNDLE_INVENTORY.json` with payload size and SHA-256. The run manifest covers all outputs; a seed ZIP contains only its documented subset.
- ZIPs use stored compression because Parquet payloads are already Zstandard compressed. Extract Yoochoose bundles into the same dataset directory; shared files are identical. Do not mix datasets.

## Validation

106 Python tests passed, including full miniature end-to-end execution and manifest tamper detection; Ruff passed. The implementation commit CI passed all five jobs. Final publication CI is checked separately.

