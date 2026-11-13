"""Category-priority popularity with separate prefix-only and oracle entry points."""

from collections import Counter


class CategoryPopularity:
    """Use allowed metadata and train event counts; cache ranking by selected category."""

    def __init__(self, counts, candidates, mapping, k=20):
        if type(k) is not int or k < 1:
            raise ValueError("k must be a positive integer")
        if len(candidates) != len(set(candidates)) or set(mapping) != set(candidates):
            raise ValueError("Require unique candidates and exact category mapping")
        if any(not isinstance(value, str) or not value.strip() for value in mapping.values()):
            raise ValueError("Category IDs must be nonempty strings, with UNK for unknown")
        if set(counts) - set(candidates) or any(value < 0 for value in counts.values()):
            raise ValueError("Train counts must be nonnegative and inside candidates")
        self.counts = dict(counts)
        self.mapping = dict(mapping)
        self.k = k
        self.candidates = tuple(sorted(candidates))
        self.popularity = tuple(sorted(candidates, key=lambda i: (-counts.get(i, 0), i)))
        self.categories = {}
        for item in self.popularity:
            category = self.mapping[item]
            if category != "UNK":
                self.categories.setdefault(category, []).append(item)
        self.cache = {}

    def select_category(self, prefix):
        known = [self.mapping.get(item, "UNK") for item in prefix]
        known = [category for category in known if category != "UNK"]
        if not known:
            return None
        counts = Counter(known)
        maximum = max(counts.values())
        return next(category for category in reversed(known) if counts[category] == maximum)

    def _ranking(self, category):
        if category not in self.cache:
            preferred = self.categories.get(category, [])[: self.k]
            seen = set(preferred)
            # All preferred items fit if fewer than K; remaining items retain global order.
            tail = []
            if len(preferred) < self.k:
                for item in self.popularity:
                    if item not in seen:
                        tail.append(item)
                        if len(preferred) + len(tail) == min(self.k, len(self.popularity)):
                            break
            self.cache[category] = tuple(preferred + tail)
        return list(self.cache[category])

    def predict_non_oracle(self, prefix):
        """No target, target category, query object or future events accepted."""
        return self._ranking(self.select_category(prefix))

    def predict_oracle(self, target_category):
        """Privileged category-only interface; unknown target category is unsupported."""
        if target_category is None or target_category == "UNK":
            return None
        if target_category not in self.categories:
            raise ValueError("Oracle category must be from allowed mapping")
        return self._ranking(target_category)
