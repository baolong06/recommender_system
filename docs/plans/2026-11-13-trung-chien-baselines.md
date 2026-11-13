# Trung Chiến — split acceptance and baseline execution

Use the P0-data-v2 implementation merged into dev by PR #3. Preserve the fixed temporal
windows, train-only support filtering, segmentation, SHA-256 controlled cold selection
ceil(20% of U0), candidates W union C, and OOV prefix positions. Reuse the handed-off
split builder and metrics rather than maintain a second split algorithm.

Input acceptance verifies payload SHA-256, all seeds, actual train item counts, cold
selection and absence from train, candidates/support, session/time disjointness,
segment continuity, and evaluation coverage. A local rerun is compared to the dev
handoff counts/windows; different Parquet encodings receive different split IDs.

Primary cutoff is K=20, selected from the existing v2 proposal before scoring test.
Popularity counts only the final training events, sorting descending count and then
ascending string item ID. Previously seen items remain candidates. Random samples an
ordered top-K uniformly without replacement from sorted candidates. Each query gets a
SHA-256-derived RNG seed including dataset, split seed, model seed, evaluation window,
session ID and source row. Predictions never read the target/category or future suffix.

Run all three split seeds and, for Random, all three model seeds per split. Popularity
is deterministic, so report one run per split with model_seed null. Score both validation
and test without refitting or selecting a model from test. Use shared HR/MRR/NDCG and
report overall/warm/controlled-cold sample counts; empty groups have null metrics.
Excluded I0/natural-unseen targets remain counted in coverage and keep prefix positions.

Publish per-run CSV/JSON, model-seed mean/sample std for each fixed split, and mean/sample
std across the three split means. Nine Random runs are not nine independent splits.
Provide hashed split manifests, a download bundle and commands for Bao Long to reuse
the same files. Do not mark report review, CatPopularity, or research promotion complete.
