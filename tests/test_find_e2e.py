"""Whole pipeline with the network replaced by recorded fixtures."""
import json

import pytest

import rg.http as http
from rg import find
from rg.model import Paper
from rg.prf import prf_queries
from rg.queries import extract_queries


@pytest.fixture
def net(monkeypatch, oa_works, s2_search):
    calls = []

    def fake_fetch(url, headers=None, timeout=30.0):
        calls.append(url)
        if "api.openalex.org" in url:
            return 200, {"x-ratelimit-remaining-usd": "0.05"}, json.dumps(oa_works)
        if "api.semanticscholar.org" in url:
            return 200, {}, json.dumps(s2_search)
        raise AssertionError("unexpected host " + url)

    monkeypatch.setattr(http, "fetch", fake_fetch)
    return calls


def test_end_to_end_writes_cards_index_and_results(net, tmp_path):
    out = tmp_path / "cards"
    rc = find.main(["--brief", "examples/tyks-mylab-ward-amr/brief.txt", "--out", str(out), "--cache-dir", str(tmp_path / "c"), "--top", "5"])
    assert rc == 0
    names = sorted(p.name for p in out.glob("*.md"))
    assert "INDEX.md" in names and 2 <= len(names) <= 6
    index = (out / "INDEX.md").read_text()
    assert "Unkel" in index and "Semantic Scholar (3 calls)" in index
    data = json.loads((out / "results.json").read_text())
    unkel = [p for p in data["top"] if "Prospective Detection" in p["title"]]
    assert len(unkel) == 1, "OpenAlex and Semantic Scholar records of the same DOI must merge"
    assert set(unkel[0]["sources"]) == {"openalex", "s2"}
    assert data["meta"]["unique"] < data["meta"]["candidates"]
    assert any("api.semanticscholar.org" in u for u in net) and any("search.semantic" in u for u in net)


def test_results_json_stores_abstract_snippets_only(net, tmp_path, monkeypatch):
    monkeypatch.setattr(find, "ABSTRACT_KEEP", 200)
    out = tmp_path / "cards"
    assert find.main(["--brief", "examples/tyks-mylab-ward-amr/brief.txt", "--out", str(out), "--cache-dir", str(tmp_path / "c"), "--no-prf"]) == 0
    data = json.loads((out / "results.json").read_text())
    abstracts = [p["abstract"] for p in data["top"] + data["candidates"]]
    assert abstracts and max(len(a) for a in abstracts) <= 200 + len(" [...]")
    assert any(a.endswith("[...]") for a in abstracts)
    assert "@" not in json.dumps(data["top"])


def test_second_run_is_served_from_cache(net, tmp_path):
    args = ["--brief", "examples/tyks-mylab-ward-amr/brief.txt", "--out", str(tmp_path / "o"), "--cache-dir", str(tmp_path / "c"), "--no-prf"]
    find.main(args)
    n = len(net)
    find.main(args)
    assert len(net) == n


def test_no_semantic_scholar_flag(net, tmp_path):
    find.main(["--brief", "examples/tyks-mylab-ward-amr/brief.txt", "--out", str(tmp_path / "o"), "--cache-dir", str(tmp_path / "c"), "--no-semantic-scholar"])
    assert not any("semanticscholar" in u for u in net)


def test_dry_run_touches_no_network(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(http, "fetch", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used")))
    assert find.main(["--brief", "examples/if-insurance-home-move/brief.txt", "--dry-run"]) == 0
    err = capsys.readouterr().err
    assert "Query plan" in err and "[semantic]" in err


def test_user_keywords_reach_the_search(net, tmp_path):
    find.main(["--brief", "examples/tyks-mylab-ward-amr/brief.txt", "--keywords", "cumulative antibiogram", "--out", str(tmp_path / "o"),
               "--cache-dir", str(tmp_path / "c"), "--no-semantic-scholar", "--no-prf"])
    assert any("cumulative%20antibiogram" in u for u in net)


def test_empty_brief_is_an_error(tmp_path):
    f = tmp_path / "b.txt"
    f.write_text("   \n")
    assert find.main(["--brief", str(f)]) == 2


def test_all_sources_failing_gives_a_clear_exit_code(monkeypatch, tmp_path):
    monkeypatch.setattr(http, "fetch", lambda *a, **k: (500, {}, "boom"))
    rc = find.main(["--brief", "examples/tyks-mylab-ward-amr/brief.txt", "--out", str(tmp_path / "o"), "--cache-dir", str(tmp_path / "c"), "--no-semantic-scholar"])
    assert rc == 1


def test_anthropic_key_is_not_needed_and_not_used_with_no_llm(net, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    from rg import llm
    monkeypatch.setattr(llm, "post_json", lambda *a, **k: (_ for _ in ()).throw(AssertionError("LLM called despite --no-llm")))
    assert find.main(["--brief", "examples/tyks-mylab-ward-amr/brief.txt", "--out", str(tmp_path / "o"), "--cache-dir", str(tmp_path / "c"),
                      "--no-llm", "--no-semantic-scholar", "--no-prf"]) == 0


# ---------- pseudo-relevance feedback ----------

def _paper(i, abstract):
    p = Paper(title=f"Paper {i} about outbreak detection", abstract=abstract, year=2020)
    return p


def test_prf_finds_recurring_new_bigram_and_skips_generic_ones():
    docs = [_paper(i, "We use residential relocation data and public health records to study relocation timing.") for i in range(6)]
    plan = extract_queries("Home move injury prevention service. Home safety.")
    got = prf_queries(docs, plan, n=2)
    texts = [q.text for q in got]
    assert any("residential relocation" in t or "relocation data" in t or "relocation timing" in t for t in texts)
    assert not any(t == "public health" for t in texts)
    assert all(q.kind == "prf" and q.weight < 1 for q in got)


def test_prf_needs_enough_documents():
    plan = extract_queries("Home move injury prevention service.")
    assert prf_queries([_paper(1, "x y z abstract text here")], plan) == []
