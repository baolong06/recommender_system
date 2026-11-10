import json
from pathlib import Path

import pytest


@pytest.fixture
def dataset():
    path = Path(__file__).parent / "fixtures" / "session_dataset.json"
    return json.loads(path.read_text(encoding="utf-8"))
