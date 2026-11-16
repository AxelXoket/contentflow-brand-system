"""Deterministic content checks: the brand voice rules, numbers without a source, SEO rules and channel limits.

Every function returns a list of problems in plain English; an empty list means the text passes.
The build refuses to write deliverables while any check reports a problem.
"""
import json
import pathlib
import re
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
BRAND = json.loads((ROOT / "brand" / "brand.json").read_text(encoding="utf-8"))

# Writing rules that hold for every text in the repository, Turkish or English.
STYLE_BANNED = ("delve", "crucial", "robust", "comprehensive", "nuanced", "multifaceted", "furthermore", "moreover",
                "pivotal", "landscape", "tapestry", "underscore", "foster", "showcase", "intricate", "vibrant",
                "fundamental", "significant", "interplay")
LONG_DASHES = (chr(0x2013), chr(0x2014))
SINGULAR_ADDRESS = ("sen", "senin", "sana", "seni", "sende", "senden", "seninle", "senle", "sence")
# A web address with or without its scheme (example.com/a); punctuation that ends the sentence stays outside it.
URL = re.compile(r"(?:https?://|\b[a-z0-9-]+(?:\.[a-z0-9-]+)+/)\S*?(?=[.,;:!?)\"”]*(?:\s|$))", re.IGNORECASE)
HASHTAG = re.compile(r"#\w+")
WORD = re.compile(r"[\w'’]+")
# Number words become digits before the number check, so a number read aloud is checked like a written one.
# "bir" and "yedi" stay out: in running text they almost always mean "a" and "ate".
NUMBER_WORDS = {"iki": 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6, "sekiz": 8, "dokuz": 9, "on": 10, "yirmi": 20,
                "otuz": 30, "kırk": 40, "elli": 50, "altmış": 60, "yetmiş": 70, "seksen": 80, "doksan": 90, "yüz": 100,
                "bin": 1000}
_STEMS = "|".join(sorted(NUMBER_WORDS, key=len, reverse=True))
PERCENT_WORD = re.compile(rf"(?<!\w)yüzde\s+({_STEMS})\w*")
NUMBER_WORD = re.compile(rf"(?<!\w)({_STEMS})(?!\w)")
# A number as Turkish text writes it (6, 100,0, 1.250,50, %80, the range 20-35), an apostrophe suffix ('ine), an
# ordinal point (1.) and, without consuming it, the word after it.
NUMBER = re.compile(r"(%?\d+(?:[.,]\d+)*(?:-\d+(?:[.,]\d+)*)?)(?:'\w+)?(\.(?!\d))?(?=[^\w\s]*\s*(\w*))")
# What may stand before an ordinal on its line: heading, list and quote marks ("## 1. Harcama ...").
ORDINAL_LEAD = re.compile(r"[#>*\s-]*")
CHANNEL_LIMITS = {"Instagram": 2200, "LinkedIn": 3000, "X": 280}
HASHTAG_LIMITS = {"Instagram": 5, "LinkedIn": 3, "X": 2}
# Instagram captions are not links, so a post there sends the reader to the profile instead of printing the address.
LINK_IN_BIO = {"Instagram": "bağlantı profilde"}
# The prefix of a number problem, so the checklist can show numbers apart from the other voice rules.
NUMBER_PROBLEM = "number without source"
BLOG_TITLE_MAX = 60
BLOG_DESCRIPTION = (120, 155)
BLOG_WORDS = (600, 1200)


def tr_lower(text: str) -> str:
    """Lower case the Turkish way: I becomes ı and İ becomes i. Composed first, so I plus a combining dot is İ."""
    return unicodedata.normalize("NFC", text).replace("I", "ı").replace("İ", "i").lower()


def starts_a_word(stem: str, text: str) -> bool:
    """The stem begins some word of the text, in Turkish or plain lower case (KESIN typed without İ counts too)."""
    pattern = rf"(?<!\w){re.escape(stem)}"
    return any(re.search(pattern, low) for low in (tr_lower(text), unicodedata.normalize("NFC", text).lower()))


