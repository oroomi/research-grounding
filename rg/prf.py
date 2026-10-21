"""Pseudo-relevance feedback: learn the scholars' vocabulary from the first results.

Briefs use business words ("home move", "ward round"); papers use others ("residential relocation", "antibiogram").
After round one we look at the best-ranked papers, find two-word terms that recur across them and are not yet in
any query, and use the strongest as extra keyword queries. Cheap (no model), and it is only a nudge: PRF queries
get a lower weight than the brief's own queries so a drifting term cannot take over the ranking.
"""
from __future__ import annotations

from collections import Counter

from .model import Paper
from .queries import Query, QueryPlan, VERB_STEMS
from .text import BUZZ, GENERIC, STOP, stem, tokens

# words that make a bigram useless as a query even though they are not stopwords
_JUNK = {"study", "studies", "results", "result", "conclusion", "conclusions", "background", "methods", "method", "objective", "objectives",
         "patients", "paper", "article", "review", "analysis", "approach", "research", "findings", "finding", "effect", "effects",
         "important", "significant", "associated", "increase", "increased", "high", "higher", "low", "lower", "clinical", "global",
         "article", "reviewed", "data", "using", "used", "based", "evidence", "factor", "factors", "outcomes", "outcome", "impact",
         "public", "health", "healthcare", "medical", "medicine", "social", "human", "world", "population", "countries", "country", "national",
         "international", "development", "management", "quality", "level", "levels", "time", "years", "system", "knowledge", "process", "program",
         "programs", "role", "need", "needs", "use", "case", "cases", "group", "groups", "state", "states", "current", "recent", "future", "potential",
         "management", "practice", "practices", "model", "models", "novel", "major", "common", "general", "local", "large", "small", "rate", "rates"}


def _bigrams(text: str) -> set[tuple[str, str]]:
    toks = [t for t in tokens(text)]
    out = set()
    for a, b in zip(toks, toks[1:]):
        if any(len(x) < 4 or x in STOP or x in GENERIC or x in _JUNK or x in BUZZ or stem(x).rstrip("e") in VERB_STEMS for x in (a, b)):
            continue
        out.add((a, b))
    return out


def prf_queries(top_papers: list[Paper], plan: QueryPlan, n: int = 2, min_df: int = 3) -> list[Query]:
    docs = [p for p in top_papers if p.abstract]
    if len(docs) < 5:
        return []
    df: Counter[tuple[str, str]] = Counter()
    for p in docs:
        for bg in _bigrams(p.title + ". " + p.abstract):
            df[bg] += 1
    have = {stem(t) for q in plan.queries for t in tokens(q.text)} | {stem(t) for t in tokens(plan.subject)}
    brief_stems = {stem(t) for ph, _ in plan.phrases for t in tokens(ph)}
    scored = []
    for (a, b), c in df.items():
        if c < max(min_df, int(0.2 * len(docs))):
            continue
        sa, sb = stem(a), stem(b)
        if sa in have and sb in have:  # nothing new
            continue
        # a term that shares a word with the brief is anchored to the subject; a wholly unrelated one is more likely drift
        anchor = (sa in brief_stems) + (sb in brief_stems)
        scored.append((c * (1 + 0.6 * anchor) * (1 + 0.04 * (len(a) + len(b))), f"{a} {b}"))
    scored.sort(reverse=True)
    out, used = [], set()
    for _, text in scored:
        words = set(text.split())
        if words & used:
            continue
        used |= words
        out.append(Query(text, "prf", 0.8, text.split()))
        if len(out) >= n:
            break
    return out
