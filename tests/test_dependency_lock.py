import re
import tomllib
from pathlib import Path


def pins(filename):
    content = Path(filename).read_text(encoding="utf-8")
    return dict(re.findall(r"^([\w-]+)==([^\s;\\]+)", content, re.MULTILINE))


def test_build_and_direct_dependencies_match_both_locks():
    build = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["build-system"]
    direct = pins("requirements-dev.in")
    for requirement in build["requires"]:
        name, version = requirement.split("==")
        assert direct[name] == version
    for filename in ["requirements-dev.txt", "requirements-audit.txt"]:
        locked = pins(filename)
        for name, version in direct.items():
            assert locked[name] == version


def test_lock_entries_have_distribution_hashes():
    for filename in ["requirements-dev.txt", "requirements-audit.txt"]:
        content = Path(filename).read_text(encoding="utf-8")
        entries = re.split(r"\n(?=[\w-]+==)", content)
        for entry in entries:
            if re.match(r"[\w-]+==", entry):
                assert re.search(r"--hash=sha256:[a-f0-9]{64}", entry), filename


def test_runtime_dependencies_are_installed_and_locked():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    direct = pins("requirements-dev.in")
    for requirement in project["dependencies"]:
        name, version = requirement.split("==")
        assert direct[name] == version