def words(text: str) -> list[str]:
    return WORD.findall(text)


def same_words(a: str, b: str) -> bool:
    """The same words in the same order, whatever the case, punctuation or line breaks."""
    return [tr_lower(w) for w in words(a)] == [tr_lower(w) for w in words(b)]


IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def blog_word_count(markdown_text: str) -> int:
    """Words a reader reads in the text: pictures (their alt text included) and link addresses do not count."""
    return len(words(re.sub(r"\]\([^)]*\)", "]", IMAGE.sub("", markdown_text))))


def sentences(text: str) -> list[str]:
    """Sentences of running text; a line break also ends one, so headings and list items count on their own."""
    plain = URL.sub("", text)
    parts = re.split(r"(?<=[.!?])\s+|\n+", plain)
    return [part.strip() for part in parts if words(part)]


def long_sentences(text: str, limit: int = BRAND["voice"]["max_sentence_words"]) -> list[str]:
    return [f"{len(words(s))} words: {s}" for s in sentences(text) if len(words(s)) > limit]


def avoided_words(text: str, avoid=tuple(BRAND["voice"]["avoid"])) -> list[str]:
    """Avoid-list hits, matched at the start of a word so Turkish suffixes are caught too (garantili, israfı)."""
    plain = URL.sub("", text)
    return sorted({word for word in avoid if starts_a_word(tr_lower(word), plain)})


def singular_address(text: str) -> list[str]:
    """The brand speaks to the reader as "siz"; singular "sen" forms are a slip."""
    return sorted({w for w in (tr_lower(x) for x in words(text)) if w in SINGULAR_ADDRESS})


def style_problems(text: str) -> list[str]:
    found = [f"long dash U+{ord(c):04X}" for c in LONG_DASHES if c in text]
    found += [f"banned word {w}" for w in STYLE_BANNED if starts_a_word(w, text)]
    return found


def allowed_forms(brand=BRAND) -> list[tuple[str, str]]:
    """Every phrase a number may stand in, as (number, start of the next word): "6 saniye" is ("6", "saniye")."""
    items = brand["facts"] + brand["own_numbers"]
    return [(number, tr_lower(after)) for item in items for number, _, after in (form.partition(" ") for form in item["forms"])]


def numbers_in(text: str) -> list[tuple[str, str]]:
    """Each number of the text with the word after it, number words turned into digits, URLs and hashtags left out."""
    plain = tr_lower(HASHTAG.sub("", URL.sub("", text)))
    plain = PERCENT_WORD.sub(lambda m: f"%{NUMBER_WORDS[m.group(1)]}", plain)
    plain = NUMBER_WORD.sub(lambda m: str(NUMBER_WORDS[m.group(1)]), plain)
    found = []
    for match in NUMBER.finditer(plain):
        number, point, after = match.groups()
        line_start = plain.rfind("\n", 0, match.start()) + 1
        # A point makes an ordinal only after a whole number that starts its line; anywhere else it ends the sentence.
        if point and number.isdigit() and ORDINAL_LEAD.fullmatch(plain[line_start:match.start()]):
            number += point
        found.append((number, after))
    return found


def unexplained_numbers(text: str, forms: list[tuple[str, str]] | None = None) -> list[str]:
    """Numbers that stand in no phrase of a product fact or a labelled own number: a hallucination risk."""
    forms = allowed_forms() if forms is None else forms
    found = {f"{number} {after}".strip() for number, after in numbers_in(text)
             if not any(number == allowed and after.startswith(start) for allowed, start in forms)}
    return sorted(found)


def claims_in(text: str, brand=BRAND) -> list[str]:
    """The product facts and claims a text makes: a fact by one of its number phrases, a claim by one of its phrases.
    The checklist lists them per piece, so every claim a reader meets leads to a line in the panel's code."""
    numbers = numbers_in(text)
    low = tr_lower(URL.sub("", text))
    facts = [item["id"] for item in brand["facts"]
             if any(found == number and after.startswith(tr_lower(start))
                    for number, _, start in (form.partition(" ") for form in item["forms"]) for found, after in numbers)]
    return facts + [item["id"] for item in brand["product_claims"] if any(tr_lower(p) in low for p in item["phrases"])]


