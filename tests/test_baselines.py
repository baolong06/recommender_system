from recommender.baselines import popularity_ranking, random_ranking


def test_popularity_uses_only_training_counts(dataset):
    candidates = list(dataset["catalog"])
    assert popularity_ranking(dataset["train"], candidates) == ["a", "b", "c", "d", "e"]
    dataset["test"] *= 100
    assert popularity_ranking(dataset["train"], candidates) == ["a", "b", "c", "d", "e"]


def test_random_seed_is_reproducible_and_preserves_candidates():
    candidates = ["a", "b", "c", "d", "e"]
    ranking = random_ranking(candidates, 42)
    assert ranking == random_ranking(list(reversed(candidates)), 42)
    assert set(ranking) == set(candidates)
    assert len(ranking) == len(candidates)
    assert candidates == ["a", "b", "c", "d", "e"]
