import hashlib
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def loader(tmp_path):
    module = runpy.run_path(str(ROOT / "scripts/download_raw.py"))
    source = tmp_path / "cache"
    source.mkdir()
    (source / "clicks.dat").write_bytes(b"raw-event\n")
    expected = hashlib.sha256(b"raw-event\n").hexdigest()
    module["SOURCES"].clear()
    module["SOURCES"]["demo"] = ("owner/demo/versions/1", {"clicks.dat": expected})
    return module, source


def test_download_verifies_and_reuses_without_network(tmp_path):
    module, source = loader(tmp_path)
    calls = []
    result = module["fetch_raw"]("demo", tmp_path / "raw", lambda h: calls.append(h) or source)
    assert (result / "clicks.dat").read_bytes() == b"raw-event\n"
    assert calls == ["owner/demo/versions/1"]
    module["fetch_raw"]("demo", tmp_path / "raw", lambda _: pytest.fail("must reuse input"))


def test_wrong_download_hash_never_becomes_raw_input(tmp_path):
    module, source = loader(tmp_path)
    (source / "clicks.dat").write_bytes(b"different version")
    with pytest.raises(ValueError, match="checksum"):
        module["fetch_raw"]("demo", tmp_path / "raw", lambda _: source)
    assert not (tmp_path / "raw/demo/clicks.dat").exists()


def test_wrong_existing_file_is_preserved(tmp_path):
    module, source = loader(tmp_path)
    destination = tmp_path / "raw/demo"
    destination.mkdir(parents=True)
    target = destination / "clicks.dat"
    target.write_bytes(b"existing-unrelated-data")
    with pytest.raises(ValueError, match="Existing raw checksum"):
        module["fetch_raw"]("demo", tmp_path / "raw", lambda _: source)
    assert target.read_bytes() == b"existing-unrelated-data"
