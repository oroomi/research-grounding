"""Search clients: OpenAlex (works search + semantic search) and Semantic Scholar (graph paper search).

Each client turns raw JSON into `Paper` records (pure functions, tested on recorded fixtures) and wraps
the network call (cache + backoff) in one method. Failures never abort a run: they are reported and
the other source carries on.
"""
from __future__ import annotations

import os
import re
import time

from .http import Cache, HttpError, RateLimited, get_json
from .model import Paper, norm_doi
from .text import reconstruct_abstract

OPENALEX_URL = "https://api.openalex.org/works"
S2_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

OA_SELECT = ("id,doi,title,display_name,publication_year,cited_by_count,open_access,best_oa_location,primary_location,"
             "authorships,abstract_inverted_index,type,language,is_retracted,relevance_score")
S2_FIELDS = "title,abstract,year,citationCount,influentialCitationCount,openAccessPdf,externalIds,authors,venue,tldr,publicationTypes,isOpenAccess,url"


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


# ---------- parsers (pure) ----------

def parse_openalex_work(w: dict) -> Paper | None:
    title = _clean(w.get("title") or w.get("display_name") or "")
    if not title or w.get("is_retracted"):
        return None
    doi = norm_doi(w.get("doi"))
    oa = w.get("open_access") or {}
    best = w.get("best_oa_location") or {}
    prim = w.get("primary_location") or {}
    oa_url = ""
    if oa.get("is_oa"):
        oa_url = oa.get("oa_url") or best.get("pdf_url") or best.get("landing_page_url") or ""
    src = (prim.get("source") or {}).get("display_name") or ""
    authors = [(a.get("author") or {}).get("display_name", "") for a in (w.get("authorships") or [])]
    wid = (w.get("id") or "").rsplit("/", 1)[-1]
    paper = Paper(
        title=title, year=w.get("publication_year"), authors=[a for a in authors if a], venue=_clean(src), doi=doi,
        url=(f"https://doi.org/{doi}" if doi else (prim.get("landing_page_url") or w.get("id") or "")),
        oa_url=oa_url, abstract=reconstruct_abstract(w.get("abstract_inverted_index")),
        cited_by=int(w.get("cited_by_count") or 0), kind=w.get("type") or "article",
        sources={"openalex"}, ids={"openalex": wid},
    )
    paper.raw_score = w.get("relevance_score")
    return paper


def parse_s2_paper(p: dict) -> Paper | None:
    title = _clean(p.get("title") or "")
    if not title:
        return None
    ext = p.get("externalIds") or {}
    doi = norm_doi(ext.get("DOI"))
    pdf = (p.get("openAccessPdf") or {}).get("url") or ""
    if not pdf and ext.get("PubMedCentral"):  # S2 sometimes has the PMC id but an empty pdf url
        pdf = f"https://pmc.ncbi.nlm.nih.gov/articles/PMC{str(ext['PubMedCentral']).removeprefix('PMC')}"
    if not pdf and ext.get("ArXiv"):
        pdf = f"https://arxiv.org/abs/{ext['ArXiv']}"
    types = p.get("publicationTypes") or []
    kind = "review" if "Review" in types else ("article" if types else "article")
    return Paper(
        title=title, year=p.get("year"), authors=[a.get("name", "") for a in (p.get("authors") or []) if a.get("name")],
        venue=_clean(p.get("venue") or ""), doi=doi, url=(f"https://doi.org/{doi}" if doi else (p.get("url") or "")),
        oa_url=pdf, abstract=_clean(p.get("abstract") or ""), cited_by=int(p.get("citationCount") or 0), kind=kind,
        tldr=_clean((p.get("tldr") or {}).get("text") or ""), sources={"s2"}, ids={"s2": p.get("paperId") or ""},
    )


def year_range(years: str | None) -> tuple[int, int] | None:
    if not years:
        return None
    m = re.fullmatch(r"\s*(\d{4})\s*[-:]\s*(\d{4})\s*", years)
    if not m:
        raise ValueError(f"--years wants 2010-2026, got {years!r}")
    lo, hi = int(m.group(1)), int(m.group(2))
    return (min(lo, hi), max(lo, hi))


# ---------- clients ----------

class SourceReport:
    """What happened per source, printed in the run summary and written into INDEX.md."""

    def __init__(self):
        self.calls = 0
        self.cached = 0
        self.errors: list[str] = []
        self.disabled = ""
        self.budget = ""


