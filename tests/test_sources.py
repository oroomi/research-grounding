import json

import pytest

import rg.http as http
from rg.http import Cache, HttpError, RateLimited, cache_key, get_json
from rg.sources import OpenAlex, SemanticScholar, parse_openalex_work, parse_s2_paper, year_range


# ---------- parsers on recorded fixtures ----------

def test_parse_openalex_work_fields(oa_works):
    papers = [parse_openalex_work(w) for w in oa_works["results"]]
    unkel = next(p for p in papers if "Prospective Detection" in p.title)
    assert unkel.doi == "10.1111/j.1467-985x.2011.00714.x"  # normalised: no URL prefix, lower case
    assert unkel.link == "https://doi.org/10.1111/j.1467-985x.2011.00714.x"
    assert unkel.year == 2011 and unkel.cited_by > 100
    assert unkel.authors[0] == "Steffen Unkel"
    assert unkel.abstract.startswith(("Many", "The", "In", "A")) or len(unkel.abstract) > 200
    assert unkel.sources == {"openalex"} and unkel.ids["openalex"].startswith("W")
    assert unkel.raw_score is not None


def test_parse_openalex_oa_url_only_when_open(oa_works):
    papers = [parse_openalex_work(w) for w in oa_works["results"]]
    closed = next(p for p in papers if "Prospective Detection" in p.title)  # recorded with is_oa false
    opened = next(p for p in papers if p.title.startswith("Confidence"))
    assert closed.oa_url == ""
    assert opened.oa_url.startswith("http")


def test_parse_openalex_drops_retracted_and_untitled():
    assert parse_openalex_work({"title": "x", "is_retracted": True}) is None
    assert parse_openalex_work({"title": "", "display_name": ""}) is None


def test_parse_s2_paper(s2_search):
    ps = [parse_s2_paper(x) for x in s2_search["data"]]
    assert ps[2] is None  # no title
    a, b = ps[0], ps[1]
    assert a.doi == "10.1111/j.1467-985x.2011.00714.x"  # upper-case DOI normalised so it dedupes against OpenAlex
    assert a.kind == "review" and a.tldr.startswith("Reviews")
    assert b.abstract == "" and b.oa_url == "https://example.org/antibiogram.pdf" and b.doi == "" and b.authors == ["Priya Rao"]


def test_year_range():
    assert year_range("2010-2026") == (2010, 2026)
    assert year_range("2026:2010") == (2010, 2026)
    assert year_range(None) is None
    with pytest.raises(ValueError):
        year_range("recent")


# ---------- http: cache, backoff, secrets ----------

class FakeFetch:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, url, headers=None, timeout=30.0):
        self.calls.append((url, dict(headers or {})))
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]


def ok(data, hdrs=None):
    return 200, hdrs or {}, json.dumps(data)


def test_get_json_retries_429_then_succeeds(monkeypatch):
    f = FakeFetch((429, {}, "slow down"), (429, {"retry-after": "2"}, ""), ok({"a": 1}))
    monkeypatch.setattr(http, "fetch", f)
    slept = []
    data, cached, _ = get_json("https://x.test/a", {"q": "1"}, sleep=slept.append, source="t")
    assert data == {"a": 1} and not cached and len(f.calls) == 3
    assert len(slept) == 2 and 2.0 <= slept[1] <= 2.6  # honours Retry-After


def test_get_json_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(http, "fetch", FakeFetch((429, {}, "")))
    with pytest.raises(RateLimited):
        get_json("https://x.test/a", {}, max_retries=2, sleep=lambda s: None)


def test_get_json_huge_retry_after_means_budget_gone(monkeypatch):
    f = FakeFetch((429, {"retry-after": "14691"}, ""), ok({}))
    monkeypatch.setattr(http, "fetch", f)
    with pytest.raises(RateLimited) as e:
        get_json("https://x.test/a", {}, sleep=lambda s: None)
    assert "budget" in str(e.value) and len(f.calls) == 1


def test_get_json_other_errors_raise_http_error(monkeypatch):
    monkeypatch.setattr(http, "fetch", FakeFetch((400, {}, "bad query")))
    with pytest.raises(HttpError) as e:
        get_json("https://x.test/a", {})
    assert e.value.status == 400


def test_cache_hit_skips_network_and_refresh_bypasses(monkeypatch, tmp_path):
    f = FakeFetch(ok({"n": 1}))
    monkeypatch.setattr(http, "fetch", f)
    c = Cache(tmp_path)
    get_json("https://x.test/a", {"q": "v"}, cache=c)
    data, cached, _ = get_json("https://x.test/a", {"q": "v"}, cache=c)
    assert cached and data == {"n": 1} and len(f.calls) == 1
    get_json("https://x.test/a", {"q": "v"}, cache=Cache(tmp_path, refresh=True))
    assert len(f.calls) == 2


def test_cache_key_ignores_secrets_and_param_order():
    assert cache_key("u", {"a": 1, "b": 2, "api_key": "S", "mailto": "m@x.org"}) == cache_key("u", {"b": 2, "a": 1})
    assert cache_key("u", {"a": 1}) != cache_key("u", {"a": 2})


