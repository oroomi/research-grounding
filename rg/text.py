"""Plain-text helpers: stopwords, light stemming, tokenising, sentence splitting, abstract reconstruction."""
from __future__ import annotations

import re

_EN = """a about above after again against all also am an and any are as at be because been before being below between both but by
can cannot could did do does doing down during each either else etc few for from further had has have having he her here hers him his
how however i if in into is it its itself just like may me might more most much must my no nor not now of off on once only or other
our ours out over own per same shall she should since so some such than that the their theirs them then there these they this those
through to too under until up upon us very via was we were what when where whether which while who whom whose why will with within without
would yet you your yours one two three four five six seven eight nine ten first second third new many every each among across around
get gets got make makes made take takes taken need needs needed want wants wanted well even still back off ever never always often
able likely really quite rather thus therefore hence whereas although though""".split()

_FI = """ja tai mutta että kun jos niin kuin on ovat oli olla ei ole eivät se ne tämä nämä tuo nuo mikä mitkä joka jotka sekä myös vain
jo vielä sen niiden tässä siinä kanssa ilman kautta välillä aikana sitten koska vaan ettei joten eli tämän näiden""".split()

# Words that describe the hackathon itself, not the subject of the challenge. They break phrases.
GENERIC = set("""hackathon hackathons challenge challenges participant participants team teams build builds building built solution solutions
prototype prototypes develop develops developing developed development create creates creating created use uses using used help helps helping
support supports supporting provide provides providing tool tools platform platforms app apps application applications service services
product products company companies partner partners startup startups business businesses organisation organization organisations
organizations problem problems idea ideas innovative innovation innovations future better best improve improves improved improving
enable enables enabling easier easy user users customer customers people person someone something anything everyone demo demos pitch pitches
judge judges judging criteria prize prizes mentor mentors deadline submit submission submissions weekend track tracks case cases
work works working worked task tasks goal goals aim aims aimed objective objectives brief briefs competition event
opportunity opportunities way ways approach approaches concept concepts vision example examples including include includes included
based role world real today day days time year years part parts end level levels free open scale simple smart digital modern
different various several certain particular specific important key main general overall potential possible significant
looking look looks find finds finding show shows showing give gives giving let lets allow allows allowing""".split())

# Common verbs/adverbs/pronouns that RAKE would otherwise glue into "phrases" ("tips nobody reads", "goes wrong").
# Matched on the light stem, so goes/going/went... need listing only where the stem differs.
VERBS = set("""go goe went gone expect read reduce think care explain ask try know see say come became become remember follow reach ensure
consider start begin continue hope believe suggest require appear seem happen tell keep let put set run bring turn hold leave feel
mean stay pay meet include lead learn change play live believe understand watch sit stand lose add spend grow open walk offer remain
wrong right nobody anybody nothing everything anyone everyone anywhere somewhere nowhere often usually rarely sometimes already
today tomorrow yesterday soon early late next last previous recent current currently daily weekly produce summarise summarize
express reflect represent describe discuss mention note notice consider think wish prefer imagine remember forget decide choose
actually basically simply mostly mainly merely maybe perhaps indeed quickly easily fully highly clearly directly especially
usually typically generally essentially approximately exactly nearly almost""".split())

# Method buzzwords: fine inside a phrase ("machine learning model of X"), but a phrase made only of these is dropped.
BUZZ = set("""ai artificial intelligence machine learning ml llm llms model models chatbot chatbots generative genai algorithm algorithms
data dataset datasets analysis analytics insight insights information system systems technology technologies software""".split())

STOP = set(_EN) | set(_FI)

_ABBREV = ["e.g.", "i.e.", "et al.", "vs.", "fig.", "figs.", "no.", "approx.", "ca.", "cf.", "dr.", "mr.", "mrs.", "ms.", "inc.", "ltd.", "sp.", "spp."]


def stem(w: str) -> str:
    """Very light English stemmer, only for matching a brief's words against abstracts."""
    w = w.lower().strip("-'")
    if w.endswith("'s"):
        w = w[:-2]
    if len(w) <= 3:
        return w
    for suf, rep in (("ies", "y"), ("sses", "ss"), ("ations", "ate"), ("ation", "ate"), ("ments", "ment"), ("ings", ""), ("ing", ""),
                     ("edly", ""), ("ed", ""), ("ly", ""), ("es", ""), ("s", "")):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            if suf == "s" and (w.endswith("ss") or w.endswith("us") or w.endswith("is")):
                continue
            w = w[: len(w) - len(suf)] + rep
            break
    if w.endswith("e") and len(w) > 4:  # resistance / resistances, reduce / reduced meet in the same stem
        w = w[:-1]
    return w


_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ0-9]*(?:[-'][A-Za-zÀ-ÖØ-öø-ÿ0-9]+)*")


def tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD.finditer(text)]


def stems(text: str) -> set[str]:
    return {stem(t) for t in tokens(text) if t not in STOP}


def strip_markup(text: str) -> str:
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\S+@\S+\.\S+", " ", text)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # markdown links keep their label
    text = re.sub(r"<[^>]+>", " ", text)
    return text


def split_sentences(text: str) -> list[str]:
    """Sentence splitter that does not break on common abbreviations, initials, decimals or 'et al.'."""
    t = re.sub(r"\s+", " ", text).strip()
    if not t:
        return []
    for ab in _ABBREV:
        t = re.sub(r"(?<![A-Za-z])" + re.escape(ab), ab.replace(".", "\u2024"), t, flags=re.I)
    t = re.sub(r"(?<=\b[A-Z])\.(?=\s?[A-Z]\.)", "\u2024", t)  # initials "J. K."
    t = re.sub(r"(?<=[A-Z]\u2024 [A-Z])\.(?=\s[A-Z][a-z])", "\u2024", t)  # ...and the last one before the surname
    t = re.sub(r"(\d)\.(\d)", "\\1\u2024\\2", t)  # decimals
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\[\"“])", t)
    return [p.replace("\u2024", ".").strip() for p in parts if p.strip()]


_JATS = re.compile(r"</?(?:jats:)?[a-z0-9]+[^>]*>", re.I)


def reconstruct_abstract(inv: dict | None) -> str:
    """OpenAlex returns abstracts as {word: [positions]}. Put the words back in order."""
    if not inv:
        return ""
    slots: dict[int, str] = {}
    for word, positions in inv.items():
        for pos in positions or []:
            slots.setdefault(int(pos), word)
    if not slots:
        return ""
    text = " ".join(slots[i] for i in sorted(slots))
    text = _JATS.sub(" ", text)
    text = re.sub(r"\s+([,.;:!?)\]])", r"\1", text)
    text = re.sub(r"([(\[])\s+", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(?:abstract|summary)\s*[:.\-]?\s+", "", text, flags=re.I)
    return text
