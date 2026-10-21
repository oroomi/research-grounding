"""Print the badge HTML for one paper from a finder run, ready to paste into the app.

    python3 -m rg.badge cards/results.json --rank 3 --method "Flags a ward when ..." [--validated "2,310 isolates, 6 wards"]

Without --validated the badge says "implements". The sample text is yours to write and must describe what you actually ran.
"""
from __future__ import annotations

import argparse
import html
import json
import sys

from .cards import author_short
from .model import Paper


def paper_from_dict(d: dict) -> Paper:
    keys = {"title", "year", "authors", "venue", "doi", "url", "oa_url", "abstract", "cited_by", "kind"}
    return Paper(**{k: v for k, v in d.items() if k in keys})


def badge_html(p: Paper, method: str, validated_sample: str = "") -> str:
    a = lambda s: html.escape(str(s), quote=True)
    level = "validated" if validated_sample.strip() else "implements"
    attrs = [f'data-author="{a(author_short(p))}"', f'data-year="{a(p.year or "")}"', f'data-url="{a(p.link)}"',
             f'data-title="{a(p.title)}"', f'data-method="{a(method)}"', f'data-level="{level}"']
    if level == "validated":
        attrs.append(f'data-sample="{a(validated_sample.strip())}"')
    return '<span class="based-on" ' + " ".join(attrs) + "></span>"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rg.badge", description=__doc__.split("\n\n")[0])
    ap.add_argument("results", help="results.json written by rg.find (in the cards directory)")
    ap.add_argument("--rank", type=int, required=True, help="rank in INDEX.md (1 = best)")
    ap.add_argument("--method", required=True, help="one line: what WE compute from this paper")
    ap.add_argument("--validated", default="", help='only after testing: "what sample, how many rows, what was checked"')
    a = ap.parse_args(argv)
    data = json.load(open(a.results, encoding="utf-8"))
    if not 1 <= a.rank <= len(data["top"]):
        print(f"rank must be 1..{len(data['top'])}", file=sys.stderr)
        return 2
    print(badge_html(paper_from_dict(data["top"][a.rank - 1]), a.method, a.validated))
    return 0


if __name__ == "__main__":
    sys.exit(main())
