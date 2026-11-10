import pytest

from recommender.evaluation import evaluate_groups


def test_groups_use_target_not_history():
    examples = [
        {"history": ["cold"], "target": "warm"},
        {"history": ["warm"], "target": "cold"},
    ]
    result = evaluate_groups(examples, [["warm"], ["warm"]], {"cold"}, 1)
    assert result["warm"] == {"n": 1, "metrics": {"hr": 1, "mrr": 1, "ndcg": 1}}
    assert result["cold"] == {"n": 1, "metrics": {"hr": 0, "mrr": 0, "ndcg": 0}}
    assert result["overall"] == {"n": 2, "metrics": {"hr": 0.5, "mrr": 0.5, "ndcg": 0.5}}


def test_empty_group_is_unavailable_rather_than_zero():
    result = evaluate_groups([{"target": "a"}], [["a"]], set(), 1)
    assert result["cold"] == {"n": 0, "metrics": {"hr": None, "mrr": None, "ndcg": None}}


def test_missing_prediction_is_rejected():
    with pytest.raises(ValueError, match="each example"):
        evaluate_groups([{"target": "a"}], [], set(), 1)