def voice_problems(text: str) -> list[str]:
    """Everything the voice guide asks of a published text, in one list."""
    problems = [f"long sentence ({s})" for s in long_sentences(text)]
    problems += [f"avoided word {w}" for w in avoided_words(text)]
    problems += [f"singular address {w}" for w in singular_address(text)]
    problems += [f"{NUMBER_PROBLEM} {n}" for n in unexplained_numbers(text)]
    problems += style_problems(text)
    return problems


def post_problems(post: dict) -> list[str]:
    """A social post: voice rules plus the channel's length and hashtag limits, and a link to the panel."""
    text, channel = post["text"], post["channel"]
    problems = voice_problems(text)
    if len(text) > CHANNEL_LIMITS[channel]:
        problems.append(f"{len(text)} characters, {channel} allows {CHANNEL_LIMITS[channel]}")
    tags = HASHTAG.findall(text)
    if len(tags) > HASHTAG_LIMITS[channel]:
        problems.append(f"{len(tags)} hashtags, the guide allows {HASHTAG_LIMITS[channel]} on {channel}")
    if tr_lower(LINK_IN_BIO.get(channel, BRAND["short_url"])) not in tr_lower(text):
        problems.append("no link to the panel")
    return problems


def blog_problems(meta: dict, markdown_text: str) -> list[str]:
    """SEO rules for the blog post, on its front matter and Markdown body."""
    problems = []
    keyword = tr_lower(meta["keyword"])
    if len(meta["title"]) > BLOG_TITLE_MAX:
        problems.append(f"title has {len(meta['title'])} characters, at most {BLOG_TITLE_MAX}")
    low, high = BLOG_DESCRIPTION
    if not low <= len(meta["description"]) <= high:
        problems.append(f"description has {len(meta['description'])} characters, {low} to {high} wanted")
    lines = markdown_text.splitlines()
    h1 = [line[2:] for line in lines if line.startswith("# ")]
    h2 = [line[3:] for line in lines if line.startswith("## ")]
    # Headings, list items and quotes are not the first paragraph; a line that only starts with a number is.
    paragraphs = [line for line in lines if line.strip() and not re.match(r"#|[-*>] |\d+\. ", line)]
    if len(h1) != 1:
        problems.append(f"{len(h1)} H1 headings, exactly 1 wanted")
    for place, text in (("title", meta["title"]), ("H1", h1[0] if h1 else ""), ("first paragraph", paragraphs[0] if paragraphs else ""),
                        ("description", meta["description"])):
        if keyword not in tr_lower(text):
            problems.append(f"keyword missing from the {place}")
    if not any(keyword in tr_lower(h) for h in h2):
        problems.append("keyword missing from every H2")
    if BRAND["app_url"] not in markdown_text:
        problems.append("no link to the panel")
    if BRAND["disclaimer"] not in markdown_text:
        problems.append("no disclaimer")
    count = blog_word_count(markdown_text)
    low, high = BLOG_WORDS
    if not low <= count <= high:
        problems.append(f"{count} words, {low} to {high} wanted")
    return problems + voice_problems("\n".join([meta["title"], meta["description"], markdown_text]))


def read_front_matter(path: pathlib.Path) -> tuple[dict, str]:
    """A Markdown file with "key: value" lines between two --- lines at the top."""
    text = path.read_text(encoding="utf-8")
    _, head, body = text.split("---\n", 2)
    meta = dict(line.split(": ", 1) for line in head.strip().splitlines())
    return meta, body.lstrip("\n")


def contrast(foreground: str, background: str) -> float:
    """WCAG contrast ratio of two #RRGGBB colours."""
    def luminance(hex_colour: str) -> float:
        channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    high, low = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)
