"""Validate the small, already-split interchange fixture used by CI."""

from math import ceil


def validate_dataset(dataset: dict, cold_fraction: float) -> None:
    if not 0 < cold_fraction < 1:
        raise ValueError("cold fraction must be between zero and one")
    catalog = dataset["catalog"]
    cold = dataset["cold_items"]
    if not catalog or not all(isinstance(item, str) and item for item in catalog):
        raise ValueError("catalog must contain non-empty string item IDs")
    if any(not isinstance(category, str) or not category for category in catalog.values()):
        raise ValueError("category IDs must be non-empty strings")
    if len(cold) != len(set(cold)) or not set(cold) <= catalog.keys():
        raise ValueError("cold items must be unique catalog items")
    if len(cold) != ceil(len(catalog) * cold_fraction):
        raise ValueError("fixture cold fraction must use ceil(catalog size * fraction)")

    train = dataset["train"]
    if not train:
        raise ValueError("train must not be empty")
    sessions = set()
    last_timestamp = {}
    for event in train:
        session, item = event["session_id"], event["item_id"]
        timestamp = event["timestamp"]
        if not isinstance(session, str) or not session:
            raise ValueError("session IDs must be non-empty strings")
        if type(timestamp) is not int or timestamp < 0:
            raise ValueError("timestamps must be non-negative integer Unix seconds")
        if item not in catalog or event["category_id"] != catalog[item]:
            raise ValueError("train item/category does not match catalog")
        if item in cold:
            raise ValueError("cold item leakage in train")
        if session in last_timestamp and timestamp < last_timestamp[session]:
            raise ValueError("events must be ordered within each session")
        last_timestamp[session] = timestamp
        sessions.add(session)

    for split in ["validation", "test"]:
        if not dataset[split]:
            raise ValueError(f"{split} must not be empty")
        for example in dataset[split]:
            session = example["session_id"]
            if not isinstance(session, str) or not session:
                raise ValueError("session IDs must be non-empty strings")
            if session in sessions:
                raise ValueError("session overlap across splits or duplicate evaluation session")
            sessions.add(session)
            history = example["history"]
            if not isinstance(history, list) or not history:
                raise ValueError("evaluation history must be a non-empty list")
            if any(item not in catalog for item in [*history, example["target"]]):
                raise ValueError("evaluation item missing from catalog")
