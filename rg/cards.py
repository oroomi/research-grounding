"""Method cards: one markdown file per paper plus INDEX.md.

Everything in a card that is not metadata is EXTRACTED from the abstract (sentences are copied, not paraphrased)
or computed from simple rules, and the card says so. With ANTHROPIC_API_KEY set, the "signals" section is
drafted by the model and labelled "draft, check the paper". Nothing here reads the full text of a paper.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path

from .model import Paper
from .queries import QueryPlan
from .rank import is_review
from .text import split_sentences, stem, tokens, STOP

PARTICLES = {"van", "von", "de", "del", "della", "di", "da", "der", "den", "du", "la", "le", "bin", "ibn", "al", "el", "ter", "ten", "op", "af", "av"}


# ---------- names, citations, slugs ----------

def split_name(full: str) -> tuple[str, str]:
    """('Jane Q.', 'van der Berg') from 'Jane Q. van der Berg' or 'van der Berg, Jane Q.'"""
    full = re.sub(r"\s+", " ", full).strip()
    if "," in full:
        fam, giv = [x.strip() for x in full.split(",", 1)]
        return giv, fam
    parts = full.split(" ")
    if len(parts) == 1:
        return "", parts[0]
    i = len(parts) - 1
    while i > 1 and parts[i - 1].lower() in PARTICLES:
        i -= 1
    return " ".join(parts[:i]), " ".join(parts[i:])


def surname(full: str) -> str:
    return split_name(full)[1]


def initials(given: str) -> str:
    out = []
    for part in re.split(r"[\s]+", given.strip()):
        for sub in part.split("-"):
            if sub and sub[0].isalpha():
                out.append(sub[0].upper() + ".")
    return " ".join(out)


def author_short(p: Paper) -> str:
    """'Smith', 'Smith & Jones', 'Smith et al.' for in-text citations and the badge."""
    names = [surname(a) for a in p.authors if a]
    if not names:
        return "Unknown author"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} & {names[1]}"
    return f"{names[0]} et al."


def apa_citation(p: Paper) -> str:
    def fmt(a: str) -> str:
        g, f = split_name(a)
        return f"{f}, {initials(g)}".rstrip(", ").strip() if g else f

    names = [fmt(a) for a in p.authors if a]
    if not names:
        auth = "Unknown author"
    elif len(names) == 1:
        auth = names[0]
    elif len(names) <= 6:
        auth = ", ".join(names[:-1]) + ", & " + names[-1]
    else:
        auth = ", ".join(names[:6]) + ", et al."
    title = p.title.rstrip(".")
    venue = f" *{p.venue}*." if p.venue else ""
    link = f" https://doi.org/{p.doi}" if p.doi else (f" {p.url}" if p.url else "")
    return f"{auth} ({p.year or 'n.d.'}). {title}.{venue}{link}".replace("..", ".")


def ascii_slug(s: str, max_words: int = 4) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    words = [w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP]
    return "-".join(words[:max_words])


def make_slug(p: Paper, used: set[str]) -> str:
    base = "-".join(x for x in (ascii_slug(surname(p.authors[0]), 2) if p.authors else "anon", str(p.year or "nd"), ascii_slug(p.title)) if x)
    slug, n = base, 2
    while slug in used:
        slug, n = f"{base}-{n}", n + 1
    used.add(slug)
    return slug


# ---------- abstract mining (rules, no model) ----------

METHOD_LEXICON = [  # domain-agnostic: statistics, forecasting, ML, causal inference, behaviour, spatial
    (r"\bcusum\b|cumulative sum", "CUSUM"), (r"\bewma\b|exponentially weighted moving average", "EWMA"),
    (r"control chart|shewhart|statistical process control", "control chart / SPC"), (r"farrington", "Farrington algorithm"),
    (r"scan statistic", "scan statistic"), (r"change[- ]?point", "change-point detection"), (r"anomal(?:y|ies) detection|outlier detection", "anomaly detection"),
    (r"time[- ]series|arima|sarima", "time series"), (r"seasonal(?:ity)?", "seasonality"), (r"holt[- ]winters|exponential smoothing", "exponential smoothing"),
    (r"poisson", "Poisson model"), (r"negative binomial", "negative binomial"), (r"logistic regression", "logistic regression"),
    (r"linear regression|ordinary least squares", "linear regression"), (r"mixed[- ]effects?|multilevel|hierarchical (?:model|linear)", "multilevel / mixed model"),
    (r"bayesian|posterior|prior distribution|credible interval", "Bayesian"), (r"shrinkage|partial pooling|empirical bayes", "shrinkage / partial pooling"),
    (r"confidence interval|wilson|clopper|binomial (?:proportion|test)", "binomial confidence interval"), (r"funnel plot", "funnel plot"),
    (r"kaplan|survival analysis|cox |proportional hazards|time[- ]to[- ]event|hazard", "survival analysis"), (r"random forest|decision tree|gradient boost|xgboost", "tree ensemble"),
    (r"machine[- ]learning|supervised learning|classifier|classification model|predictive model", "machine learning"),
    (r"neural network|deep learning|lstm|transformer|convolutional", "neural network"), (r"support vector", "SVM"), (r"k-means|clustering|cluster analysis", "clustering"),
    (r"natural language processing|\bnlp\b|topic model|text mining|sentiment", "text mining / NLP"), (r"compartmental|\bsir\b|\bseir\b", "compartmental model"),
    (r"monte carlo|simulation", "simulation"), (r"bootstrap", "bootstrap"), (r"propensity score|matched (?:cohort|control|pairs)", "propensity / matching"),
    (r"difference[- ]in[- ]differences?", "difference-in-differences"), (r"randomi[sz]ed (?:controlled )?(?:trial|experiment)|\brct\b|a/b test", "randomised experiment"),
    (r"regression discontinuity|instrumental variable", "quasi-experimental"), (r"nudge|default effect|choice architecture|behaviou?ral intervention|reminder", "nudge / behaviour change"),
    (r"risk (?:score|index|stratification|prediction)|scoring (?:system|model)|composite (?:index|score)", "risk score / index"),
    (r"\broc\b|\bauc\b|area under|sensitivity (?:and|/) specificity|precision (?:and|/) recall", "sensitivity / specificity / AUC"), (r"odds ratio|relative risk|hazard ratio|incidence rate", "effect-size ratio"),
    (r"early warning|prospective surveillance|syndromic|outbreak detection", "early-warning / surveillance"), (r"\bantibiogram", "antibiogram"),
    (r"spatial|geograph|hotspot|moran|kernel density|\bgis\b", "spatial analysis"), (r"network analysis|graph (?:model|analysis)|centrality", "network analysis"),
    (r"survey|questionnaire|likert|interview", "survey / interview"), (r"cost[- ]effective|cost[- ]benefit|return on investment|\broi\b", "cost-effectiveness"),
    (r"optimi[sz]ation|linear programming|integer programming|heuristic", "optimisation"), (r"forecast", "forecasting"), (r"principal component|factor analysis|dimensionality", "PCA / factor analysis"),
    (r"threshold|cut-?off|alert level|trigger", "threshold / trigger rule"), (r"rolling|moving average|sliding window", "rolling window"),
    (r"data envelopment|stochastic frontier", "efficiency frontier"), (r"fuzzy|analytic hierarchy|\bahp\b|multi-criteria|mcda", "multi-criteria decision"),
]
_METHOD_RX = [(re.compile(r"(?<![A-Za-z])(?:" + rx + ")", re.I), name) for rx, name in METHOD_LEXICON]

_CUE_AIM = re.compile(r"\b(aim|aims|aimed|objective|objectives|purpose|we propose|we present|we develop|we introduce|we describe|this (?:study|paper|article|work|review)|"
                      r"we (?:investigate|examine|evaluate|assess|compare|test|explore)|investigat)", re.I)
_CUE_METHOD = re.compile(r"\b(using|based on|we (?:used|applied|developed|built|fitted|calculated|computed|estimated|analy[sz]ed)|methods?|algorithm|model|approach|"
                         r"framework|implemented|derived|calculated|defined as|computed)\b", re.I)
_CUE_RESULT = re.compile(r"\b(results?|found|showed|shows|demonstrat|conclusion|conclude|revealed|outperform|improved|reduced|increase|decrease|associated|detect|accuracy)\w*", re.I)
_CUE_MEASURE = re.compile(r"\b(measur|predict|estimat|detect|forecast|quantif|assess|identif|monitor|classif|score|index|risk|rate|prevalence|incidence|trend|signal|alert)\w*", re.I)
_CUE_INPUT = re.compile(r"\b(based on|using|derived from|calculated|defined as|ratio|proportion|per \d|rate|score|index|threshold|window|variables?|features?|"
                        r"data (?:from|on)|records?|measured|covariates?|predictors?|indicators?)\b", re.I)
_CUE_LIMIT = re.compile(r"\b(limitation|limited|however|only|small sample|small numbers|retrospective|single[- ]cent|not generali[sz]|further (?:research|work|studies)|"
                        r"bias|confound|cannot|may not|future work|validation (?:is )?needed)\b", re.I)
_LABEL = re.compile(r"^(?:background|objectives?|purpose|aims?|introduction|methods?|design|results?|findings|conclusions?|interpretation|context|importance|setting)\s*[:.]?\s*", re.I)


def _plain(s: str) -> str:
    return _LABEL.sub("", s).strip()


def abstract_sentences(abstract: str) -> list[str]:
    # structured abstracts glue headings on ("Background Antibiotic ... Methods We ..."): split before known headings
    t = re.sub(r"(?<=[a-z0-9.)])\s+(?=(?:Background|Objectives?|Purpose|Methods|Results|Conclusions?|Findings|Interpretation|Introduction)\b[:\s])", ". ", abstract)
    sents = [s for s in split_sentences(t) if len(s.split()) >= 4 and not re.search(r"©|copyright|all rights reserved|published by|licen[sc]e", s, re.I)]
    return sents


def _overlap(sentence: str, wanted: set[str]) -> float:
    st = {stem(t) for t in tokens(sentence) if t not in STOP}
    return len(st & wanted) / (len(st) ** 0.5 or 1)


def pick(sents: list[str], rx: re.Pattern, wanted: set[str], n: int = 1, exclude: set[int] = frozenset()) -> list[int]:
    scored = []
    for i, s in enumerate(sents):
        if i in exclude:
            continue
        hits = len(rx.findall(s))
        if hits:
            scored.append((hits + _overlap(s, wanted), -i, i))
    scored.sort(reverse=True)
    return [i for _, _, i in scored[:n]]


def brief_terms(plan: QueryPlan) -> set[str]:
    return {stem(t) for ph, _ in plan.phrases for t in tokens(ph) if t not in STOP}


def summary_sentences(abstract: str, wanted: set[str]) -> list[str]:
    sents = abstract_sentences(abstract)
    if len(sents) <= 3:
        return [_plain(s) for s in sents]
    idx = set(pick(sents, _CUE_AIM, wanted, 1)) or {0}
    idx |= set(pick(sents, _CUE_METHOD, wanted, 1, exclude=idx))
    idx |= set(pick(sents, _CUE_RESULT, wanted, 1, exclude=idx))
    chosen = sorted(idx)[:3]
    while len(chosen) < 3:
        nxt = next((i for i in range(len(sents)) if i not in chosen), None)
        if nxt is None:
            break
        chosen = sorted(chosen + [nxt])
    return [_plain(sents[i]) for i in chosen]


def method_terms(text: str) -> list[str]:
    seen, out = set(), []
    for rx, name in _METHOD_RX:
        if rx.search(text) and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def measured_sentences(abstract: str, wanted: set[str], avoid: Iterable[str] = ()) -> list[str]:
    """Sentences that say what is measured or predicted; the ones already shown in the summary are used only if nothing else fits."""
    sents = abstract_sentences(abstract)
    shown = set(avoid)
    used = {i for i, s in enumerate(sents) if _plain(s) in shown}
    idx = pick(sents, _CUE_MEASURE, wanted, 2, exclude=used) or pick(sents, _CUE_MEASURE, wanted, 2)
    return [_plain(sents[i]) for i in sorted(idx)]


def input_sentences(abstract: str, wanted: set[str]) -> list[str]:
    sents = abstract_sentences(abstract)
    idx = pick(sents, _CUE_INPUT, wanted, 2)
    return [_plain(sents[i]) for i in sorted(idx)]


def limit_notes(p: Paper) -> list[str]:
    notes = [f"Stated in the abstract: \"{_plain(s)}\"" for s in [abstract_sentences(p.abstract)[i] for i in pick(abstract_sentences(p.abstract), _CUE_LIMIT, set(), 2)]]
    if p.kind == "preprint":
        notes.append("Preprint: not peer-reviewed at the time of indexing; check whether a published version exists.")
    if is_review(p):
        notes.append("Survey/review: it tells you what methods exist and how well they work, it is not itself a method to implement.")
    if p.cited_by < 10:
        notes.append(f"Only {p.cited_by} citations in OpenAlex/Semantic Scholar: recent or niche, so less independent confirmation.")
    return notes


def pitch_lines(p: Paper) -> tuple[str, str]:
    cite = f"{author_short(p)} ({p.year or 'n.d.'})"
    link = p.link
    implements = f"Our <signal name> implements the method of {cite}, {link}. It has not been validated on the partner's data yet."
    validated = (f"Our <signal name> follows {cite}, {link}, and was checked on <N> rows of <partner sample>: <the measured result, "
                 f"only what we computed ourselves>.")
    return implements, validated


# ---------- rendering ----------

def render_card(p: Paper, plan: QueryPlan, rank_no: int, llm_sections: dict | None = None) -> str:
    wanted = brief_terms(plan)
    summ = summary_sentences(p.abstract, wanted)
    measured = measured_sentences(p.abstract, wanted, summ)
    inputs = input_sentences(p.abstract, wanted)
    terms = method_terms(p.title + ". " + p.abstract)
    impl, valid = pitch_lines(p)
    queries = sorted({h["query"] for h in p.hits})
    L: list[str] = []
    L.append(f"# {p.title}")
    L.append("")
    L.append(f"**Rank {rank_no}** · relevance {p.relevance:.2f} · score {p.score:.2f} · {p.cited_by} citations · "
             f"{'review/survey' if is_review(p) else p.kind} · found by {', '.join(sorted(p.sources))}")
    L.append("")
    L.append("## Citation")
    L.append("")
    L.append(apa_citation(p))
    L.append("")
    L.append(f"- DOI / link: {p.link or 'none found'}")
    L.append(f"- Open-access copy: {p.oa_url or 'none found (the abstract above is all we have; ask the library or an author for the PDF)'}")
    L.append(f"- Badge text: `Based on: {author_short(p)} ({p.year or 'n.d.'})`")
    L.append("")
    L.append("## Summary")
    L.append("")
    L.append("> Sentences copied from the abstract, not paraphrased; we have not read the full paper." if p.abstract else "> No abstract available.")
    L.append("")
    L.append(" ".join(summ) if summ else "_No abstract._")
    if p.tldr:
        L.append("")
        L.append(f"_Semantic Scholar's automatic one-liner:_ {p.tldr}")
    L.append("")
    L.append("## What it measured / predicts")
    L.append("")
    if measured:
        L.append("From the abstract: " + " ".join(measured))
    else:
        L.append("Not stated in the abstract. Read the methods section before you claim what it measures.")
    L.append("")
    L.append("## Signals or formula we could compute from public or partner data")
    L.append("")
    if llm_sections and llm_sections.get("signals"):
        L.append("_Draft by a language model from the abstract, check the paper before you build or claim anything._")
        L.append("")
        L.append(llm_sections["signals"].strip())
        L.append("")
        L.append("Rule-based cross-check (from the abstract text):")
    else:
        L.append("_Rule-based pointers from the abstract text, not a reading of the paper._")
    L.append("")
    L.append("- Method vocabulary in the abstract: " + (", ".join(terms) if terms else "none of the usual method terms matched, read the methods section"))
    for s in inputs:
        L.append(f"- Sentence naming inputs or outputs: \"{s}\"")
    L.append("- To make it a signal: (1) map each input above to a column in the data we are given; (2) read the paper's methods for the exact "
             "formula and thresholds; (3) compute it on the sample and show the number in the app.")
    L.append("")
    L.append("## Limits")
    L.append("")
    for n in limit_notes(p):
        L.append(f"- {n}")
    L.append("- We only read the abstract. The paper's population, setting and definitions may differ from the partner's data.")
    L.append("")
    L.append("## Ready-to-paste pitch line")
    L.append("")
    L.append("Use the first line until the signal has been run on real data; use the second only after, with numbers we computed.")
    L.append("")
    L.append(f"- Implements: {impl}")
    L.append(f"- Validated: {valid}")
    L.append("")
    L.append("## Honesty level")
    L.append("")
    L.append("- [ ] implements (code follows the method, not tested on partner data)")
    L.append("- [ ] validated on <sample name, N rows, what was compared>")
    L.append("")
    L.append(f"<sub>Surfaced by: {'; '.join(queries[:4])}{' ...' if len(queries) > 4 else ''}</sub>")
    L.append("")
    return "\n".join(L)


def render_index(top: list[Paper], slugs: dict[int, str], plan: QueryPlan, meta: dict, brief: str) -> str:
    L = ["# Literature for the brief", ""]
    first = next((ln.strip(" #*") for ln in brief.splitlines() if ln.strip()), "")
    L.append(f"Brief: **{first}**  ")
    L.append(f"Run: {meta['date']} · years {meta['years']} · {meta['plan_method']} · {meta['candidates']} hits -> {meta['unique']} unique papers")
    L.append("")
    L.append("Queries: " + "; ".join(f"`{q['text']}`" for q in meta["queries"]) + (f"; semantic: _{meta['semantic'][:120]}_" if meta["semantic"] else ""))
    L.append("")
    srcs = meta["sources"]
    oa = srcs["openalex"]
    L.append(f"Sources: OpenAlex ({oa['calls']} calls, {oa['cached']} from cache{', ' + oa['budget'] if oa['budget'] else ''})"
             + (f"; Semantic Scholar ({srcs['semantic_scholar']['calls']} calls)" if not srcs["semantic_scholar"].get("skipped") else "; Semantic Scholar skipped"))
    errs = oa["errors"] + srcs["semantic_scholar"].get("errors", [])
    if errs:
        L.append("")
        L.append("Warnings: " + " | ".join(dict.fromkeys(e[:160] for e in errs)))
    L.append("")
    L.append("| # | Paper | Year | Cites | Open access | Relevance | Method terms | Card |")
    L.append("|--:|---|--:|--:|:-:|--:|---|---|")
    for i, p in enumerate(top, 1):
        terms = ", ".join(method_terms(p.title + ". " + p.abstract)[:3]) or "-"
        kind = " (review)" if is_review(p) else ""
        title = p.title.replace("|", "/")
        L.append(f"| {i} | {author_short(p)}: {title[:95]}{'...' if len(title) > 95 else ''}{kind} | {p.year or ''} | {p.cited_by} | "
                 f"{'yes' if p.oa_url else 'no'} | {p.relevance:.2f} | {terms} | [{slugs[i]}]({slugs[i]}.md) |")
    L.append("")
    L.append("## How to pick one (10 minutes)")
    L.append("")
    L.append("1. Which of these needs only columns the partner actually gives us? Open the card's \"Signals\" section and map inputs to columns.")
    L.append("2. Which gives a number or a flag a judge can see on screen in one glance?")
    L.append("3. Can we compute it and test it on the partner sample before the demo? If not, we say \"implements\", never \"validated\".")
    L.append("")
    L.append("Relevance is a heuristic (rank fusion over the queries + how many subject phrases the title/abstract contain). "
             "It finds candidates, it does not judge fit: read the abstract of your top two before choosing.")
    L.append("")
    return "\n".join(L)


def write_cards(top: list[Paper], ranked: list[Paper], plan: QueryPlan, meta: dict, out: Path, brief: str, use_llm: bool = True, log=print) -> None:
    from . import llm
    out.mkdir(parents=True, exist_ok=True)
    cards_dir = out
    for old in cards_dir.glob("*.md"):
        old.unlink()  # a re-run replaces the previous set; stale cards would mislead
    used: set[str] = set()
    slugs: dict[int, str] = {}
    for i, p in enumerate(top, 1):
        slugs[i] = make_slug(p, used)
        sections = None
        if use_llm and llm.available():
            try:
                sections = llm.draft_sections(p, brief)
            except Exception as e:
                log(f"LLM draft failed for card {i} ({type(e).__name__}); using rule-based text")
        (cards_dir / f"{slugs[i]}.md").write_text(render_card(p, plan, i, sections), encoding="utf-8")
    (cards_dir / "INDEX.md").write_text(render_index(top, slugs, plan, meta, brief), encoding="utf-8")