class OpenAlex:
    name = "openalex"

    def __init__(self, cache: Cache | None, years: str | None = None, per_page: int = 40, lang: str | None = "en",
                 log=lambda m: None, sleep=None):
        self.cache, self.per_page, self.log, self.sleep = cache, per_page, log, sleep
        self.mailto = os.environ.get("RG_MAILTO", "").strip()
        self.key = (os.environ.get("RG_OPENALEX_KEY") or os.environ.get("OPENALEX_API_KEY") or "").strip()
        self.yr = year_range(years)
        self.lang = lang
        self.report = SourceReport()

    def _filter(self) -> str:
        f = ["has_abstract:true", "is_retracted:false"]
        if self.yr:
            f.append(f"publication_year:{self.yr[0]}-{self.yr[1]}")
        if self.lang:
            f.append(f"language:{self.lang}")
        return ",".join(f)

    def _call(self, search_param: str, text: str) -> list[Paper]:
        if self.report.disabled:
            return []
        params = {search_param: text, "filter": self._filter(), "per-page": self.per_page, "select": OA_SELECT}
        for attempt in (0, 1):
            full = dict(params)
            headers = {}
            if self.mailto:
                full["mailto"] = self.mailto
            if self.key and attempt == 0:
                headers["Authorization"] = f"Bearer {self.key}"
            try:
                data, cached, hdrs = get_json(OPENALEX_URL, full, headers=headers, cache=self.cache, source="openalex",
                                              min_interval=0.15,
                                              sleep=self.sleep, log=self.log)
            except RateLimited as e:
                self.report.disabled = str(e)
                self.report.errors.append(str(e))
                return []
            except HttpError as e:
                if e.status == 403 and self.key and attempt == 0:
                    self.log("openalex: API key rejected (not activated yet?), continuing without it")
                    self.report.errors.append("API key rejected, used the anonymous budget")
                    continue
                self.report.errors.append(f"{search_param}={text[:40]!r}: {e}")
                return []
            self.report.calls += 1
            self.report.cached += 1 if cached else 0
            rem = (hdrs or {}).get("x-ratelimit-remaining-usd")
            if rem:
                self.report.budget = f"${float(rem):.3f} left today"
            return [p for p in (parse_openalex_work(w) for w in data.get("results", [])) if p]
        return []

    def keyword(self, text: str) -> list[Paper]:
        return self._call("search.title_abstract_keywords", text)

    def semantic(self, text: str) -> list[Paper]:
        # semantic search cannot be combined with other search params, filters are fine
        return self._call("search.semantic", text)


class SemanticScholar:
    name = "s2"

    def __init__(self, cache: Cache | None, years: str | None = None, limit: int = 40, log=lambda m: None, sleep=None):
        self.cache, self.limit, self.log, self.sleep = cache, limit, log, sleep
        self.key = (os.environ.get("S2_API_KEY") or os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or "").strip()
        self.yr = year_range(years)
        self.report = SourceReport()

    def keyword(self, text: str) -> list[Paper]:
        if self.report.disabled:
            return []
        params = {"query": re.sub(r'["\-]', " ", text), "limit": self.limit, "fields": S2_FIELDS}
        if self.yr:
            params["year"] = f"{self.yr[0]}-{self.yr[1]}"
        headers = {"x-api-key": self.key} if self.key else {}
        try:
            data, cached, _ = get_json(S2_URL, params, headers=headers, cache=self.cache, source="semantic-scholar",
                                       max_retries=3, backoff=3.0, backoff_cap=20.0, min_interval=1.1, max_wait=30.0,
                                       sleep=self.sleep, log=self.log)
        except RateLimited as e:
            # the anonymous pool is shared by everyone; one hard failure switches the source off for this run
            self.report.disabled = ("Semantic Scholar rate-limited this run (anonymous pool is shared); set S2_API_KEY to use it. "
                                    + str(e))
            self.report.errors.append(self.report.disabled)
            return []
        except HttpError as e:
            self.report.errors.append(f"{text[:40]!r}: {e}")
            return []
        self.report.calls += 1
        self.report.cached += 1 if cached else 0
        return [p for p in (parse_s2_paper(x) for x in data.get("data", [])) if p]
