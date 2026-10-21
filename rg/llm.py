"""Optional LLM steps, used only when ANTHROPIC_API_KEY is set. The kit never requires them.

  * plan_queries : turn a business-language brief into scholarly search queries (the biggest relevance win)
  * draft_sections : draft the "signals we could compute" section of a card from the abstract

The key is read from the environment at call time, sent only to api.anthropic.com, never logged or cached.
Model: RG_MODEL, default claude-sonnet-5-5. Output is always labelled as a draft in the cards.
"""
from __future__ import annotations

import json
import os
import re

from .http import post_json
from .model import Paper
from .queries import Query, QueryPlan
from .text import tokens, STOP

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5-5"


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def model_name() -> str:
    return os.environ.get("RG_MODEL", DEFAULT_MODEL)


def ask(system: str, user: str, max_tokens: int = 900) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    status, body = post_json(API_URL, {"x-api-key": key, "anthropic-version": "2023-06-01"},
                             {"model": model_name(), "max_tokens": max_tokens, "system": system,
                              "messages": [{"role": "user", "content": user}]})
    if status != 200:
        raise RuntimeError(f"Anthropic API HTTP {status}: {str((body.get('error') or {}).get('message', ''))[:160]}")
    return "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")


def extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in model output")
    return json.loads(m.group(0))


PLAN_SYSTEM = ("You help a hackathon team find peer-reviewed literature for a challenge brief. Reply with JSON only: "
               '{"queries": [4 to 6 strings], "semantic": "one sentence"}. Each query is 2-4 words in the vocabulary scholars use '
               "(not the brief's marketing words), mixing WHAT is studied and WHAT IS COMPUTED, DETECTED OR PREDICTED. "
               '"semantic" is one plain sentence, in scholarly language, describing the research question. No commentary.')


def plan_queries(brief: str, offline: QueryPlan, max_queries: int = 6) -> QueryPlan | None:
    data = extract_json(ask(PLAN_SYSTEM, brief[:6000], 500))
    qs = [q.strip() for q in data.get("queries", []) if isinstance(q, str) and 2 <= len(q.split()) <= 7][:max_queries]
    if len(qs) < 3:
        return None
    queries = [Query(q, "llm", 1.2, [t for t in tokens(q) if t not in STOP]) for q in qs]
    phrases = [(q, 1.0) for q in qs] + offline.phrases[:2]
    sem = str(data.get("semantic", "")).strip()[:420] or offline.semantic
    return QueryPlan(queries=queries[:max_queries], semantic=sem, phrases=phrases, method="llm")


DRAFT_SYSTEM = ("You help a hackathon team turn a paper's ABSTRACT into something they can build. Use only the abstract; do not invent numbers, "
                "datasets or formulas that are not in it. Reply with JSON only: "
                '{"signals": "markdown bullet list, 3 to 5 bullets: each is an input column or derived value a team could compute from '
                'typical public or partner data (counts, rates, dates, categories) and how it would be combined; say \\"not in the abstract\\" '
                'where the abstract does not give the formula"}')


def draft_sections(p: Paper, brief: str) -> dict:
    user = f"Challenge brief (context):\n{brief[:1500]}\n\nPaper: {p.title} ({p.year})\nAbstract: {p.abstract[:2500]}"
    data = extract_json(ask(DRAFT_SYSTEM, user, 700))
    sig = data.get("signals", "")
    if isinstance(sig, list):
        sig = "\n".join(f"- {x}" for x in sig)
    return {"signals": str(sig)}
