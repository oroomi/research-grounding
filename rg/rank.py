"""Merge results from several queries/sources, drop duplicates, rank.

score = relevance^2 x impact x recency x access
  relevance : 0.30 * reciprocal-rank fusion over every query that returned the paper (semantic queries count 2-2.5x), scaled to 0..1
            + 0.30 * how much of the brief's subject phrases appear in the title and abstract (rare words weigh more, see pool_idf)
            + 0.40 * the best semantic-search similarity, min-max scaled inside its query (0 if never found that way)
  impact    : 1 + 0.5 * log10(1 + citations)          (compressive: 1000 cites is 2.5x of 0, relevance decides first)
  recency   : 0.70 + 0.30 * exp(-age / 10)            (a 20-year-old paper keeps 0.74)
  access    : x1.10 if an open-access copy exists, x0.5 if there is no abstract to build a card from
Reviews are allowed but capped (see select_top) so the list is not ten surveys.
"""
from __future__ import annotations

import datetime as _dt
import math
import re

from .model import Paper, norm_doi, norm_title
from .text import stem, tokens, STOP

RRF_K = 60
W_RRF, W_COV, W_SIM = 0.30, 0.30, 0.40
IMPACT_K = 0.5


# ---------- merge / dedupe ----------

def _first_surname(p: Paper) -> str:
    if not p.authors:
        return ""
    parts = re.sub(r"[^A-Za-zÀ-ɏ ,'-]", "", p.authors[0]).replace(",", " ").split()
    return parts[-1].lower() if parts else ""


def _title_tokens(t: str) -> set[str]:
    return set(norm_title(t).split())


def is_duplicate(a: Paper, b: Paper) -> bool:
    if a.doi and b.doi:
        return a.doi == b.doi
    na, nb = norm_title(a.title), norm_title(b.title)
    if na and na == nb:
        return True
    ta, tb = _title_tokens(a.title), _title_tokens(b.title)
    if len(ta) >= 5 and len(tb) >= 5:
        jac = len(ta & tb) / len(ta | tb)
        # preprint vs published version: near-identical title, same first author, years within 2
        if jac >= 0.85 and _first_surname(a) == _first_surname(b) and abs((a.year or 0) - (b.year or 0)) <= 2:
            return True
    return False


def _absorb(keep: Paper, other: Paper) -> None:
    """Merge `other` into `keep`, preferring the richer value for every field."""
    keep.hits += other.hits
    keep.sources |= other.sources
    keep.ids.update({k: v for k, v in other.ids.items() if v})
    keep.cited_by = max(keep.cited_by, other.cited_by)
    for f in ("doi", "venue", "oa_url", "tldr"):
        if not getattr(keep, f) and getattr(other, f):
            setattr(keep, f, getattr(other, f))
    if len(other.abstract) > len(keep.abstract):
        keep.abstract = other.abstract
    if not keep.authors and other.authors:
        keep.authors = other.authors
    if keep.kind in ("preprint", "") and other.kind not in ("preprint", ""):
        keep.kind = other.kind
    if keep.doi:
        keep.url = f"https://doi.org/{keep.doi}"


def merge(papers: list[Paper]) -> list[Paper]:
    """Collapse duplicates (same DOI, same normalised title, or preprint/published twins)."""
    out: list[Paper] = []
    by_key: dict[str, Paper] = {}
    for p in papers:
        p.doi = norm_doi(p.doi)
        existing = by_key.get(p.doi) if p.doi else None
        if existing is None:
            existing = by_key.get("t:" + norm_title(p.title))
        if existing is None:
            for q in out:
                if is_duplicate(p, q):
                    existing = q
                    break
        if existing is not None:
            _absorb(existing, p)
            if existing.doi:
                by_key[existing.doi] = existing
            continue
        out.append(p)
        if p.doi:
            by_key[p.doi] = p
        by_key["t:" + norm_title(p.title)] = p
    return out


