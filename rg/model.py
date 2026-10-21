"""The one record type shared by every module."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


def norm_doi(doi: str | None) -> str:
    if not doi:
        return ""
    d = doi.strip().lower()
    d = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", d)
    d = re.sub(r"^doi:\s*", "", d)
    return d.strip().rstrip(".,;")


def norm_title(title: str | None) -> str:
    t = (title or "").lower()
    t = re.sub(r"<[^>]+>", " ", t).replace("&", " and ")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


EMAIL_RX = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def scrub_emails(text: str | None) -> str:
    """Abstracts sometimes carry authors' contact addresses; they are personal data and of no use here."""
    return EMAIL_RX.sub("[email removed]", text or "")


def shorten(text: str, limit: int) -> str:
    """Cut at a sentence end (or a space) before `limit` characters and mark the cut."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    if end > limit * 0.6:
        cut = cut[:end + 1]
    elif " " in cut:
        cut = cut[:cut.rfind(" ")]
    return cut.rstrip() + " [...]"


@dataclass
class Paper:
    title: str
    year: int | None = None
    authors: list[str] = field(default_factory=list)  # "Given Family", as the source gave them
    venue: str = ""
    doi: str = ""  # normalised: lower case, no https://doi.org/ prefix
    url: str = ""  # landing page (doi.org link if there is a DOI)
    oa_url: str = ""  # open-access full text or landing page, "" if none known
    abstract: str = ""
    cited_by: int = 0
    kind: str = "article"  # source work type: article | review | preprint | book-chapter | ...
    tldr: str = ""  # Semantic Scholar's machine-written one-liner, if any
    sources: set[str] = field(default_factory=set)
    hits: list[dict] = field(default_factory=list)  # {"source","query","kind","rank","weight"}
    ids: dict = field(default_factory=dict)  # {"openalex": "W..", "s2": ".."}
    sim: float = 0.0  # best normalised semantic-search similarity (0..1), 0 if never found by semantic search
    raw_score: float | None = None  # engine score of the query that returned this record (only meaningful for semantic search)
    # filled by the ranker
    rrf: float = 0.0
    coverage: float = 0.0
    relevance: float = 0.0
    score: float = 0.0

    def __post_init__(self):
        self.abstract = scrub_emails(self.abstract)

    @property
    def key(self) -> str:
        return self.doi or norm_title(self.title)

    @property
    def link(self) -> str:
        return f"https://doi.org/{self.doi}" if self.doi else self.url

    def to_dict(self, abstract_limit: int | None = None) -> dict:
        d = dict(self.__dict__)
        d["sources"] = sorted(self.sources)
        if abstract_limit:
            d["abstract"] = shorten(self.abstract, abstract_limit)
        return d
