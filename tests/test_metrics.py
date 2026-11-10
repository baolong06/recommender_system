import pytest

from recommender.metrics import ranking_metrics


@pytest.mark.parametrize(
    "ranking,target,k,expected",
    [
        (["a", "b", "c"], "a", 3, {"hr": 1, "mrr": 1, "ndcg": 1}),
        (["a", "b", "c"], "c", 3, {"hr": 1, "mrr": 1 / 3, "ndcg": 0.5}),
        (["a", "b", "c"], "c", 2, {"hr": 0, "mrr": 0, "ndcg": 0}),
        ([], "c", 20, {"hr": 0, "mrr": 0, "ndcg": 0}),
        (["a"], "c", 20, {"hr": 0, "mrr": 0, "ndcg": 0}),
    ],
)
def test_hand_calculated_metrics(ranking, target, k, expected):
    assert ranking_metrics(ranking, target, k) == pytest.approx(expected)


def test_duplicate_recommendations_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        ranking_metrics(["a", "a"], "a", 2)


def test_non_positive_cutoff_is_rejected():
    with pytest.raises(ValueError, match="positive"):
        ranking_metrics(["a"], "a", 0)
