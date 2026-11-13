import pandas as pd
import pytest

from recommender.data.category_v2 import fit_category_mapping


def fixture(tmp_path, train, candidates=None):
    train_path = tmp_path / "train.parquet"
    candidates_path = tmp_path / "candidates.parquet"
    pd.DataFrame(train).to_parquet(train_path)
    pd.DataFrame(candidates or {"item_id": ["A", "C"], "group": ["warm", "cold"]}).to_parquet(
        candidates_path
    )
    return train_path, candidates_path


def test_yoochoose_fits_only_final_train_genuine_context_numeric_tie(tmp_path):
    train, candidates = fixture(
        tmp_path,
        {"item_id": ["A"] * 8, "raw_context": ["S", "0", "12345678", "01", "10", "2", "10", "2"]},
    )
    out = tmp_path / "mapping.parquet"
    audit = fit_category_mapping(train, candidates, "yoochoose", out)
    assert pd.read_parquet(out).set_index("item_id").category_id.to_dict() == {"A": "2", "C": "UNK"}
    assert audit["coverage"]["cold"]["known"] == 0
    assert audit["cold_catpop_status"] == "N/A"
    assert audit["heldout_interactions_read"] is False


def test_cold_present_in_train_is_rejected(tmp_path):
    train, candidates = fixture(tmp_path, {"item_id": ["C"], "raw_context": ["1"]})
    with pytest.raises(ValueError, match="leaked"):
        fit_category_mapping(train, candidates, "yoochoose", tmp_path / "out.parquet")


def test_diginetica_cold_can_use_static_catalog_only(tmp_path):
    train, candidates = fixture(tmp_path, {"item_id": ["A"]})
    catalog = tmp_path / "catalog.csv"
    catalog.write_text("itemId;categoryId\nA;2\nC;3\nC;3\n")
    out = tmp_path / "out.parquet"
    audit = fit_category_mapping(train, candidates, "diginetica", out, catalog)
    assert pd.read_parquet(out).set_index("item_id").category_id.to_dict() == {"A": "2", "C": "3"}
    assert audit["coverage"]["cold"]["known"] == 1
    assert audit["identical_catalog_duplicates_collapsed"] == 1
    assert audit["historical_catalog_availability_verified"] is False


def test_static_catalog_conflict_is_rejected(tmp_path):
    train, candidates = fixture(tmp_path, {"item_id": ["A"]})
    catalog = tmp_path / "catalog.csv"
    catalog.write_text("itemId;categoryId\nA;2\nA;3\n")
    with pytest.raises(ValueError, match="conflicting"):
        fit_category_mapping(train, candidates, "diginetica", tmp_path / "out.parquet", catalog)


@pytest.mark.parametrize("groups", [["warm", "bad"], ["warm", None]])
def test_invalid_candidate_groups_are_rejected(tmp_path, groups):
    train, candidates = fixture(
        tmp_path, {"item_id": ["A"], "raw_context": ["1"]}, {"item_id": ["A", "C"], "group": groups}
    )
    with pytest.raises(ValueError, match="Candidate"):
        fit_category_mapping(train, candidates, "yoochoose", tmp_path / "out.parquet")


def test_duplicate_candidate_ids_are_rejected(tmp_path):
    train, candidates = fixture(
        tmp_path,
        {"item_id": ["A"], "raw_context": ["1"]},
        {"item_id": ["A", "A"], "group": ["warm", "cold"]},
    )
    with pytest.raises(ValueError, match="Candidate"):
        fit_category_mapping(train, candidates, "yoochoose", tmp_path / "out.parquet")
