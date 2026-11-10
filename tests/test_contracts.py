import pytest

from recommender.contracts import validate_dataset


def test_shared_fixture_has_no_leakage(dataset):
    validate_dataset(dataset, 0.2)


def test_cold_item_in_training_is_rejected(dataset):
    dataset["train"][0].update(item_id="e", category_id="c2")
    with pytest.raises(ValueError, match="cold item leakage"):
        validate_dataset(dataset, 0.2)


def test_session_overlap_is_rejected(dataset):
    dataset["test"][0]["session_id"] = dataset["train"][0]["session_id"]
    with pytest.raises(ValueError, match="session overlap"):
        validate_dataset(dataset, 0.2)


def test_validation_test_overlap_is_rejected(dataset):
    dataset["test"][0]["session_id"] = dataset["validation"][0]["session_id"]
    with pytest.raises(ValueError, match="session overlap"):
        validate_dataset(dataset, 0.2)


def test_unknown_target_is_rejected(dataset):
    dataset["test"][0]["target"] = "unknown"
    with pytest.raises(ValueError, match="missing from catalog"):
        validate_dataset(dataset, 0.2)


def test_unordered_training_history_is_rejected(dataset):
    dataset["train"][0]["timestamp"] = 9
    with pytest.raises(ValueError, match="ordered"):
        validate_dataset(dataset, 0.2)


def test_wrong_category_is_rejected(dataset):
    dataset["train"][0]["category_id"] = "made-up"
    with pytest.raises(ValueError, match="category"):
        validate_dataset(dataset, 0.2)


def test_wrong_cold_fraction_is_rejected(dataset):
    dataset["cold_items"] = ["d", "e"]
    with pytest.raises(ValueError, match="cold fraction"):
        validate_dataset(dataset, 0.2)
