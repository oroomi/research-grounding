import json
import pathlib

import pytest

from rg import badge
from rg.model import Paper

ROOT = pathlib.Path(__file__).parent.parent


def paper():
    return Paper(title='Tricky "title" <script>', year=2011, authors=["Steffen Unkel", "Paddy Farrington", "Paul Garthwaite"], doi="10.1/x")


def test_badge_html_escapes_and_defaults_to_implements():
    h = badge.badge_html(paper(), 'one line "quoted" <b>')
    assert "<script>" not in h and "&lt;script&gt;" in h and "&quot;quoted&quot;" in h
    assert 'data-level="implements"' in h and "data-sample" not in h
    assert 'data-author="Unkel et al."' in h and 'data-year="2011"' in h and 'data-url="https://doi.org/10.1/x"' in h


def test_badge_html_validated_needs_a_sample():
    assert 'data-level="implements"' in badge.badge_html(paper(), "m", "   ")
    h = badge.badge_html(paper(), "m", "2,310 isolates, 6 wards")
    assert 'data-level="validated"' in h and 'data-sample="2,310 isolates, 6 wards"' in h


def test_badge_cli(tmp_path, capsys):
    f = tmp_path / "results.json"
    f.write_text(json.dumps({"top": [paper().to_dict()]}))
    assert badge.main([str(f), "--rank", "1", "--method", "m"]) == 0
    assert 'class="based-on"' in capsys.readouterr().out
    assert badge.main([str(f), "--rank", "2", "--method", "m"]) == 2


def test_css_has_dark_light_and_no_hardcoded_server_paths():
    css = (ROOT / "badge/based-on.css").read_text()
    assert 'data-theme="dark"' in css and "prefers-color-scheme: dark" in css and "--bo-accent" in css
    assert "/root/" not in css


@pytest.fixture(scope="module")
def page():
    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:  # browser not installed: this check is optional
            pytest.skip(f"no chromium: {e}")
        pg = browser.new_page()
        pg.goto("file://" + str(ROOT / "badge/demo.html"))
        yield pg
        browser.close()


def test_js_renders_label_author_year_and_safe_link(page):
    ref = page.locator("#b-dark .based-on__ref").inner_text()
    assert ref == "Unkel et al. (2011)"
    assert page.locator("#b-dark .based-on__label").inner_text() == "Based on:"
    href = page.locator("#b-dark a.based-on__link").get_attribute("href")
    assert href.startswith("https://doi.org/")
    assert page.locator("#b-dark a.based-on__link").get_attribute("rel") == "noopener noreferrer"


def test_js_card_opens_on_tap_and_closes_on_escape(page):
    btn = page.locator("#b-dark .based-on__info")
    btn.click()
    assert page.locator("#b-dark").get_attribute("data-open") is not None
    assert btn.get_attribute("aria-expanded") == "true"
    assert "Implements the method" in page.locator("#b-dark .based-on__level").inner_text()
    page.keyboard.press("Escape")
    assert page.locator("#b-dark").get_attribute("data-open") is None


def test_js_validated_without_sample_falls_back_and_text_is_not_html(page):
    html = page.evaluate("""() => { const e = BasedOn.create({author: '<img src=x onerror=alert(1)>', year: 2020, url: 'javascript:alert(1)',
                                    method: '<b>m</b>', level: 'validated'}); document.body.appendChild(e); return e.outerHTML; }""")
    assert "<img" not in html.replace("&lt;img", "")  # escaped
    assert 'data-level="implements"' in html  # no sample, so not "validated"
    assert "javascript:" not in html  # unsafe URL is dropped, the chip is not a link
