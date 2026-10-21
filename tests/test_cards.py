import json

from rg import llm
from rg.cards import (abstract_sentences, apa_citation, author_short, brief_terms, input_sentences, limit_notes, make_slug, measured_sentences,
                      method_terms, pitch_lines, render_card, render_index, split_name, summary_sentences, write_cards)
from rg.model import Paper
from rg.queries import extract_queries
from rg.sources import parse_openalex_work

ABSTRACT = ("BACKGROUND Surveillance of antimicrobial resistance needs timely alarms. METHODS We applied a CUSUM control chart to monthly counts of resistant "
            "isolates per ward, using a Poisson baseline estimated from the previous 24 months. RESULTS The chart flagged 4 of 5 known clusters, and the "
            "median delay was 2 weeks. However, only one hospital was studied and the data were retrospective. CONCLUSIONS CUSUM based alarms can support "
            "infection control teams.")


def paper(**kw):
    d = dict(title="Timely alarms for resistance on hospital wards", year=2018, authors=["Jane Q. Smith", "Pekka Virtanen", "Anna de la Cruz"],
             venue="Journal of Hospital Infection", doi="10.1/abc", abstract=ABSTRACT, cited_by=120, oa_url="https://oa.example/p.pdf")
    d.update(kw)
    p = Paper(**d)
    p.hits = [{"source": "openalex", "query": "resistance trend detection", "kind": "phrase", "rank": 1, "weight": 1.0}]
    p.sources = {"openalex"}
    return p


def test_split_name_handles_particles_and_comma_form():
    assert split_name("Anna de la Cruz") == ("Anna", "de la Cruz")
    assert split_name("van der Berg, Jan") == ("Jan", "van der Berg")
    assert split_name("Madonna") == ("", "Madonna")


def test_author_short_one_two_many():
    assert author_short(paper(authors=["A Smith"])) == "Smith"
    assert author_short(paper(authors=["A Smith", "B Jones"])) == "Smith & Jones"
    assert author_short(paper()) == "Smith et al."
    assert author_short(paper(authors=[])) == "Unknown author"


def test_apa_citation_has_year_title_venue_and_doi():
    c = apa_citation(paper())
    assert c.startswith("Smith, J. Q., Virtanen, P., & de la Cruz, A. (2018). Timely alarms")
    assert "*Journal of Hospital Infection*" in c and c.endswith("https://doi.org/10.1/abc")
    assert ".." not in c


def test_slug_is_ascii_and_unique():
    used = set()
    a = make_slug(paper(authors=["Åsa Öberg"], title="Älä pelkää: ‘tests’ & more"), used)
    b = make_slug(paper(authors=["Åsa Öberg"], title="Älä pelkää: ‘tests’ & more"), used)
    assert a.isascii() and a != b and b.endswith("-2")


def test_abstract_sentences_split_structured_headings():
    sents = abstract_sentences(ABSTRACT)
    assert len(sents) == 5  # five sentences, one per structured heading plus the "However" sentence
    assert sents[1].startswith("METHODS We applied") and sents[2].startswith("RESULTS")


def test_summary_is_extractive_three_sentences_with_aim_method_result():
    plan = extract_queries("Resistance trend detection on hospital wards. We need ward level surveillance.")
    from rg.cards import brief_terms
    s = summary_sentences(ABSTRACT, brief_terms(plan))
    assert len(s) == 3
    joined = " ".join(s)
    assert "CUSUM" in joined and "flagged" in joined  # method sentence and result sentence made it
    for sent in s:
        assert sent.rstrip(".") in ABSTRACT.replace("BACKGROUND ", "").replace("METHODS ", "").replace("RESULTS ", "").replace("CONCLUSIONS ", "")


def test_method_terms_and_input_sentences():
    t = method_terms("A CUSUM control chart on Poisson counts with a Bayesian baseline and rolling windows")
    assert {"CUSUM", "control chart / SPC", "Poisson model", "Bayesian", "rolling window"} <= set(t)
    ins = input_sentences(ABSTRACT, set())
    assert ins and any("Poisson baseline" in s or "monthly counts" in s for s in ins)


def test_method_terms_ignore_everyday_words_that_are_not_methods():
    # "matching", "sensitivity", "precision" alone are ordinary words; only the statistical phrases count
    plain = method_terms("Matching the right nurse to a task needs precision, and the sensitivity of the staff matters.")
    assert "propensity / matching" not in plain and "sensitivity / specificity / AUC" not in plain
    assert "propensity / matching" in method_terms("We built a matched cohort and a propensity score.")
    assert "sensitivity / specificity / AUC" in method_terms("Sensitivity and specificity were 0.9 and 0.8.")
    assert "sensitivity / specificity / AUC" in method_terms("Precision/recall and the ROC curve were reported.")