# ---------- scoring ----------

def paper_stems(p: Paper) -> tuple[set[str], set[str]]:
    title_s = {stem(t) for t in tokens(p.title) if t not in STOP}
    return title_s, title_s | {stem(t) for t in tokens(p.abstract) if t not in STOP}


def pool_idf(papers: list[Paper]) -> dict[str, float]:
    """How rare is each stem across the candidate pool? Words every candidate contains (the subject itself) say nothing
    about which paper is the better fit, words few contain (the method, the setting) do."""
    df: dict[str, int] = {}
    for p in papers:
        for s_ in paper_stems(p)[1]:
            df[s_] = df.get(s_, 0) + 1
    n = max(1, len(papers))
    return {s_: math.log(1 + n / (1 + c)) for s_, c in df.items()}


def coverage(p: Paper, phrases: list[tuple[str, float]], idf: dict[str, float] | None = None) -> float:
    """Weighted share of the brief's subject phrases found in the paper's title+abstract (title counts extra).
    With `idf`, rare stems weigh more than stems nearly every candidate has."""
    if not phrases:
        return 0.0
    title_s, body_s = paper_stems(p)
    total = got = 0.0
    for phrase, w in phrases:
        ps = [stem(t) for t in tokens(phrase) if t not in STOP]
        if not ps:
            continue
        ws = [(idf or {}).get(s_, 1.0) if idf else 1.0 for s_ in ps]
        if idf:  # a stem the pool has never seen scores as the rarest one
            ws = [idf.get(s_, math.log(1 + len(idf))) for s_ in ps]
        mass = sum(ws) or 1.0
        in_body = sum(wi for s_, wi in zip(ps, ws) if s_ in body_s) / mass
        in_title = sum(wi for s_, wi in zip(ps, ws) if s_ in title_s) / mass
        got += w * mass * min(1.0, in_body + 0.25 * in_title)
        total += w * mass
    return got / total if total else 0.0


def impact(cited_by: int) -> float:
    return 1.0 + IMPACT_K * math.log10(1 + max(0, cited_by))


def recency(year: int | None, now_year: int) -> float:
    if not year:
        return 0.8
    age = max(0, now_year - year)
    return 0.70 + 0.30 * math.exp(-age / 10.0)


def rank(papers: list[Paper], phrases: list[tuple[str, float]], now_year: int | None = None) -> list[Paper]:
    now_year = now_year or _dt.date.today().year
    for p in papers:
        p.rrf = sum(h.get("weight", 1.0) / (RRF_K + h["rank"]) for h in p.hits)
    top = max((p.rrf for p in papers), default=0.0) or 1.0
    idf = pool_idf(papers)
    for p in papers:
        p.coverage = coverage(p, phrases, idf)
        p.sim = max((h.get("sim", 0.0) for h in p.hits if h.get("kind") == "semantic"), default=0.0)
        p.relevance = W_RRF * (p.rrf / top) + W_COV * p.coverage + W_SIM * p.sim
        access = (1.10 if p.oa_url else 1.0) * (1.0 if p.abstract else 0.5)
        p.score = (p.relevance ** 2) * impact(p.cited_by) * recency(p.year, now_year) * access
    return sorted(papers, key=lambda p: (-p.score, -p.cited_by, p.title))


def is_review(p: Paper) -> bool:
    return p.kind == "review" or bool(re.search(r"\b(systematic review|meta-analysis|scoping review|literature review|a review|review of|overview|survey)\b",
                                                 p.title, re.I))


def select_top(ranked: list[Paper], n: int, max_reviews: int = 3) -> list[Paper]:
    """Top n by score, but at most `max_reviews` surveys: method cards need method papers."""
    out, reviews = [], 0
    for p in ranked:
        if is_review(p):
            if reviews >= max_reviews:
                continue
            reviews += 1
        out.append(p)
        if len(out) >= n:
            break
    return out
