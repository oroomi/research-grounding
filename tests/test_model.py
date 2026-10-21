import json

from rg.find import ABSTRACT_KEEP
from rg.model import Paper, norm_doi, norm_title, scrub_emails, shorten


def test_norm_doi_strips_prefixes_case_and_trailing_punctuation():
    assert norm_doi("https://doi.org/10.1000/ABC.") == "10.1000/abc"
    assert norm_doi("doi: 10.1/x") == "10.1/x"
    assert norm_doi(None) == ""


def test_norm_title_ignores_case_markup_and_punctuation():
    assert norm_title("Cats & <i>Dogs</i>: A Study!") == "cats and dogs a study"
    assert norm_title("") == ""


def test_emails_are_scrubbed_from_abstracts_at_construction():
    p = Paper(title="t", abstract="Data are available from the PI (jane.doe+x@uni-example.ac.uk) or john.q@mail.example.com.")
    assert "@" not in p.abstract and p.abstract.count("[email removed]") == 2
    assert scrub_emails(None) == ""
    assert scrub_emails("a venue named TRAP@NCI stays") == "a venue named TRAP@NCI stays"  # no domain dot: not an address


def test_shorten_cuts_at_a_sentence_end_and_marks_the_cut():
    text = "First sentence is here. " * 30
    out = shorten(text, 100)
    assert out == "First sentence is here. " * 3 + "First sentence is here. [...]"
    assert len(out) <= 100 + len(" [...]")
    assert shorten("short", 100) == "short"
    assert shorten("x" * 300, 100) == "x" * 100 + " [...]"  # no space to cut at: hard cut


def test_to_dict_limit_only_touches_the_abstract():
    p = Paper(title="t", abstract="word " * 1000, doi="10.1/x")
    full, short = p.to_dict(), p.to_dict(200)
    assert len(full["abstract"]) == 5000 and len(short["abstract"]) <= 207 and short["abstract"].endswith("[...]")
    assert {k: v for k, v in full.items() if k != "abstract"} == {k: v for k, v in short.items() if k != "abstract"}
    assert json.dumps(short)  # serialisable


def test_saved_results_keep_only_a_snippet_of_long_abstracts():
    assert 500 <= ABSTRACT_KEEP <= 3000
