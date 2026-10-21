from rg.model import Paper, norm_doi, norm_title
from rg.rank import coverage, impact, is_duplicate, merge, pool_idf, rank, recency, select_top

ABS = "We study how resistance changes over time on hospital wards and propose a control chart for detecting rising trends in resistant isolates."


def P(title, doi="", year=2019, cites=10, abstract=ABS, authors=("Ann Smith",), oa="", kind="article", hits=None, source="openalex"):
    p = Paper(title=title, doi=doi, year=year, cited_by=cites, abstract=abstract, authors=list(authors), oa_url=oa, kind=kind, sources={source})
    p.hits = hits or [{"source": source, "query": "q", "kind": "phrase", "rank": 1, "weight": 1.0}]
    return p


def test_norm_doi_variants_agree():
    assert norm_doi("https://doi.org/10.1/ABC") == norm_doi("doi:10.1/abc") == norm_doi("http://dx.doi.org/10.1/abc.") == "10.1/abc"
    assert norm_doi(None) == ""


def test_norm_title_ampersand_and_punctuation():
    assert norm_title("Analysis of A & B: <i>the</i> Case") == norm_title("analysis of a and b the case")


def test_merge_dedupes_by_doi_and_keeps_richest_fields():
    a = P("Outbreak detection", doi="10.1/x", cites=5, abstract="short abstract here for test", source="openalex")
    b = P("Outbreak Detection!", doi="https://doi.org/10.1/X", cites=40, abstract=ABS, oa="https://oa.example/p.pdf", source="s2")
    b.tldr = "gist"
    out = merge([a, b])
    assert len(out) == 1
    m = out[0]
    assert m.cited_by == 40 and m.abstract == ABS and m.oa_url and m.tldr == "gist"
    assert m.sources == {"openalex", "s2"} and len(m.hits) == 2


def test_merge_dedupes_by_title_when_a_doi_is_missing():
    a = P("Analysis of Microbial Resistance and Prescription Preferences Using Antibiograms", doi="10.1/a")
    b = P("Analysis of Microbial Resistance & Prescription Preferences Using Antibiograms", doi="")
    assert len(merge([a, b])) == 1


def test_merge_treats_preprint_and_published_twin_as_one():
    pre = P("A Bayesian model for ward level resistance forecasting in hospitals", doi="10.1101/pre", year=2020, kind="preprint")
    pub = P("A Bayesian Model for Ward-Level Resistance Forecasting in Hospitals", doi="10.1/pub", year=2021, cites=12)
    # different DOIs: the DOI rule says "different", so twins are only caught when one side has no DOI
    pre.doi = ""
    out = merge([pre, pub])
    assert len(out) == 1 and out[0].doi == "10.1/pub"


def test_different_papers_with_similar_titles_are_not_merged():
    a = P("Resistance trends in hospital A", doi="10.1/a")
    b = P("Resistance trends in hospital B", doi="10.1/b")
    assert not is_duplicate(a, b) and len(merge([a, b])) == 2


def test_impact_and_recency_are_monotone_and_compressive():
    assert impact(0) == 1.0 < impact(10) < impact(1000) < 3.0
    assert recency(2026, 2026) > recency(2016, 2026) > recency(1996, 2026) >= 0.7
    assert recency(None, 2026) < 1.0


def test_relevant_paper_beats_highly_cited_irrelevant_one():
    rel = P("Control charts for detecting rising resistance on hospital wards", cites=15, hits=[
        {"source": "openalex", "query": "s", "kind": "semantic", "rank": 1, "weight": 2.5, "sim": 1.0},
        {"source": "openalex", "query": "p", "kind": "phrase", "rank": 2, "weight": 1.0}])
    irrel = P("Mechanisms of everything in biology", abstract="A broad survey of molecular mechanisms in cells and tissues across many organisms.",
              cites=5000, hits=[{"source": "openalex", "query": "p", "kind": "phrase", "rank": 1, "weight": 1.0}])
    ranked = rank([irrel, rel], [("resistance trends", 1.0), ("control chart", 0.8)], now_year=2026)
    assert ranked[0] is rel


def test_citations_and_recency_break_ties_between_equally_relevant():
    hit = [{"source": "openalex", "query": "p", "kind": "phrase", "rank": 1, "weight": 1.0}]
    old_low = P("Control charts for resistance on wards", year=2005, cites=3, hits=list(hit))
    new_high = P("Control charts for resistance on wards II", year=2022, cites=200, hits=list(hit))
    assert rank([old_low, new_high], [("control chart", 1.0)], now_year=2026)[0] is new_high


def test_open_access_bonus_and_missing_abstract_penalty():
    hit = [{"source": "openalex", "query": "p", "kind": "phrase", "rank": 1, "weight": 1.0}]
    a = P("Control charts for resistance", oa="https://oa", hits=list(hit))
    b = P("Control charts for resistance two", hits=list(hit))
    c = P("Control charts for resistance three", abstract="", hits=list(hit))
    r = rank([b, c, a], [("control chart", 1.0)], now_year=2026)
    assert r[0] is a and r[-1] is c


def test_idf_makes_rare_words_count_more():
    common = [P(f"resistance study {i}", abstract="resistance in hospitals " + ("cusum" if i == 0 else "")) for i in range(20)]
    idf = pool_idf(common)
    assert idf["cusum"] > 2 * idf["hospital"]  # present in 1 of 20 versus 20 of 20
    with_rare, without = common[0], common[1]
    cov_rare = coverage(with_rare, [("resistance cusum", 1.0)], idf)
    cov_plain = coverage(without, [("resistance cusum", 1.0)], idf)
    assert cov_rare > 0.9 and cov_plain < 0.5


def test_select_top_caps_reviews():
    ps = [P(f"A systematic review of topic {i}", kind="review") for i in range(5)] + [P(f"Method paper {i}") for i in range(5)]
    for i, p in enumerate(ps):
        p.score = 10 - i * 0.1
    top = select_top(ps, 6, max_reviews=2)
    assert len(top) == 6 and sum(1 for p in top if "review" in p.title) == 2
