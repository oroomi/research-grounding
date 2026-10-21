"""Turn a challenge brief into 3-6 literature search queries plus one 'semantic' sentence.

No NLP library: a RAKE-style phrase extractor (phrases are runs of words between stopwords / punctuation,
scored by word co-occurrence and frequency), with three tweaks that matter for briefs:
  * hackathon words ("challenge", "participants", "prototype", "users") break phrases, they are never the subject;
  * the title and headings count double;
  * acronyms (CUSUM, ICU, EUCAST) are kept even when short.
An optional LLM step (see llm.py) can replace the plan with scholarly vocabulary; this module works without it.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from .text import BUZZ, GENERIC, STOP, VERBS, _WORD, split_sentences, stem, strip_markup

VERB_STEMS = {stem(v).rstrip('e') for v in VERBS}


@dataclass
class Query:
    text: str  # what is sent to the search APIs (unquoted words, AND-ed; user queries keep their own quotes)
    kind: str  # phrase | combo | user | llm | semantic
    weight: float = 1.0
    terms: list[str] = field(default_factory=list)  # the content words, for scoring coverage


@dataclass
class QueryPlan:
    queries: list[Query]
    semantic: str  # one natural-language sentence for semantic search ("" = none)
    phrases: list[tuple[str, float]]  # (phrase, weight) used to score how well a paper covers the brief
    method: str = "rake"
    semantic_extra: list[str] = field(default_factory=list)  # task-facet sentences for semantic search
    facets: list[str] = field(default_factory=list)  # names of the matched task facets
    subject: str = ""  # the phrase the facets were built around

    def all_texts(self) -> list[str]:
        return [q.text for q in self.queries] + ([self.semantic] if self.semantic else []) + self.semantic_extra


_DELIM = re.compile(r"[.!?,;:()\[\]{}\"“”‘’—–|/•*#<>=+&]+|\s-\s|\s–\s")
_CLEAN_EDGE = re.compile(r"^[^A-Za-zÀ-ÿ0-9]+|[^A-Za-zÀ-ÿ0-9]+$")


def _is_acronym(w: str) -> bool:
    return len(w) >= 2 and w.isupper() and w.isalpha()


def _heading_lines(raw: str) -> set[int]:
    """Indexes of lines that look like titles/headings: first non-empty line, markdown headings, short lines w/o period."""
    lines = raw.splitlines()
    out: set[int] = set()
    first = True
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            continue
        if first:
            out.add(i)
            first = False
        if s.startswith("#") or (len(s.split()) <= 8 and not re.search(r"[.!?]$", s) and not s.startswith(("-", "*", "•"))):
            out.add(i)
    return out


def candidate_phrases(raw: str) -> list[tuple[tuple[str, ...], bool, bool]]:
    """Return (words, in_heading, has_acronym) for every candidate phrase, in order of appearance."""
    text = strip_markup(raw)
    heads = _heading_lines(text)
    out: list[tuple[tuple[str, ...], bool, bool]] = []
    for li, line in enumerate(text.splitlines()):
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", line)
        for seg in _DELIM.split(line):
            cur: list[str] = []
            acr = False

            def flush():
                nonlocal cur, acr
                if cur:
                    # very long runs are split in two rather than used as one over-specific query
                    chunks = [cur] if len(cur) <= 4 else [cur[: len(cur) // 2], cur[len(cur) // 2:]]
                    for c in chunks:
                        out.append((tuple(c), li in heads, acr))
                cur, acr = [], False

            for raw_tok in seg.split():
                tok = _CLEAN_EDGE.sub("", raw_tok)
                if not tok or not _WORD.fullmatch(tok):
                    flush()
                    continue
                low = tok.lower()
                acronym = _is_acronym(tok)
                if (low in STOP or low in GENERIC or stem(low).rstrip('e') in VERB_STEMS) and not (acronym and low not in STOP and low not in GENERIC):
                    flush()
                    continue
                cur.append(low)
                acr = acr or acronym
            flush()
    return out


def rank_phrases(raw: str) -> list[tuple[str, float, tuple[str, ...]]]:
    """Score candidate phrases. Returns [(phrase, score, words)] best first."""
    cands = candidate_phrases(raw)
    freq: Counter[str] = Counter()
    deg: Counter[str] = Counter()
    for words, _, _ in cands:
        for w in words:
            freq[w] += 1
            deg[w] += len(words)
    pfreq: Counter[tuple[str, ...]] = Counter(w for w, _, _ in cands)
    in_head: dict[tuple[str, ...], bool] = {}
    has_acr: dict[tuple[str, ...], bool] = {}
    for words, h, a in cands:
        in_head[words] = in_head.get(words, False) or h
        has_acr[words] = has_acr.get(words, False) or a
    head_words = {w for (ws, h) in in_head.items() if h for w in ws}

    scored = []
    for words in pfreq:
        if all(w in BUZZ for w in words):
            continue
        if len(words) == 1:
            w = words[0]
            if not (freq[w] >= 2 or has_acr[words] or w in head_words or len(w) >= 9):
                continue
        s = sum(deg[w] / freq[w] + 0.8 * math.log(freq[w]) for w in words)  # RAKE ratio + recurrence: topic words recur
        s *= 1 + 0.6 * math.log(pfreq[words])  # repeated phrases are the subject
        if any(w in head_words for w in words):
            s *= 1.5
        if has_acr[words]:
            s *= 1.4
        if len(words) == 1:
            s *= 0.8
        if len(words) == 2 and not any(w in BUZZ for w in words):
            s *= 1.15  # two-word noun phrases are the best search units
        if len(words) >= 4:
            s *= 0.6
        # long words are usually the specific ones (antibiogram), short ones the vague ones (tips, wrong)
        s *= min(1.6, max(0.6, (sum(len(w) for w in words) / len(words)) / 6.5))
        scored.append((" ".join(words), s, words))
    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored


def _overlap(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    sa, sb = {stem(w) for w in a}, {stem(w) for w in b}
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    return max(inter / len(sa | sb), 1.0 if (sa <= sb or sb <= sa) else 0.0)


def pick_diverse(ranked, n: int, max_overlap: float = 0.5):
    chosen = []
    for phrase, score, words in ranked:
        if all(_overlap(words, c[2]) < max_overlap for c in chosen):
            chosen.append((phrase, score, words))
        if len(chosen) >= n:
            break
    return chosen


def semantic_sentence(raw: str, ranked, max_chars: int = 420) -> str:
    """The 1-2 sentences of the brief that carry the most subject phrases, in original order."""
    top = {w: sc for _, sc, ws in ranked[:12] for w in ws}
    heads = _heading_lines(strip_markup(raw))
    body = "\n".join(ln for i, ln in enumerate(strip_markup(raw).splitlines()) if i not in heads)
    sents = [clean_sentence(s) for ln in body.splitlines() for s in split_sentences(ln) if 6 <= len(s.split()) <= 60]
    if not sents:
        return ""
    scored = []
    for i, s in enumerate(sents):
        toks = [t.lower() for t in _WORD.findall(s)]
        val = sum(top.get(t, 0.0) for t in set(toks)) / math.sqrt(len(toks) or 1)
        scored.append((val, i, s))
    best = sorted(scored, reverse=True)[:2]
    best.sort(key=lambda x: x[1])
    out = " ".join(s for _, _, s in best)
    return out[:max_chars].rsplit(" ", 1)[0] if len(out) > max_chars else out


# What does the brief ask us to DO with the data? Each facet is a generic research task; a matching one adds a semantic query
# "<task wording> <subject>" so the search reaches method papers, not only papers about the subject.
FACETS = [
    ("detection", r"detect|alert|anomal|trend|surveil|monitor|early[- ]warning|outbreak|unusual|cluster|spike|drift|abnormal",
     "statistical methods for early detection of unusual trends and clusters in {S}", "{S} surveillance trend detection"),
    ("prediction", r"predict|forecast|risk|likel|probab|propensity|churn|demand|prognos|projection",
     "forecasting and prediction methods for {S}", "{S} forecasting prediction model"),
    ("intervention", r"nudg|behaviou?r|habit|engag|motivat|adheren|encourag|remind|prevent|educat|campaign|awareness|incentiv|reward|persua",
     "effectiveness of behavioural interventions and nudges for {S}", "{S} behavioural intervention"),
    ("allocation", r"optimi[sz]|schedul|routing|allocat|assign|capacity|logistic|dispatch|queue|timetable",
     "optimization model for {S}", "{S} optimization model"),
    ("measurement", r"\bindex\b|benchmark|ranking|\bkpi|indicator|maturity|rating|composite|scorecard",
     "composite indicator for measuring and benchmarking {S}", "{S} composite indicator"),
    ("recommendation", r"recommend|personali[sz]|tailor|preference|suggest",
     "recommender systems and personalised advice for {S}", "{S} personalised recommendation"),
    ("uncertainty", r"uncertain|confidence|reliab|small sample|small numbers|noisy|missing|sparse|robust",
     "handling uncertainty, small samples and noisy data in {S}", "{S} small sample uncertainty"),
]
_FACET_RX = [(n, re.compile(rx, re.I), sem, kw) for n, rx, sem, kw in FACETS]
_BOILER = re.compile(r"^(?:(?:your|the|our|this)\s+(?:challenge|task|mission|goal|assignment)\s+(?:is|will be)\s+to\s+|"
                     r"(?:we|the\s+\w+)\s+(?:would like|want|wants|are looking|is looking)\s+(?:you\s+|participants\s+)?to\s+|"
                     r"participants\s+(?:are asked|will be asked)\s+to\s+|(?:design|build|create|develop)\s+)", re.I)


def clean_sentence(s: str) -> str:
    """Strip imperative boilerplate ('Your challenge is to build ...') so the sentence reads like a research question."""
    prev = None
    while prev != s:
        prev, s = s, _BOILER.sub("", s.strip(), count=1)
    return s[:1].upper() + s[1:] if s else s


def pick_facets(raw: str, max_facets: int = 2) -> list[tuple[str, str, str]]:
    counts = []
    for name, rx, sem, kw in _FACET_RX:
        n = len(rx.findall(raw))
        if n:
            counts.append((n, name, sem, kw))
    counts.sort(key=lambda x: (-x[0], x[1]))
    # the best facet always counts; further ones need two trigger words so one stray 'behaviour' does not add a wrong task
    keep = [c for i, c in enumerate(counts) if i == 0 or c[0] >= 2]
    return [(n, sem, kw) for _, n, sem, kw in keep[:max_facets]]


def pick_subject(ranked) -> str:
    """The best phrase that is not itself a task word ('trend detection'): what the research is ABOUT."""
    task_rx = re.compile("|".join(rx.pattern for _, rx, _, _ in _FACET_RX), re.I)
    for phrase, _score, words in ranked:
        if not task_rx.search(phrase) and not all(w in BUZZ for w in words):
            return phrase
    return ranked[0][0] if ranked else ""


def parse_user_keywords(keywords) -> list[str]:
    """--keywords accepts several arguments and/or one comma/semicolon separated string."""
    if not keywords:
        return []
    if isinstance(keywords, str):
        keywords = [keywords]
    out = []
    for k in keywords:
        for part in re.split(r"[;,]\s*", k):
            part = part.strip()
            if part:
                out.append(part)
    return out


def extract_queries(brief: str, keywords=None, max_queries: int = 6, semantic: bool = True) -> QueryPlan:
    """Plan the searches. `keywords` (user supplied) come first; the rest is filled from the brief."""
    user = parse_user_keywords(keywords)
    ranked = rank_phrases(brief)
    n_user = min(len(user), max_queries - 2) if user else 0
    n_auto = max(max_queries - n_user, 2 if user else 3)
    facets = pick_facets(brief) if semantic else []
    # what the research is ABOUT: the user's first term if they gave one (they know better than RAKE), else the best brief phrase
    subject = re.sub(r'["“”]', "", user[0]).strip() if user else pick_subject(ranked)
    n_facet = min(len(facets), 2 if n_auto >= 5 else (1 if n_auto >= 4 else 0))
    n_combo = 1 if n_auto - n_facet >= 4 else 0
    chosen = pick_diverse(ranked, n_auto - n_combo - n_facet)

    queries: list[Query] = []
    for u in user[:n_user]:
        words = [w.lower() for w in _WORD.findall(u)]
        queries.append(Query(u, "user", 1.3, words))
    for phrase, _score, words in chosen:
        queries.append(Query(phrase, "phrase", 1.0, list(words)))
    # combos: the strongest phrase paired with the next ones; AND-ed words restrict to papers on the intersection
    for i in range(1, 1 + n_combo):
        if len(chosen) > i:
            a, b = chosen[0], chosen[i]
            queries.append(Query(f"{a[0]} {b[0]}", "combo", 1.2, list(a[2]) + list(b[2])))
    for _name, _sem, kw in facets[:n_facet]:
        text = kw.format(S=subject)
        queries.append(Query(text, "facet", 1.2, [w for w in _WORD.findall(text.lower()) if w not in STOP]))
    weights = {p: s for p, s, _ in chosen}
    top = max(weights.values(), default=1.0)
    phrases = [(p, round(s / top, 3)) for p, s in weights.items()]
    phrases += [(u, 1.3) for u in user[:n_user]]
    return QueryPlan(queries=queries[:max_queries], semantic=semantic_sentence(brief, ranked) if semantic else "",
                     phrases=phrases, method="rake+user" if user else "rake",
                     semantic_extra=[re.sub(r'["“”]', "", u) for u in user[:3]] + ([sem.format(S=subject) for _n, sem, _kw in facets] if subject else []),
                     facets=[n for n, _s, _k in facets], subject=subject)