def test_method_terms_know_plain_machine_learning():
    assert "machine learning" in method_terms("This paper develops a machine-learning model to predict startup exits.")
    assert "machine learning" in method_terms("A supervised learning classifier was trained on 10,000 firms.")
    assert method_terms("Founders talk about machines and learning separately.") == []


def test_method_terms_only_match_at_a_word_start():
    # "enrolling" must not look like a rolling window, "pharmacox" must not look like a Cox model
    assert "rolling window" not in method_terms("Patients were enrolling slowly at the site.")
    assert "rolling window" in method_terms("A rolling 12-month window was used.")
    assert "survival analysis" not in method_terms("The pharmacox trial reported nothing else.")
    assert "survival analysis" in method_terms("A Cox model and Kaplan-Meier curves were fitted.")
    # alternatives inside one pattern share the guard: "cumulative sum" in the middle of a word does not count either
    assert "CUSUM" not in method_terms("the supercumulative sumo league")
    assert "CUSUM" in method_terms("The cumulative sum chart flagged it.")


READMIT = ("We propose a score that predicts hospital readmission risk. The model was built on discharge records using logistic regression. "
           "Results showed that the risk score identified high-risk patients early. The estimate of readmission rate was stable across sites.")


def test_measured_sentences_prefer_sentences_not_already_in_the_summary():
    wanted = brief_terms(extract_queries("Readmission risk prediction in hospitals."))
    shown = summary_sentences(READMIT, wanted)
    fresh = measured_sentences(READMIT, wanted, shown)
    assert fresh and not set(fresh) & set(shown)
    # with nothing else to say, a summary sentence is reused rather than leaving the section empty
    only = "We propose a score that predicts readmission risk. Thanks to everybody involved in this long running project."
    assert measured_sentences(only, set(), ["We propose a score that predicts readmission risk."]) == ["We propose a score that predicts readmission risk."]
    assert measured_sentences("Nothing relevant is stated in this short text.", set()) == []


def test_card_does_not_repeat_summary_sentences_under_what_it_measured():
    plan = extract_queries("Readmission risk prediction in hospitals.")
    card = render_card(paper(abstract=READMIT), plan, 1)
    summary = card.split("## Summary")[1].split("## What it measured")[0]
    measured = card.split("## What it measured")[1].split("## Signals")[0]
    assert "From the abstract:" in measured
    for sent in summary_sentences(READMIT, brief_terms(plan)):
        assert sent in summary and sent not in measured


def test_card_reuses_a_summary_sentence_when_it_is_the_only_one_that_fits():
    plan = extract_queries("Resistance trend detection on hospital wards. Ward level antibiogram.")
    card = render_card(paper(), plan, 1)  # ABSTRACT has a single sentence with measurement words
    measured = card.split("## What it measured")[1].split("## Signals")[0]
    assert "CUSUM control chart to monthly counts" in measured


def test_limits_quote_the_abstract_and_flag_preprints_and_low_citations():
    notes = limit_notes(paper(kind="preprint", cited_by=2))
    text = " ".join(notes)
    assert "only one hospital" in text.lower() and "Preprint" in text and "2 citations" in text


def test_pitch_line_defaults_to_implements_never_validated():
    impl, valid = pitch_lines(paper())
    assert "implements" in impl and "Smith et al. (2018)" in impl and "https://doi.org/10.1/abc" in impl and "not been validated" in impl
    assert "<partner sample>" in valid and "<N>" in valid  # placeholders: the numbers must be ours


def test_render_card_sections_and_honesty():
    plan = extract_queries("Resistance trend detection on hospital wards. Ward level antibiogram.")
    card = render_card(paper(), plan, 1)
    for h in ("# Timely alarms", "## Citation", "## Summary", "## What it measured", "## Signals or formula", "## Limits",
              "## Ready-to-paste pitch line", "## Honesty level"):
        assert h in card
    assert "Based on: Smith et al. (2018)" in card
    assert "copied from the abstract" in card and "[x]" not in card  # no honesty box is pre-ticked
    assert "Draft by a language model" not in card


def test_render_card_without_abstract_does_not_crash():
    plan = extract_queries("Resistance trend detection on hospital wards.")
    card = render_card(paper(abstract="", oa_url=""), plan, 3)
    assert "No abstract" in card and "none found" in card


def test_llm_sections_are_labelled_draft(monkeypatch):
    plan = extract_queries("Resistance trend detection on hospital wards.")
    card = render_card(paper(), plan, 1, {"signals": "- monthly resistant share per ward"})
    assert "Draft by a language model" in card and "check the paper" in card and "monthly resistant share per ward" in card