def test_secrets_never_reach_the_cache_or_the_url(monkeypatch, tmp_path, oa_works):
    monkeypatch.setenv("RG_OPENALEX_KEY", "oa-secret-key-123456")
    monkeypatch.setenv("RG_MAILTO", "someone@example.org")
    f = FakeFetch(ok(oa_works, {"x-ratelimit-remaining-usd": "0.081"}))
    monkeypatch.setattr(http, "fetch", f)
    oa = OpenAlex(Cache(tmp_path), years="2010-2026")
    got = oa.keyword("antibiogram")
    assert len(got) == 4 and oa.report.budget == "$0.081 left today"
    url, headers = f.calls[0]
    assert "oa-secret-key" not in url and headers["Authorization"] == "Bearer oa-secret-key-123456"  # key only in the header
    assert "mailto=someone%40example.org" in url
    for p in tmp_path.glob("*.json"):
        assert "oa-secret-key" not in p.read_text() and "someone@example.org" not in p.read_text()


def test_openalex_filter_has_abstract_year_and_language(monkeypatch, oa_works):
    f = FakeFetch(ok(oa_works))
    monkeypatch.setattr(http, "fetch", f)
    OpenAlex(None, years="2015-2024").semantic("a sentence about wards")
    url = f.calls[0][0]
    assert "search.semantic=a%20sentence%20about%20wards" in url
    assert "has_abstract%3Atrue" in url and "publication_year%3A2015-2024" in url and "language%3Aen" in url


def test_openalex_key_rejected_falls_back_to_anonymous(monkeypatch, oa_works):
    monkeypatch.setenv("RG_OPENALEX_KEY", "not-activated")
    f = FakeFetch((403, {}, '{"error":"key_not_activated"}'), ok(oa_works))
    monkeypatch.setattr(http, "fetch", f)
    oa = OpenAlex(None)
    assert len(oa.keyword("x")) == 4
    assert "Authorization" in f.calls[0][1] and "Authorization" not in f.calls[1][1]


def test_openalex_budget_exhausted_disables_source(monkeypatch):
    f = FakeFetch((429, {"retry-after": "9000"}, ""))
    monkeypatch.setattr(http, "fetch", f)
    oa = OpenAlex(None)
    assert oa.keyword("a") == [] and oa.report.disabled
    assert oa.keyword("b") == [] and len(f.calls) == 1  # no further calls once switched off


def test_s2_429_switches_source_off_for_the_run(monkeypatch):
    f = FakeFetch((429, {}, ""))
    monkeypatch.setattr(http, "fetch", f)
    s2 = SemanticScholar(None)
    assert s2.keyword("antibiogram") == []
    assert "S2_API_KEY" in s2.report.disabled
    n = len(f.calls)
    assert s2.keyword("again") == [] and len(f.calls) == n


def test_s2_sends_key_and_year_filter(monkeypatch, s2_search):
    monkeypatch.setenv("S2_API_KEY", "s2-secret")
    f = FakeFetch(ok(s2_search))
    monkeypatch.setattr(http, "fetch", f)
    got = SemanticScholar(None, years="2012-2020").keyword('"ward-level" antibiogram')
    assert len(got) == 2  # the untitled record is dropped
    url, headers = f.calls[0]
    assert headers["x-api-key"] == "s2-secret" and "year=2012-2020" in url and "%22" not in url


def test_parse_real_s2_response():
    real = json.loads((__import__("pathlib").Path(__file__).parent / "fixtures" / "s2_search_real.json").read_text())
    ps = [parse_s2_paper(x) for x in real["data"]]
    assert ps[-1] is None  # the hand-added untitled record
    good = [p for p in ps if p]
    assert len(good) == 4
    for p in good:
        assert p.doi and p.doi == p.doi.lower() and p.link.startswith("https://doi.org/")
        assert p.abstract and p.tldr and p.oa_url.startswith("http") and p.cited_by > 100 and p.authors and p.sources == {"s2"}


# ---------- open-access fallback (PMC, arXiv) ----------

def test_s2_open_access_fallback_uses_pmc_when_the_pdf_url_is_empty():
    real = json.loads((__import__("pathlib").Path(__file__).parent / "fixtures" / "s2_search_real.json").read_text())
    nano = next(x for x in real["data"] if (x.get("title") or "").startswith("Nanomaterial"))
    assert (nano.get("openAccessPdf") or {}).get("url") == ""  # recorded as empty; S2 only knows the PMC id
    p = parse_s2_paper(nano)
    assert p.oa_url == "https://pmc.ncbi.nlm.nih.gov/articles/PMC11852044"


def test_s2_open_access_fallback_order_pdf_then_pmc_then_arxiv_then_nothing():
    base = {"title": "A paper", "year": 2020, "authors": [{"name": "A B"}]}
    with_pdf = dict(base, openAccessPdf={"url": "https://x.example/p.pdf"}, externalIds={"PubMedCentral": "123", "ArXiv": "2001.00001"})
    assert parse_s2_paper(with_pdf).oa_url == "https://x.example/p.pdf"
    pmc = dict(base, openAccessPdf=None, externalIds={"PubMedCentral": "PMC123", "ArXiv": "2001.00001"})
    assert parse_s2_paper(pmc).oa_url == "https://pmc.ncbi.nlm.nih.gov/articles/PMC123"  # a "PMC" prefix is not doubled
    arxiv = dict(base, externalIds={"ArXiv": "2001.00001"})
    assert parse_s2_paper(arxiv).oa_url == "https://arxiv.org/abs/2001.00001"
    none = dict(base, openAccessPdf={"url": ""}, externalIds=None)
    assert parse_s2_paper(none).oa_url == ""
