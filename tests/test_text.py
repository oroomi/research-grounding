from rg.text import reconstruct_abstract, split_sentences, stem, stems, strip_markup


def test_reconstruct_orders_words_by_position():
    inv = {"world": [1, 5], "Hello": [0], "again": [6], "my": [4], "dear": [3], ",": [2]}
    # position 2 is a comma token placed with a space before it by naive joining; punctuation is tightened
    assert reconstruct_abstract(inv) == "Hello world, dear my world again"


def test_reconstruct_handles_empty_and_none():
    assert reconstruct_abstract(None) == ""
    assert reconstruct_abstract({}) == ""
    assert reconstruct_abstract({"x": []}) == ""


def test_reconstruct_strips_markup_and_abstract_prefix():
    inv = {"Abstract": [0], "<jats:p>We": [1], "measured": [2], "resistance.</jats:p>": [3]}
    assert reconstruct_abstract(inv) == "We measured resistance."


def test_reconstruct_gaps_and_duplicate_positions_do_not_crash():
    inv = {"a": [0, 10], "b": [10], "c": [3]}
    out = reconstruct_abstract(inv)
    assert out.startswith("a c")
    assert len(out.split()) == 3  # position 10 appears once


def test_reconstruct_real_fixture(oa_works):
    for w in oa_works["results"]:
        text = reconstruct_abstract(w["abstract_inverted_index"])
        assert len(text) > 200
        assert "  " not in text
        n_positions = len({p for ps in w["abstract_inverted_index"].values() for p in ps})
        assert len(text.split()) >= n_positions * 0.9  # almost every position became a word


def test_split_sentences_keeps_abbreviations_together():
    s = split_sentences("We followed Smith et al. (2019) and used e.g. a CUSUM chart. The rate was 3.5 per 1000. J. K. Rowling agreed.")
    assert len(s) == 3
    assert s[0].startswith("We followed Smith et al.")
    assert "3.5 per 1000" in s[1]


def test_stem_is_light_and_consistent():
    assert stem("resistances") == stem("resistance")
    assert stem("detecting") == stem("detect")
    assert stem("ice") == "ice"
    assert stem("analysis") == "analysis"  # -is is not a plural
    assert "ward" in stems("Wards and the ward")


def test_strip_markup():
    t = strip_markup("See [the docs](https://x.org/a) or https://y.org and mail a@b.com <b>bold</b>")
    assert "http" not in t and "@" not in t and "<b>" not in t and "the docs" in t