def test_write_cards_creates_index_and_replaces_stale_cards(tmp_path, monkeypatch):
    plan = extract_queries("Resistance trend detection on hospital wards. Ward level antibiogram.")
    (tmp_path / "old-card.md").write_text("stale")
    meta = {"date": "2026-10-18", "years": "2010-2026", "plan_method": "keyword extraction", "candidates": 5, "unique": 3,
            "queries": [{"kind": "phrase", "text": "x"}], "semantic": "", "sources": {"openalex": {"calls": 1, "cached": 0, "errors": [], "budget": ""},
                                                                                        "semantic_scholar": {"skipped": True}}}
    ps = [paper(), paper(title="Second paper on wards", doi="10.1/b", authors=["Li Wei"])]
    write_cards(ps, ps, plan, meta, tmp_path, "Brief title\nbody", use_llm=False)
    files = sorted(f.name for f in tmp_path.glob("*.md"))
    assert "INDEX.md" in files and "old-card.md" not in files and len(files) == 3
    index = (tmp_path / "INDEX.md").read_text()
    assert "| 1 |" in index and "| 2 |" in index and "Semantic Scholar skipped" in index and "Brief title" in index


def test_index_lists_warnings_once():
    plan = extract_queries("Resistance trend detection on hospital wards.")
    meta = {"date": "d", "years": "y", "plan_method": "m", "candidates": 1, "unique": 1, "queries": [], "semantic": "",
            "sources": {"openalex": {"calls": 1, "cached": 0, "errors": ["boom", "boom"], "budget": ""}, "semantic_scholar": {"skipped": True}}}
    idx = render_index([paper()], {1: "slug"}, plan, meta, "T")
    assert idx.count("boom") == 1


def test_real_fixture_papers_make_cards(oa_works):
    plan = extract_queries("Antibiotic resistance trend detection with a ward level antibiogram.")
    for w in oa_works["results"]:
        p = parse_openalex_work(w)
        p.hits = []
        card = render_card(p, plan, 1)
        assert p.title in card and "## Honesty level" in card


# ---------- optional LLM steps (mocked: no key, no network) ----------

def test_llm_plan_queries_parses_json_and_validates(monkeypatch):
    out = 'Sure!\n{"queries": ["antibiogram statistical methods", "cumulative antibiogram small samples", "CUSUM resistance surveillance", "x"], "semantic": "How can rising resistance be detected early at ward level?"}'
    monkeypatch.setattr(llm, "ask", lambda *a, **k: out)
    offline = extract_queries("Resistance trend detection on hospital wards. Ward level antibiogram.")
    plan = llm.plan_queries("brief", offline)
    assert plan.method == "llm" and [q.kind for q in plan.queries] == ["llm"] * 3  # one-word query rejected
    assert plan.semantic.startswith("How can") and len(plan.phrases) >= 3


def test_llm_plan_returns_none_when_output_is_unusable(monkeypatch):
    monkeypatch.setattr(llm, "ask", lambda *a, **k: '{"queries": ["one"]}')
    assert llm.plan_queries("b", extract_queries("Resistance trend detection on hospital wards.")) is None


def test_llm_draft_sections(monkeypatch):
    monkeypatch.setattr(llm, "ask", lambda *a, **k: json.dumps({"signals": ["monthly resistant share", "baseline from 24 months"]}))
    assert llm.draft_sections(paper(), "brief")["signals"] == "- monthly resistant share\n- baseline from 24 months"


def test_llm_ask_posts_key_in_header_only_and_reports_errors(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    seen = {}

    def fake_post(url, headers, payload, timeout=90.0):
        seen.update(url=url, headers=headers, payload=payload)
        return 200, {"content": [{"type": "text", "text": "hello"}]}

    monkeypatch.setattr(llm, "post_json", fake_post)
    assert llm.ask("sys", "user") == "hello"
    assert seen["url"].startswith("https://api.anthropic.com/") and seen["headers"]["x-api-key"] == "sk-test-not-real"
    assert "sk-test" not in json.dumps(seen["payload"]) and seen["payload"]["model"] == "claude-sonnet-5-5"
    monkeypatch.setattr(llm, "post_json", lambda *a, **k: (401, {"error": {"message": "invalid x-api-key"}}))
    try:
        llm.ask("s", "u")
        assert False
    except RuntimeError as e:
        assert "401" in str(e) and "sk-test" not in str(e)


def test_write_cards_falls_back_when_llm_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    monkeypatch.setattr(llm, "draft_sections", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    plan = extract_queries("Resistance trend detection on hospital wards.")
    meta = {"date": "d", "years": "y", "plan_method": "m", "candidates": 1, "unique": 1, "queries": [], "semantic": "",
            "sources": {"openalex": {"calls": 1, "cached": 0, "errors": [], "budget": ""}, "semantic_scholar": {"skipped": True}}}
    logs = []
    write_cards([paper()], [paper()], plan, meta, tmp_path, "T", use_llm=True, log=logs.append)
    card = next(f for f in tmp_path.glob("*.md") if f.name != "INDEX.md").read_text()
    assert "Draft by a language model" not in card and any("LLM draft failed" in m for m in logs)
