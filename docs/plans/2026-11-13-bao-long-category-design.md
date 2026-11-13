# Bảo Long — category baseline design selected before scoring

Build on the exact Trung Chiến split delivery (three split seeds 42/43/44, K=20,
W union C candidates and unchanged holdouts). Do not tune cutoffs, formula, tie-break
or seeds against test. This implementation choice does not imply human protocol approval.

Cat-Popularity selects one category and ranks every candidate by the tuple
`(-int(item_category == selected_category), -final_train_event_count, item_id)`.
Thus selected-category items come first; their order is train popularity with string
ID tie-break. Fill remaining top-K with the same global popularity ordering. Unknown
candidate category is never a selected category. Candidate membership never changes.
No pseudo-counts, embeddings or artificial cold vectors are introduced.

Non-oracle selects the modal known category among observed prefix items; ties choose
the category with the latest occurrence. Unknown/OOV prefix positions stay present but
do not vote. An entirely unknown prefix falls back to global popularity. Predictors
receive only the prefix, never target ID/category or the future suffix.

Oracle receives only the target category looked up from the allowed seed mapping,
not the target ID. Unknown target category is unsupported, not a miss. Oracle access is
privileged and is not a deployable prediction or a guaranteed accuracy upper bound.

Yoochoose maps categories solely from final-train genuine contexts 1..12. All cold
categories are unknown; primary Cat-Popularity cold is N/A in both modes. Non-oracle
still scores all warm targets, using fallback when needed. Oracle scores only targets
with known category. Diginetica uses the handed-off static catalog assumption. Verify
the mapping against allowed raw catalog/final train before model fit.

Report target-based overall/warm/cold with n_eligible, n_scored, support fraction,
unsupported reasons and null metrics when n_scored=0. Overall with incomplete support
is explicitly partial and cannot be compared to a full-cohort baseline. Therefore
also score Random/Popularity on each Cat model's supported query cohort, keeping the
same query RNG and rankings as Trung Chiến. Publish paired metric differences on those
matched cohorts; do not treat the oracle/non-oracle cohorts as interchangeable.

Fit once per split. Rerun Random/Popularity and compare every published row with the
Trung Chiến result snapshot. Aggregate model seeds within a split, then three split
means with sample std ddof=1. Describe low, zero and N/A values as observed; do not
claim that knowing category must improve cold item ranking. Deliver code, tests,
full runs, coverage/fallback counts, provenance and a descriptive research report.
