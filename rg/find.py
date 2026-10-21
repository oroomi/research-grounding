"""CLI: paste a challenge brief, get the most relevant, well-cited papers and one method card per paper.

    python3 -m rg.find --brief brief.txt [--keywords "term one" "term two"] [--years 2010-2026] [--top 10]

Environment (all optional):
  RG_MAILTO          your email, sent to OpenAlex as the "polite pool" mailto parameter
  RG_OPENALEX_KEY    free OpenAlex API key (10x the anonymous daily budget)
  S2_API_KEY         Semantic Scholar API key (without it the shared anonymous pool often answers 429)
  ANTHROPIC_API_KEY  enables the LLM steps (better queries, drafted "signals" section); never required
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

from . import __version__
from .cards import write_cards
from .http import Cache
from .model import Paper
from .queries import QueryPlan, extract_queries
from .rank import merge, rank, select_top
from .sources import OpenAlex, SemanticScholar


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def build_plan(brief: str, keywords, max_queries: int, use_llm: bool, log=_log) -> tuple[QueryPlan, str]:
    plan = extract_queries(brief, keywords, max_queries=max_queries)
    note = "keyword extraction"
    if use_llm and os.environ.get("ANTHROPIC_API_KEY"):
        from . import llm
        try:
            better = llm.plan_queries(brief, plan, max_queries=max_queries)
            if better:
                plan, note = better, "LLM-planned queries (" + llm.model_name() + ")"
        except Exception as e:  # the LLM is an extra; any failure falls back to the offline plan
            log(f"LLM query planning failed ({type(e).__name__}: {e}); using keyword extraction")
    return plan, note


SEM_WEIGHT = 2.5
ABSTRACT_KEEP = 1500  # results.json keeps a snippet, not the whole abstract (some records carry whole articles)


def retrieve(plan: QueryPlan, oa: OpenAlex, s2: SemanticScholar | None, s2_queries: int = 3, log=_log) -> list[Paper]:
    papers: list[Paper] = []

    def add(found: list[Paper], source: str, label: str, kind: str, weight: float):
        for i, p in enumerate(found):
            p.hits.append({"source": source, "query": label, "kind": kind, "rank": i + 1, "weight": weight})
            papers.append(p)

    for q in plan.queries:
        found = oa.keyword(q.text)
        log(f"  openalex  {q.kind:<8} {q.text[:60]!r:<64} -> {len(found)}")
        add(found, "openalex", q.text, q.kind, q.weight)
    for k, sent in enumerate(([plan.semantic] if plan.semantic else []) + plan.semantic_extra):
        found = oa.semantic(sent)
        log(f"  openalex  semantic {sent[:60]!r} -> {len(found)}")
        lo = min((p.raw_score for p in found if p.raw_score is not None), default=0.0)
        hi = max((p.raw_score for p in found if p.raw_score is not None), default=0.0)
        for i, p in enumerate(found):
            sim = ((p.raw_score - lo) / (hi - lo)) if (hi > lo and p.raw_score is not None) else 0.0
            p.hits.append({"source": "openalex", "query": sent[:80], "kind": "semantic", "rank": i + 1, "weight": SEM_WEIGHT if k == 0 else SEM_WEIGHT * 0.8, "sim": round(sim, 3), "raw": p.raw_score})
            papers.append(p)
    if s2 is not None:
        # the S2 free pool is slow and shared: ask it about the user's terms and the strongest queries only
        ordered = [q for q in plan.queries if q.kind in ("user", "llm")] + [q for q in plan.queries if q.kind not in ("user", "llm")]
        for q in ordered[:s2_queries]:
            found = s2.keyword(q.text)
            log(f"  s2        {q.kind:<8} {q.text[:60]!r:<64} -> {len(found)}")
            add(found, "s2", q.text, q.kind, q.weight)
            if s2.report.disabled:
                log(f"  s2 switched off for this run: {s2.report.disabled[:120]}")
                break
    return papers


def prf_round(papers: list[Paper], plan: QueryPlan, oa: OpenAlex, log=_log) -> list[Paper]:
    """Second pass: learn scholarly vocabulary from the best first-round papers and search with it."""
    from .prf import prf_queries
    first = rank(merge([_clone(p) for p in papers]), plan.phrases)
    extra = prf_queries(first[:15], plan)
    out: list[Paper] = []
    for q in extra:
        found = oa.keyword(q.text)
        log(f"  openalex  prf      {q.text!r:<64} -> {len(found)}")
        for i, p in enumerate(found):
            p.hits.append({"source": "openalex", "query": q.text, "kind": "prf", "rank": i + 1, "weight": q.weight})
            out.append(p)
    plan.queries.extend(extra)
    return out


def _clone(p: Paper) -> Paper:
    import copy
    return copy.deepcopy(p)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="rg.find", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("\n\n", 1)[1])
    ap.add_argument("--brief", required=True, help="text/markdown file with the challenge brief ('-' reads stdin)")
    ap.add_argument("--keywords", nargs="+", metavar="TERM", help='extra search terms, e.g. --keywords "antibiogram" "CUSUM control chart"')
    ap.add_argument("--years", default=f"2010-{dt.date.today().year}", help="publication years, default 2010-<this year>")
    ap.add_argument("--top", type=int, default=10, help="how many papers get a method card (default 10)")
    ap.add_argument("--out", default="cards", help="output directory for cards/ (default ./cards)")
    ap.add_argument("--cache-dir", default=".cache", help="raw API responses are cached here (default ./.cache)")
    ap.add_argument("--max-queries", type=int, default=6, help="keyword queries per source, 3-6 (default 6)")
    ap.add_argument("--max-reviews", type=int, default=3, help="at most this many surveys/reviews in the top list (default 3)")
    ap.add_argument("--no-prf", action="store_true", help="skip the second pass that learns scholarly vocabulary from the first results")
    ap.add_argument("--no-semantic-scholar", action="store_true", help="skip Semantic Scholar entirely")
    ap.add_argument("--no-llm", action="store_true", help="ignore ANTHROPIC_API_KEY even if set")
    ap.add_argument("--any-language", action="store_true", help="do not restrict OpenAlex to English papers")
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and re-query")
    ap.add_argument("--dry-run", action="store_true", help="print the planned queries and stop (no network)")
    ap.add_argument("--version", action="version", version=f"rg {__version__}")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    brief = sys.stdin.read() if a.brief == "-" else Path(a.brief).read_text(encoding="utf-8")
    if not brief.strip():
        _log("the brief is empty")
        return 2
    max_q = min(6, max(3, a.max_queries))
    use_llm = not a.no_llm
    plan, how = build_plan(brief, a.keywords, max_q, use_llm)
    _log(f"Query plan ({how}):")
    for q in plan.queries:
        _log(f"  [{q.kind}] {q.text}")
    if plan.semantic:
        _log(f"  [semantic] {plan.semantic}")
    if a.dry_run:
        return 0

    cache = Cache(a.cache_dir, refresh=a.refresh)
    oa = OpenAlex(cache, years=a.years, lang=None if a.any_language else "en", log=_log)
    s2 = None if a.no_semantic_scholar else SemanticScholar(cache, years=a.years, log=_log)
    _log("Searching:")
    raw = retrieve(plan, oa, s2)
    if raw and not a.no_prf:
        raw += prf_round(raw, plan, oa)
    if not raw:
        _log("No results. Errors: " + "; ".join(oa.report.errors + (s2.report.errors if s2 else [])))
        return 1
    merged = merge(raw)
    ranked = rank(merged, plan.phrases)
    top = select_top(ranked, a.top, a.max_reviews)
    meta = {
        "version": __version__, "date": dt.date.today().isoformat(), "plan_method": how, "years": a.years,
        "queries": [{"kind": q.kind, "text": q.text} for q in plan.queries], "semantic": plan.semantic,
        "candidates": len(raw), "unique": len(merged),
        "sources": {"openalex": {"calls": oa.report.calls, "cached": oa.report.cached, "errors": oa.report.errors, "budget": oa.report.budget},
                    "semantic_scholar": ({"calls": s2.report.calls, "cached": s2.report.cached, "errors": s2.report.errors,
                                          "disabled": s2.report.disabled} if s2 else {"skipped": True})},
        "llm": bool(use_llm and os.environ.get("ANTHROPIC_API_KEY")),
    }
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    write_cards(top, ranked, plan, meta, out, brief, use_llm=use_llm, log=_log)
    (out / "results.json").write_text(json.dumps({"meta": meta, "top": [p.to_dict(ABSTRACT_KEEP) for p in top],
                                                   "candidates": [p.to_dict(ABSTRACT_KEEP) for p in ranked[:60]]}, indent=1, ensure_ascii=False))
    _log(f"\n{len(raw)} hits -> {len(merged)} unique papers -> top {len(top)}. Cards in {out}/ (start with {out}/INDEX.md)")
    if oa.report.budget:
        _log(f"OpenAlex: {oa.report.budget}")
    for i, p in enumerate(top, 1):
        first = (p.authors[0].split()[-1] if p.authors else "?")
        _log(f"{i:>2}. {p.score:5.2f}  {first} ({p.year}) {p.title[:90]}  [{p.cited_by} cites]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
