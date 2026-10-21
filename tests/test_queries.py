import re

from rg.queries import (clean_sentence, extract_queries, parse_user_keywords, pick_facets, rank_phrases)

HACKATHON_WORDS = {"challenge", "hackathon", "participants", "prototype", "solution", "users", "build", "team", "teams"}


def words(plan):
    return {w for q in plan.queries for w in re.findall(r"[a-z\-]+", q.text.lower())}


def test_between_three_and_six_queries(brief_amr, brief_if):
    for b in (brief_amr, brief_if):
        plan = extract_queries(b)
        assert 3 <= len(plan.queries) <= 6


def test_no_hackathon_words_in_queries(brief_amr, brief_if):
    for b in (brief_amr, brief_if):
        assert not (words(extract_queries(b)) & HACKATHON_WORDS)


def test_subject_phrases_come_from_the_brief(brief_amr):
    plan = extract_queries(brief_amr)
    joined = " ".join(q.text for q in plan.queries)
    assert "antibiotic resistance" in joined
    assert plan.subject == "antibiotic resistance"


def test_detection_and_uncertainty_facets_for_surveillance_brief(brief_amr):
    plan = extract_queries(brief_amr)
    assert plan.facets[0] == "detection"
    assert any("detection" in s for s in plan.semantic_extra)
    assert all("{S}" not in s for s in plan.semantic_extra)


def test_user_keywords_come_first_and_are_kept_verbatim(brief_amr):
    plan = extract_queries(brief_amr, keywords=['"cumulative antibiogram"', "CUSUM control chart"])
    assert [q.kind for q in plan.queries[:2]] == ["user", "user"]
    assert plan.queries[0].text == '"cumulative antibiogram"'
    assert plan.method == "rake+user"
    assert any(q.kind == "phrase" for q in plan.queries), "brief-derived queries must still fill the remaining slots"


def test_parse_user_keywords_splits_commas_and_semicolons():
    assert parse_user_keywords(["a b, c d; e"]) == ["a b", "c d", "e"]
    assert parse_user_keywords(None) == []
    assert parse_user_keywords("x") == ["x"]


def test_acronyms_survive():
    brief = "ESBL producing bacteria on the ward. We track ESBL rates and ICU stays.\n\nThe challenge is to build a tool."
    texts = " ".join(p for p, _, _ in rank_phrases(brief))
    assert "esbl" in texts


def test_semantic_sentence_is_clean_and_bounded(brief_if):
    plan = extract_queries(brief_if)
    assert 0 < len(plan.semantic) <= 420
    assert not plan.semantic.lower().startswith("your challenge")
    assert "\n" not in plan.semantic


def test_clean_sentence_removes_boilerplate():
    assert clean_sentence("Your challenge is to build a rolling antibiogram.") == "A rolling antibiogram."
    assert clean_sentence("We would like you to design a nudge for movers.") == "A nudge for movers."


def test_facets_need_two_hits_beyond_the_first():
    f = pick_facets("Forecast demand and predict load. Maybe some behaviour.")
    assert [x[0] for x in f] == ["prediction"]


def test_deterministic(brief_amr):
    a, b = extract_queries(brief_amr), extract_queries(brief_amr)
    assert [q.text for q in a.queries] == [q.text for q in b.queries] and a.semantic == b.semantic


def test_tiny_or_odd_input_does_not_crash():
    for text in ("x", "AI AI AI", "   \n\n", "1234 5678", "Hyvää päivää, tämä on suomenkielinen haaste sairaalan infektioista."):
        plan = extract_queries(text)
        assert isinstance(plan.queries, list)


def test_finnish_stopwords_are_ignored():
    plan = extract_queries("Sairaalan infektioiden seuranta ja antibioottiresistenssi. Antibioottiresistenssi on kasvava ongelma, ja sairaalan seuranta on vaikeaa.")
    assert not (words(plan) & {"ja", "on", "ei"})


def test_user_keywords_become_the_subject_and_get_semantic_queries(brief_if):
    plan = extract_queries(brief_if, keywords=['"residential relocation"', "home injury prevention"])
    assert plan.subject == "residential relocation"
    assert plan.semantic_extra[:2] == ["residential relocation", "home injury prevention"]
    assert any("residential relocation" in s for s in plan.semantic_extra[2:])  # facets are built around the user's subject
