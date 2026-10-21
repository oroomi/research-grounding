import json
import pathlib

import pytest

FIX = pathlib.Path(__file__).parent / "fixtures"
ROOT = FIX.parent.parent


@pytest.fixture
def oa_works():
    return json.loads((FIX / "openalex_works.json").read_text())


@pytest.fixture
def s2_search():
    return json.loads((FIX / "s2_search.json").read_text())


@pytest.fixture
def brief_amr():
    return (ROOT / "examples/tyks-mylab-ward-amr/brief.txt").read_text()


@pytest.fixture
def brief_if():
    return (ROOT / "examples/if-insurance-home-move/brief.txt").read_text()


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "RG_MAILTO", "RG_OPENALEX_KEY", "OPENALEX_API_KEY", "S2_API_KEY", "SEMANTIC_SCHOLAR_API_KEY", "RG_MODEL"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture(autouse=True)
def run_from_repo_root(monkeypatch):
    """Several tests read examples/ by relative path, as a user running from a clone would."""
    monkeypatch.chdir(ROOT)
