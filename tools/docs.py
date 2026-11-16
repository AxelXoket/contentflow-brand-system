"""The PDF documents: brand strategy (2 pages), voice guide (1 page), content checklist (2 pages), the blog post and the
presentation that joins everything for Canva. Each page is HTML with a fixed size, checked for fit, then printed by Edge.
"""
import json
import pathlib
import re
import subprocess
import tempfile

import fitz
import markdown
from PIL import Image

import build
import checks
import render
from build import BRAND, COLOURS, CONTENT, FRAMES, OUT, PILLARS, SET, e, load, tr_date, tr_day

COMPETITORS = json.loads((build.ROOT / "brand" / "competitors.json").read_text(encoding="utf-8"))
HANDLE_LINE = "AxelXoket · Kasım 2026"
REPO_URL = "https://github.com/AxelXoket/contentflow-brand-system"
PASSED = "Geçti"
CLAIMS = {item["id"]: item for item in BRAND["facts"] + BRAND["product_claims"]}

A4_CSS = """
@page { size: A4; margin: 0; }
.page { width: 210mm; height: 297mm; padding: 14mm 15mm; overflow: hidden; page-break-after: always; position: relative;
  font-size: 9.6pt; line-height: 1.38; background: #fff; }
.page:last-of-type { page-break-after: auto; }
.top { display: flex; align-items: center; gap: 10px; border-bottom: 2px solid var(--zumrut); padding-bottom: 8px; margin-bottom: 10px; }
.top h1 { font-size: 17pt; line-height: 1.15; }
.top .meta { margin-left: auto; color: var(--sis); font-size: 8.6pt; text-align: right; }
h2 { font-size: 11.5pt; color: var(--zumrut); margin: 8px 0 4px; }
h3 { font-size: 10pt; margin: 6px 0 2px; }
p + p { margin-top: 4px; }
p + table { margin-top: 6px; }
ul { padding-left: 15px; } li + li { margin-top: 2px; }
table { width: 100%; border-collapse: collapse; font-size: 8.4pt; line-height: 1.3; }
th { background: var(--zumrut); color: #fff; text-align: left; padding: 4px 5px; font-weight: 600; }
td { border-bottom: 1px solid #CAD5E2; padding: 4px 5px; vertical-align: top; }
tr.ours td { background: #ECFDF5; font-weight: 600; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.cols3 { display: grid; grid-template-columns: 1fr 1.1fr 1fr; gap: 12px; }
.swatches { display: flex; gap: 8px; margin: 4px 0 2px; }
.swatch { flex: 1; border-radius: 6px; padding: 16px 6px 5px; font-size: 7.8pt; line-height: 1.25; border: 1px solid #CAD5E2; }
.swatch b { display: block; }
.card { border: 1px solid #CAD5E2; border-radius: 8px; padding: 7px 9px; }
.label { color: var(--sis); font-size: 8pt; font-weight: 700; letter-spacing: .06em; }
.small { font-size: 7.6pt; color: var(--sis); line-height: 1.3; }
.sources { font-size: 8.2pt; color: var(--sis); line-height: 1.35; } .sources a { color: inherit; text-decoration: none; }
.pass { color: var(--zumrut); font-weight: 700; }
.fail { color: #B91C1C; font-weight: 700; }
/* Each item keeps its own indent, so a bullet never sits in the gap next to the other column. */
ul.two { columns: 2; column-gap: 22px; padding-left: 0; } ul.two li { break-inside: avoid; margin-left: 15px; }
code { font-family: Consolas, monospace; font-size: 7.4pt; }
table.dense { line-height: 1.2; } table.dense td { padding: 2px 5px; }
.foot { position: absolute; left: 15mm; right: 15mm; bottom: 9mm; display: flex; justify-content: space-between; color: var(--sis); font-size: 7.6pt; }
"""


def a4_page(title: str, inner: str, number: int, total: int) -> str:
    return (f'<section class="page" data-name="{e(title)} sayfa {number}"><div class="top">{build.logo(30, COLOURS["Zümrüt"], "#fff")}'
            f'<h1 data-max-lines="1">{e(title)}</h1><div class="meta">{e(BRAND["name"])}<br>{e(HANDLE_LINE)}</div></div>'
            f'{inner}<div class="foot"><span>{e(BRAND["short_url"])}</span><span>{number} / {total}</span></div></section>')


def print_pages(name: str, title: str, css: str, body: str, width: int, height: int) -> pathlib.Path:
    with tempfile.TemporaryDirectory() as tmp:
        page_path = build.write_checked(build.page(title, css, body), pathlib.Path(tmp) / f"{name}.html", width, height)
        target = OUT / f"{name}.pdf"
        render.html_to_pdf(page_path, target)
    return target


def swatch_colours(hex_code: str) -> str:
    return f"background:{hex_code};color:{build.text_on(hex_code)}"


def bullets(items, style: str = "") -> str:
    return f'<ul class="{style}">' + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def joined(items: list[str]) -> str:
    """Items joined into one sentence with semicolons: every item after the first starts in lower case."""
    return "; ".join([items[0]] + [checks.tr_lower(item[0]) + item[1:] for item in items[1:]])


# ---------- brand strategy ----------

def competitor_table() -> str:
    columns = [("Uygulama", "name"), ("Hesap", "account"), ("Banka bağlantısı", "bank"), ("Veri nerede", "data"),
               ("Fiyat", "price"), ("Türkçe", "turkish")]
    head = "".join(f"<th>{e(title)}</th>" for title, _ in columns)
    rows = "".join("<tr>" + "".join(f"<td>{e(app[key])}</td>" for _, key in columns) + "</tr>" for app in COMPETITORS["apps"])
    ours = COMPETITORS["ours"]
    rows += '<tr class="ours">' + "".join(f"<td>{e(ours[key])}</td>" for _, key in columns) + "</tr>"
    widths = "".join(f'<col style="width:{w}%">' for w in (13, 15, 21, 16, 22, 13))
    return f"<table><colgroup>{widths}</colgroup><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"


def strategy() -> pathlib.Path:
    swatches = "".join(f'<div class="swatch" style="{swatch_colours(p["hex"])}"><b>{e(p["name"])}</b>{e(p["hex"])}</div>'
                       for p in BRAND["palette"])
    roles = bullets(f"<b>{e(p['name'])}:</b> {e(p['role'])}" for p in BRAND["palette"])
    values = bullets(f"<b>{e(v['name'])}:</b> {e(v['line'])}" for v in BRAND["values"])
    style = bullets(e(line) for line in BRAND["visual_style"])
    gap = bullets(e(line) for line in COMPETITORS["gap"])
    page1 = f"""
<h2>1. Ürün ve sektör</h2>
<p><b>{e(BRAND['name'])}:</b> {e(BRAND['product'])} Sektör: {e(BRAND['sector'].lower())}.</p>
<h2>2. Rakip analizi</h2>
<p class="small">{e(COMPETITORS['note'])} Erişim: {e(tr_date(COMPETITORS['accessed']))}; kaynaklar 2. sayfada.</p>
{competitor_table()}
<h3>Pazardaki boşluk</h3>{gap}
<h2>3. Marka kimliği</h2>
<div class="swatches">{swatches}</div>
<div class="cols3"><div><h3>Renklerin görevi</h3>{roles}</div><div><h3>Değerler</h3>{values}</div>
<div><h3>Görsel dil</h3>{style}</div></div>"""
    w, persona, voice = BRAND["why_who_what_how"], BRAND["persona"], BRAND["voice"]
    frame = "".join(f'<tr><th style="width:18%">{label}</th><td>{e(w[key])}</td></tr>'
                    for label, key in (("Neden", "neden"), ("Kime", "kime"), ("Ne", "ne"), ("Nasıl", "nasil")))
    pillars = "".join(f'<div class="card"><b>{e(p["name"])}</b><br>{e(p["goal"])}</div>' for p in BRAND["pillars"])
    measures = "".join(f"<tr><th>{e(m['channel'])}</th><td>{e(m['metric'])}</td></tr>" for m in BRAND["measures"]["channels"])
    sources = "; ".join(f"{e(app['name'])}: " + ", ".join(f'<a class="nw" href="{e(u)}">{e(u)}</a>' for u in app["sources"])
                        for app in COMPETITORS["apps"])
    page2 = f"""
<h2>4. Marka hikâyesi; neden, kime, ne, nasıl</h2>
<p>{e(BRAND['story'])}</p>
<table style="margin-top:4px"><tbody>{frame}</tbody></table>
<h2>5. Hedef kitle: persona</h2>
<div class="card"><b>{e(persona['name'])}, {persona['age']}, {e(persona['city'])}.</b> {e(persona['job'])}. {e(persona['story'])}
<div class="cols" style="margin-top:4px"><div><span class="label">İHTİYAÇLARI</span>{bullets(e(n) for n in persona['needs'])}</div>
<div><span class="label">KANALLARI</span><p>{e(', '.join(persona['channels']))}</p></div></div></div>
<h2>6. Marka sesi ve kelimeler</h2>
<p>{e(voice['summary'])} Hitap: "{e(voice['address'])}". Bir cümle en çok {voice['max_sentence_words']} kelime.</p>
<div class="cols"><div><span class="label">KULLANIN</span><p>{e(', '.join(voice['use']))}</p></div>
<div><span class="label">KULLANMAYIN</span><p>{e(', '.join(voice['avoid']))}</p></div></div>
<p class="small">Ayrıntı ve örnekler: Marka Sesi Rehberi (tek sayfa).</p>
<h2>7. İçerik sütunları</h2>
<div class="cols">{pillars}</div>
<h2>8. Nasıl ölçülür</h2>
<p>{e(BRAND['measures']['note'])}</p>
<table><colgroup><col style="width:30%"><col></colgroup><tbody>{measures}</tbody></table>
<h3>Kaynaklar</h3><p class="sources">{sources}</p>"""
    body = a4_page("Marka Stratejisi", page1, 1, 2) + a4_page("Marka Stratejisi", page2, 2, 2)
    return print_pages("marka-stratejisi", "Marka Stratejisi", A4_CSS, body, 900, 1200)


# ---------- voice guide ----------

VOICE_EXAMPLES = [
    ("Paranızı israf etmeyi bırakın!", "Ayın nereye gittiğini görün; kararı sonra verin."),
    ("Bu uygulamayla kesin tasarruf edersiniz.", "Panel harcamanızı görünür kılar. Planı siz yaparsınız."),
    ("Track et, budget planını yap.", "Harcamanızı ekleyin, aylık bütçenizi yazın."),
]


def channel_limit(channel: str) -> str:
    """The measured limit for a channel, read from the same constants the checks use."""
    if channel in checks.CHANNEL_LIMITS:
        return f"en çok {checks.CHANNEL_LIMITS[channel]} karakter, {checks.HASHTAG_LIMITS[channel]} etiket"
    if channel == "Blog":
        low, high = checks.BLOG_WORDS
        return f"{low}-{high} kelime; başlık en çok {checks.BLOG_TITLE_MAX} karakter"
    media = load("media.json")
    spec = {"Video": media["video"], "Seslendirme": media["voiceover"]}[channel]
    return f"{spec['min_seconds']}-{spec['max_seconds']} saniye"


def situation_rows() -> str:
    return "".join(f"<tr><td><b>{e(s['situation'])}</b></td><td>{e(s['tone'])}</td><td>{e(s['example'])}</td></tr>"
                   for s in BRAND["voice"]["situations"])


def channel_rows() -> str:
    return "".join(f"<tr><td><b>{e(c['channel'])}</b></td><td>{e(channel_limit(c['channel']))}</td><td>{e(c['tone'])}</td></tr>"
                   for c in BRAND["voice"]["channels"])


def writing_rules() -> list[str]:
    return BRAND["voice"]["mechanics"] + ["Sayı: kanıtlı bir ürün davranışı ya da \"öneri\" diye etiketli kendi sayımız; "
                                          "yazıyla yazılanlar da denetlenir."]


def voice_guide() -> pathlib.Path:
    voice = BRAND["voice"]
    examples = "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td></tr>" for a, b in VOICE_EXAMPLES)
    inner = f"""
<p style="font-size:11pt;margin-top:4px"><b>{e(voice['summary'])}</b></p>
<p>Blogdan videoya bütün formatların ortak kontrol katmanı; ölçülebilen kurallar <b>tools/checks.py</b> ile denetlenir.</p>
<div class="cols"><div><h2>Yapın</h2>{bullets(e(x) for x in voice['do'])}</div><div><h2>Yapmayın</h2>{bullets(e(x) for x in voice['dont'])}</div></div>
<p style="margin-top:6px"><b>Kullanın:</b> {e(', '.join(voice['use']))}.</p>
<h2>Böyle değil, böyle</h2>
<table><thead><tr><th>Böyle değil</th><th>Böyle</th></tr></thead><tbody>{examples}</tbody></table>
<h2>Duruma göre ton</h2>
<table><colgroup><col style="width:19%"><col style="width:41%"><col></colgroup>
<thead><tr><th>Durum</th><th>Ton</th><th>Örnek</th></tr></thead><tbody>{situation_rows()}</tbody></table>
<h2>Yazım kuralları</h2>{bullets((e(x) for x in writing_rules()), "two")}
<h2>Kanala göre ses</h2>
<table><colgroup><col style="width:15%"><col style="width:33%"><col></colgroup>
<thead><tr><th>Kanal</th><th>Sınır</th><th>Nasıl konuşur</th></tr></thead><tbody>{channel_rows()}</tbody></table>
<h2>Çağrı ve uyarı</h2>
<p>Çağrı: "{e(BRAND['cta']['primary'])}" ya da "{e(BRAND['cta']['sample'])}", yanında {e(BRAND['short_url'])}.
{e(voice['cta_note'])} Para yönetimi anlatan uzun içeriklerin sonunda: "{e(BRAND['disclaimer'])}"</p>"""
    return print_pages("marka-sesi-rehberi", "Marka Sesi Rehberi", A4_CSS, a4_page("Marka Sesi Rehberi", inner, 1, 1), 900, 1200)


# ---------- checklist ----------

def checklist_rows() -> list[dict]:
    """One row per published piece: the automatic voice and number results, the product claims it makes, and the
    rights note that applies to it."""
    notes = load("checklist.json")
    problems = build.content_problems()
    texts = build.published_texts()
    media, calendar = load("media.json"), load("calendar.json")
    pieces = [("Blog yazısı", "Blog", ["blog"], "text")]
    pieces += [(f"{p['channel']} gönderisi", p["channel"], [p["id"]], "text") for p in load("social.json")]
    pieces += [(f"Görsel: {img['headline']}", f"Görsel {i}", [img["id"]], "image_screenshot" if img.get("screenshot") else "image")
               for i, img in enumerate(media["images"], 1)]
    pieces += [("Tanıtım videosu", "Video", ["video"], "video"), ("Seslendirme", "Seslendirme", ["voiceover"], "audio")]
    pieces += [("Hikâye: anket", "Anket", [s["id"]], "story") if s["kind"] == "poll" else
               ("Hikâye: sesli kontrol", "Sesli hikâye", [s["id"]], "story_audio") for s in media["stories"]]
    pieces += [(f"Takvim metinleri ({len(calendar)} gün)", "Takvim", [f"calendar {row['date']}" for row in calendar], "text")]
    rows = []
    for piece, short, keys, right in pieces:
        found = [problem for key in keys for problem in problems.get(key, [])]
        numbers = [problem for problem in found if problem.startswith(checks.NUMBER_PROBLEM)]
        voice = [problem for problem in found if problem not in numbers]
        claims = {claim for key in keys for claim in checks.claims_in(texts[key])}
        rows.append({"piece": piece, "short": short, "voice": "; ".join(voice) or PASSED, "numbers": "; ".join(numbers) or PASSED,
                     "claims": [c for c in CLAIMS if c in claims], "rights": notes["rights"][right],
                     "rights_short": notes["rights_short"][right]})
    return rows


def result_cell(value: str) -> str:
    return f'<td class="{"pass" if value == PASSED else "fail"}">{e(value)}</td>'


def checklist() -> pathlib.Path:
    notes = load("checklist.json")
    rows = checklist_rows()
    body_rows = "".join(f"<tr><td><b>{e(r['piece'])}</b></td>{result_cell(r['voice'])}{result_cell(r['numbers'])}"
                        f"<td>{e(', '.join(CLAIMS[c]['label'] for c in r['claims']) or 'Yok')}</td><td>{e(r['rights_short'])}</td></tr>"
                        for r in rows)
    rights = {r["rights_short"]: r["rights"] for r in rows}
    claim_rows = "".join(f"<tr><td>{e(item['label'])}</td><td>{e(item['evidence'].split('/', 1)[1])}<br><code>{e(item['line'])}</code></td>"
                         f"<td>{e(', '.join(r['short'] for r in rows if cid in r['claims']) or 'Yalnız marka belgelerinde')}</td></tr>"
                         for cid, item in CLAIMS.items())
    low, high = checks.BLOG_DESCRIPTION
    page1 = f"""
<p>Bütün içerikler yayından önce üç açıdan denetlendi: marka sesi tutarlılığı, telif ve etik uygunluk, halüsinasyon riski.
Ses ve sayı sütunları <b>tools/checks.py</b> çıktısıdır; iddia sütunu her parçada bulunan ürün iddialarıdır. Bu sayfa her
derlemede yeniden üretilir ve bir denetim geçmezse derleme hiçbir dosya yazmadan durur.</p>
<h2>Parça parça sonuçlar</h2>
<table><colgroup><col style="width:24%"><col style="width:9%"><col style="width:8%"><col style="width:35%"><col></colgroup>
<thead><tr><th>İçerik</th><th>Marka sesi</th><th>Sayılar</th><th>Ürün iddiaları (kaynaklı)</th><th>Telif ve etik</th></tr></thead>
<tbody>{body_rows}</tbody></table>
<h2>Telif ve etik notları</h2>{bullets(f"<b>{e(label)}:</b> {e(text)}" for label, text in rights.items())}
<h2>Parçalar arası tutarlılık</h2>{bullets(e(line) for line in notes['consistency'])}
<h2>Etik</h2><p>{e(notes['ethics'])}</p>"""
    page2 = f"""
<h2>Halüsinasyon kontrolü nasıl yapıldı</h2>{bullets(e(notes['facts'][key]) for key in ('product', 'competitors', 'numbers'))}
<h2>Ürün iddiaları ve kaynakları</h2>
<table class="dense"><colgroup><col style="width:20%"><col style="width:55%"><col></colgroup>
<thead><tr><th>İddia</th><th>Kaynak dosya ve satır</th><th>Geçtiği parçalar</th></tr></thead><tbody>{claim_rows}</tbody></table>
<h2>Marka sesi denetiminin kuralları</h2>
<ul class="two"><li>Cümle başına en çok {BRAND['voice']['max_sentence_words']} kelime.</li>
<li>Kaçınılan kelimeler ve ekli biçimleri yok (israf, garanti, kesin ...).</li><li>"Sen" hitabı yok; okura "siz" denir.</li>
<li>Kanal sınırları: karakter ve etiket sayısı; her gönderide panel bağlantısı, Instagram'da "bağlantı profilde".</li>
<li>Videoda her sahnenin ekrandaki yazısı ile sesi aynı kelimeler.</li>
<li>Blogda SEO kuralları: başlık en çok {checks.BLOG_TITLE_MAX} karakter, açıklama {low}-{high} karakter, anahtar kelime
başlıkta, H1'de, ilk paragrafta ve bir H2'de.</li></ul>"""
    body = a4_page("İçerik Kontrol Listesi", page1, 1, 2) + a4_page("İçerik Kontrol Listesi", page2, 2, 2)
    return print_pages("kontrol-listesi", "İçerik Kontrol Listesi", A4_CSS, body, 900, 1200)


# ---------- blog ----------

# The article column is the printed text width (A4 minus 20 mm margins), so the fit check sees the printed lines.
BLOG_CSS = """
@page { size: A4; margin: 18mm 20mm; }
body { font-size: 10.5pt; line-height: 1.5; max-width: 170mm; margin: 0 auto; padding: 0 0 8mm; }
header { display: flex; align-items: center; gap: 10px; color: var(--sis); font-size: 9pt; border-bottom: 2px solid var(--zumrut); padding-bottom: 6px; }
.seo { margin: 12px 0 14px; border: 1px solid #CAD5E2; border-radius: 8px; padding: 8px 12px; font-size: 9pt; color: var(--sis); }
.seo b { color: var(--gece); }
article h1 { font-size: 22pt; line-height: 1.2; margin: 14px 0 10px; text-wrap: pretty; }
article h2 { font-size: 14pt; color: var(--zumrut); margin: 16px 0 6px; break-after: avoid; }
article p, article li { break-inside: avoid; }
article p + p { margin-top: 8px; }
article ul { margin: 6px 0; padding-left: 20px; break-inside: avoid; }
article a { color: var(--zumrut); }
article img { display: block; width: 66mm; margin: 10px auto; border: 1px solid #CAD5E2; border-radius: 8px; }
"""
# The two panel pictures in the post, cut from the panel screenshot.
BLOG_IMAGES = {"blog-harcama-ekle.png": "form", "blog-kategori-dagilimi.png": "breakdown"}
BLOG_PRINT_WIDTH = 643  # 170 mm at 96 dpi


def blog() -> tuple[pathlib.Path, pathlib.Path]:
    meta, body = checks.read_front_matter(CONTENT / "blog.md")
    article = markdown.markdown(body).replace("<h1>", '<h1 data-max-lines="2" data-name="blog H1">')
    article = re.sub(r"<h2>", '<h2 data-max-lines="1">', article)
    seo = (f'<div class="seo"><b>Anahtar kelime:</b> {e(meta["keyword"])} · <b>Adres:</b> /{e(meta["slug"])}<br>'
           f'<b>Başlık ({len(meta["title"])} karakter):</b> {e(meta["title"])}<br>'
           f'<b>Açıklama ({len(meta["description"])} karakter):</b> {e(meta["description"])}</div>')
    header = f'<header>{build.logo(22, COLOURS["Zümrüt"], "#fff")}<span>{e(BRAND["name"])} · Blog</span></header>'
    SET.mkdir(parents=True, exist_ok=True)
    pdf_path = SET / "blog.pdf"
    with tempfile.TemporaryDirectory() as tmp:
        workdir = pathlib.Path(tmp)
        for name, crop in BLOG_IMAGES.items():
            build.crop_panel(crop, workdir).replace(SET / name)
        # The PDF is the submitted copy, with its SEO card; it is printed from a temporary page, so its pictures are
        # linked by full path. The HTML is the page a reader opens, next to its pictures, with the SEO in its head.
        printed_article = article
        for name in BLOG_IMAGES:
            printed_article = printed_article.replace(f'src="{name}"', f'src="{(SET / name).as_uri()}"')
        printed = build.page(meta["title"], BLOG_CSS, f"{header}{seo}<article>{printed_article}</article>")
        render.html_to_pdf(build.write_checked(printed, workdir / "blog.html", BLOG_PRINT_WIDTH, 1000), pdf_path)
    published_on = next(row["date"] for row in load("calendar.json") if row["piece"] == "blog")
    picture = "blog-kategori-dagilimi.png"
    schema = {"@context": "https://schema.org", "@type": "Article", "headline": meta["title"], "description": meta["description"],
              "inLanguage": "tr-TR", "datePublished": published_on, "image": [picture],
              "author": {"@type": "Person", "name": "AxelXoket"}, "keywords": meta["keyword"]}
    # No canonical address and no og:url: the post has no host yet; they go in with the address it is published at.
    head = (f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="description" content="{e(meta["description"])}">'
            f'<meta property="og:type" content="article"><meta property="og:locale" content="tr_TR">'
            f'<meta property="og:title" content="{e(meta["title"])}"><meta property="og:description" content="{e(meta["description"])}">'
            f'<meta property="og:image" content="{picture}">'
            f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False).replace("</", "<\\/")}</script>')
    published = build.page(meta["title"], BLOG_CSS + "body { padding: 16px; }", f"{header}<article>{article}</article>", head)
    html_path = SET / "blog.html"
    html_path.write_text(published.replace(render.FIT_SCRIPT, ""), encoding="utf-8", newline="\n")
    return html_path, pdf_path


# ---------- presentation ----------

DECK_CSS = """
@page { size: 1280px 720px; margin: 0; }
.slide { width: 1280px; height: 720px; padding: 52px 64px 44px; overflow: hidden; page-break-after: always; position: relative;
  display: flex; flex-direction: column; background: var(--kagit); font-size: 19px; line-height: 1.4; }
.slide:last-of-type { page-break-after: auto; }
.kicker { color: var(--zumrut); font-weight: 700; letter-spacing: .14em; font-size: 15px; }
.slide h2 { font-size: 38px; line-height: 1.15; margin: 6px 0 18px; }
.slide.cover { background: var(--gece); color: var(--kagit); justify-content: center; }
.slide.cover h1 { font-size: 66px; line-height: 1.1; margin: 18px 0 14px; }
.slide.cover .kicker { color: var(--kehribar); }
.grid2, .grid3, .grid4, .grid5 { display: grid; gap: 22px; align-items: start; }
.grid2 { grid-template-columns: 1fr 1fr; } .grid3 { grid-template-columns: repeat(3, 1fr); }
.grid4 { grid-template-columns: repeat(4, 1fr); gap: 18px; } .grid5 { grid-template-columns: repeat(5, 1fr); gap: 16px; }
.even { align-items: stretch; }
.box { background: #fff; border: 1px solid #CAD5E2; border-radius: 14px; padding: 14px 18px; }
.box b.t { display: block; color: var(--zumrut); margin-bottom: 4px; }
.slide table { width: 100%; border-collapse: collapse; font-size: 14px; line-height: 1.3; background: #fff; }
.slide th { background: var(--zumrut); color: #fff; text-align: left; padding: 7px 9px; }
.slide td { border-bottom: 1px solid #CAD5E2; padding: 6px 9px; vertical-align: top; }
.slide tr.ours td { background: #ECFDF5; font-weight: 600; }
.thumb { width: 100%; border-radius: 12px; display: block; border: 1px solid #CAD5E2; }
.post { white-space: pre-line; font-size: 15px; line-height: 1.42; }
.prompt { font-size: 15.5px; line-height: 1.4; }
.prompt.tight { font-size: 14px; }
.prompt b { color: var(--zumrut); }
.mid { font-size: 16px; line-height: 1.45; }
.swatch { height: 84px; border-radius: 12px; padding: 10px 12px; font-size: 15px; display: flex; flex-direction: column;
  justify-content: flex-end; border: 1px solid #CAD5E2; }
.role { font-size: 13.5px; line-height: 1.35; color: var(--sis); margin-top: 6px; }
.foot { position: absolute; left: 64px; right: 64px; bottom: 18px; display: flex; justify-content: space-between; color: var(--sis); font-size: 13px; }
.cover .foot { color: #94A3B8; }
.frames { display: flex; gap: 12px; }
.frames img { width: 150px; border-radius: 10px; display: block; }
.wave { width: 100%; height: 48px; display: block; margin: 4px 0 6px; }
.brandmark { display: flex; align-items: center; gap: 14px; font-size: 24px; font-weight: 700; margin: 4px 0 10px; }
.muted { color: var(--sis); }
ul.tight { padding-left: 20px; } ul.tight li + li { margin-top: 4px; }
ul.plain { list-style: none; padding-left: 0; }
.blogtext { column-count: 2; column-gap: 30px; font-size: 13.5px; line-height: 1.42; }
.blogtext h2 { font-size: 16px; line-height: 1.25; color: var(--zumrut); margin: 0 0 4px; break-after: avoid; }
.blogtext p, .blogtext ul { margin: 0 0 7px; break-inside: avoid; } .blogtext ul { padding-left: 18px; } .blogtext li { break-inside: avoid; }
.story { width: 220px; border-radius: 12px; display: block; border: 1px solid #CAD5E2; }
.alt { font-size: 13px; line-height: 1.35; margin-top: 6px; }
.slide a { color: var(--zumrut); font-weight: 600; }
"""
SLIDE_NUMBER = "__SLIDE__"
SHOT_SCALE = 2


def slide(key: str, kicker: str, title: str, inner: str) -> str:
    """One slide; its number is filled in by deck() from the slide's place in the deck."""
    return (f'<section class="slide" data-name="{e(key)}"><div class="kicker" data-max-lines="1">{e(kicker)}</div>'
            f'<h2 data-max-lines="1" data-name="{e(key)} başlık">{e(title)}</h2>{inner}'
            f'<div class="foot"><span>{e(BRAND["name"])} · ContentFlow</span><span>{SLIDE_NUMBER}</span></div></section>')


def link(path: pathlib.Path) -> str:
    """A link to a delivered file on the public repository, so the PDF can open the video and the sound."""
    return f'<a href="{REPO_URL}/blob/main/{path.relative_to(build.ROOT).as_posix()}">{e(path.name)}</a>'


def slide_pngs(pdf: pathlib.Path, keys: list[str]) -> list[pathlib.Path]:
    """Every page of the deck as a PNG at twice the slide size, for tools that import pictures (Canva keeps the look)."""
    target_dir = OUT / "sunum-slaytlar"
    target_dir.mkdir(parents=True, exist_ok=True)
    for old in target_dir.glob("*.png"):
        old.unlink()
    saved = []
    with fitz.open(pdf) as doc:
        for number, (page, key) in enumerate(zip(doc, keys, strict=True), 1):
            zoom = 1280 * SHOT_SCALE / page.rect.width
            target = target_dir / f"{number:02d}-{key}.png"
            page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).save(target)
            saved.append(target)
    return saved


def screenshot_keys() -> list[str]:
    """The slides saved as PNG for "Örnek İçerik Seti Ekran Görüntüleri", in this order, plus the identity card."""
    return ["marka-kimligi", "icerik-takvimi", "takvim-gerekce", "blog", *(p["id"] for p in load("social.json")), "gorseller",
            "hikayeler", "video-ve-ses", "istemler"]


def screenshot_names() -> list[str]:
    return [f"{i:02d}-{key}" for i, key in enumerate(screenshot_keys(), 1)]


def rtf(prompt: dict, style: str = "prompt") -> str:
    return (f'<div class="{style}"><b>Rol:</b> {e(prompt["role"])}<br><b>Görev:</b> {e(prompt["task"])}<br>'
            f'<b>Format:</b> {e(prompt["format"])}</div>')


def seconds(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def short_date(iso: str) -> str:
    day = build.date.fromisoformat(iso)
    return f"{day.day} {build.TR_MONTHS[day.month - 1]}, {tr_day(iso)}"


def waveform(audio: pathlib.Path, target: pathlib.Path) -> pathlib.Path:
    """A picture of the sound track, drawn by ffmpeg in the brand green: the audio's proof on paper."""
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(audio), "-filter_complex",
                    f"showwavespic=s=1100x100:colors=0x{COLOURS['Zümrüt'][1:]}", "-frames:v", "1", str(target)],
                   check=True, capture_output=True, timeout=120)
    return target


def cover_slide() -> str:
    days = len(load("calendar.json"))
    return (f'<section class="slide cover" data-name="kapak"><div class="kicker">CONTENTFLOW · YAPAY ZEKA DESTEKLİ MARKA İÇERİK SİSTEMİ</div>'
            f'<h1 data-max-lines="2">{e(BRAND["name"])}</h1><p style="font-size:28px">{e(BRAND["tagline"])}</p>'
            f'<p style="margin-top:34px;font-size:18px;color:#CAD5E2">Marka stratejisi · {days} günlük içerik takvimi · Örnek içerik seti · '
            f'Kontrol listesi</p><div class="foot"><span>{e(HANDLE_LINE)}</span><span>{e(BRAND["short_url"])}</span></div></section>')


def analysis_slide() -> str:
    note = f"{COMPETITORS['gap'][-1]} Kaynaklar marka stratejisi belgesinde; erişim {tr_date(COMPETITORS['accessed'])}."
    return slide("rakipler", "AŞAMA 1 · MARKA ANALİZİ", "Rakipler ve pazardaki boşluk",
                 competitor_table() + f'<p class="muted" style="font-size:14px;margin-top:10px">{e(note)}</p>')


def identity_slide() -> str:
    swatches = "".join(f'<div><div class="swatch" style="{swatch_colours(p["hex"])}"><b>{e(p["name"])}</b>{e(p["hex"])}</div>'
                       f'<p class="role">{e(p["role"])}</p></div>' for p in BRAND["palette"])
    values = bullets((f"<b>{e(v['name'])}:</b> {e(v['line'])}" for v in BRAND["values"]), "tight")
    style = bullets((e(line) for line in BRAND["visual_style"]), "tight")
    mark = (f'<div class="brandmark">{build.logo(56, COLOURS["Zümrüt"], "#fff")}<span>{e(BRAND["name"])}</span></div>'
            f'<p class="mid">Üç çubuklu küçük bir grafik: uygulamanın simgesi. Yazı tipi Segoe UI; başlıklar kalın.</p>')
    return slide("marka-kimligi", "AŞAMA 1 · MARKA KİMLİĞİ KARTI", "Renkler, değerler, görsel dil",
                 f'<div class="grid5">{swatches}</div><div class="grid3 even" style="margin-top:16px">'
                 f'<div class="box mid"><b class="t">Değerler</b>{values}</div><div class="box mid"><b class="t">Görsel dil</b>{style}</div>'
                 f'<div class="box"><b class="t">Logo ve yazı</b>{mark}</div></div>')


def strategy_slide() -> str:
    w, persona = BRAND["why_who_what_how"], BRAND["persona"]
    frame = bullets((f"<b>{label}:</b> {e(w[key])}" for label, key in
                     (("Neden", "neden"), ("Kime", "kime"), ("Ne", "ne"), ("Nasıl", "nasil"))), "tight")
    return slide("strateji", "AŞAMA 2 · STRATEJİ", "Neden, kime, ne, nasıl",
                 f'<div class="grid2 even"><div class="box">{frame}</div>'
                 f'<div class="box"><b class="t">Persona: {e(persona["name"])}, {persona["age"]}, {e(persona["city"])}</b>'
                 f'<p>{e(persona["job"])}. {e(persona["story"])}</p>'
                 f'<p style="margin-top:8px"><b>İhtiyaçları:</b> {e(joined(persona["needs"]))}.</p>'
                 f'<p style="margin-top:8px"><b>Kanalları:</b> {e(", ".join(persona["channels"]))}.</p></div></div>'
                 f'<div class="box mid" style="margin-top:16px"><b class="t">Marka hikâyesi</b>{e(BRAND["story"])}</div>')


def voice_slide() -> str:
    voice = BRAND["voice"]
    return slide("marka-sesi", "AŞAMA 2 · MARKA SESİ 1/3", "Sakin bir arkadaş gibi: sade, yargılamayan, somut",
                 f'<div class="grid2 even"><div class="box"><b class="t">Yapın</b>{bullets((e(x) for x in voice["do"]), "tight")}</div>'
                 f'<div class="box"><b class="t">Yapmayın</b>{bullets((e(x) for x in voice["dont"]), "tight")}</div></div>'
                 f'<div class="grid2 even" style="margin-top:18px"><div class="box"><b class="t">Kullanın</b>{e(", ".join(voice["use"]))}</div>'
                 f'<div class="box"><b class="t">Kullanmayın</b>{e(", ".join(voice["avoid"]))}</div></div>')


def voice_examples_slide() -> str:
    examples = "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td></tr>" for a, b in VOICE_EXAMPLES)
    return slide("ses-ornekleri", "AŞAMA 2 · MARKA SESİ 2/3", "Böyle değil, böyle; duruma göre ton",
                 f'<div class="grid2" style="grid-template-columns:1fr 1.25fr"><table><thead><tr><th>Böyle değil</th><th>Böyle</th></tr>'
                 f'</thead><tbody>{examples}</tbody></table><table><thead><tr><th>Durum</th><th>Ton</th><th>Örnek</th></tr></thead>'
                 f'<tbody>{situation_rows()}</tbody></table></div>')


def channels_slide() -> str:
    return slide("kanala-gore-ses", "AŞAMA 2 · MARKA SESİ 3/3", "Kanala göre ses ve yazım kuralları",
                 f'<div class="grid2" style="grid-template-columns:1.3fr 1fr"><table><thead><tr><th>Kanal</th><th>Sınır</th>'
                 f'<th>Nasıl konuşur</th></tr></thead><tbody>{channel_rows()}</tbody></table>'
                 f'<div class="box prompt tight"><b class="t">Yazım kuralları</b>{bullets((e(x) for x in writing_rules()), "tight")}'
                 f'<p style="margin-top:6px">{e(BRAND["voice"]["cta_note"])}</p></div></div>')


def pillars_slide() -> str:
    pillars = "".join(f'<div class="box"><b class="t">{e(p["name"])}</b>{e(p["goal"])}</div>' for p in BRAND["pillars"])
    measures = "".join(f"<tr><td><b>{e(m['channel'])}</b></td><td>{e(m['metric'])}</td></tr>" for m in BRAND["measures"]["channels"])
    return slide("icerik-sutunlari", "AŞAMA 2 · İÇERİK SÜTUNLARI", f"{len(BRAND['pillars'])} tema, her gönderi birine bağlı",
                 f'<div class="grid4 even">{pillars}</div><div class="grid2" style="margin-top:20px;grid-template-columns:1fr 1.3fr">'
                 f'<div class="box mid"><b class="t">Nasıl ölçülür</b>{e(BRAND["measures"]["note"])}</div>'
                 f'<table><thead><tr><th>Kanal</th><th>Ölçüt</th></tr></thead><tbody>{measures}</tbody></table></div>')


def calendar_slide() -> str:
    calendar = load("calendar.json")
    widths = "".join(f'<col style="width:{w}%">' for w in (16, 21, 12, 30, 13, 8))
    rows = "".join(f"<tr><td>{e(short_date(r['date']))}</td><td>{e(r['channel'])}</td><td>{e(r['format'])}</td>"
                   f"<td>{e(r['topic'])}</td><td>{e(PILLARS[r['pillar']]['name'])}</td><td>{e(r['status'])}</td></tr>" for r in calendar)
    first, last = build.date.fromisoformat(calendar[0]["date"]), build.date.fromisoformat(calendar[-1]["date"])
    start = str(first.day) if (first.year, first.month) == (last.year, last.month) else tr_date(first.isoformat())
    return slide("icerik-takvimi", "AŞAMA 3 · İÇERİK TAKVİMİ 1/2",
                 f"{len(calendar)} gün, {len(calendar)} içerik ({start}-{tr_date(last.isoformat())})",
                 f"<table><colgroup>{widths}</colgroup><thead><tr><th>Tarih</th><th>Kanal</th><th>Format</th><th>Konu</th>"
                 f"<th>Sütun</th><th>Durum</th></tr></thead><tbody>{rows}</tbody></table>"
                 '<p class="muted" style="font-size:14px;margin-top:8px">Saat, amaç, çağrı ve gerekçe sonraki slaytta; '
                 'dosya sütunu icerik-takvimi.xlsx içinde.</p>')


def calendar_reason_slide() -> str:
    calendar = load("calendar.json")
    widths = "".join(f'<col style="width:{w}%">' for w in (17, 21, 12, 50))
    rows = "".join(f"<tr><td>{e(short_date(r['date']))}<br>{e(r['time'])} · {e(r['channel'])}</td><td>{e(r['goal'])}</td>"
                   f"<td>{e(r['cta'])}</td><td>{e(r['rationale'])}</td></tr>" for r in calendar)
    return slide("takvim-gerekce", "AŞAMA 3 · İÇERİK TAKVİMİ 2/2", "Amaç, çağrı ve hedef kitleye bağlı gerekçe",
                 f'<table style="font-size:13px"><colgroup>{widths}</colgroup><thead><tr><th>Gün, saat, kanal</th><th>Amaç</th>'
                 f'<th>Çağrı</th><th>Gerekçe (Deniz için)</th></tr></thead><tbody>{rows}</tbody></table>'
                 '<p class="muted" style="font-size:13px;margin-top:6px">Saatler Deniz\'in gününe göre bir başlangıç tahmini; '
                 'ilk haftanın istatistikleriyle güncellenir.</p>')


def blog_slide() -> str:
    meta, body = checks.read_front_matter(CONTENT / "blog.md")
    prompt = load("prompts.json")["blog"]
    sections = [line[3:] for line in body.splitlines() if line.startswith("## ")]
    seo = (f'<p><b>Anahtar kelime:</b> {e(meta["keyword"])}<br><b>Adres:</b> /{e(meta["slug"])}<br>'
           f'<b>Açıklama ({len(meta["description"])} karakter):</b> {e(meta["description"])}</p>'
           f'<p style="margin-top:8px"><b>Bölümler:</b></p>{bullets((e(s) for s in sections), "tight plain")}'
           f'<p style="margin-top:8px">{checks.blog_word_count(body)} kelime. Tam metin sonraki iki slaytta ve '
           f'icerik-seti/blog.pdf içinde.</p>')
    costar = "".join(f"<b>{label}:</b> {e(prompt[key])}<br>" for label, key in
                     (("Bağlam", "context"), ("Hedef", "objective"), ("Üslup", "style"), ("Ton", "tone"), ("Kitle", "audience"),
                      ("Yanıt", "response")))
    return slide("blog", "AŞAMA 3 · BLOG", meta["title"],
                 f'<div class="grid2"><div class="box mid"><b class="t">SEO kartı</b>{seo}</div>'
                 f'<div class="box prompt tight"><b class="t">CO-STAR istemi</b>{costar}</div></div>')


def blog_text_slides() -> list[str]:
    """The whole post in two columns over two slides, split before step 4; its pictures stay in the PDF and the page."""
    meta, body = checks.read_front_matter(CONTENT / "blog.md")
    body = re.sub(r"^(# .*|!\[.*)$", "", body, flags=re.M)
    first, second = body.split("\n## 4.", 1)
    return [slide(f"blog-metni-{i}", f"AŞAMA 3 · BLOG METNİ {i}/2", meta["title"], f'<div class="blogtext">{markdown.markdown(half)}</div>')
            for i, half in enumerate((first, "## 4." + second), 1)]


def social_slides(images: dict) -> list[str]:
    social = load("social.json")
    return [slide(post["id"], f"AŞAMA 3 · SOSYAL MEDYA {i}/{len(social)}", f"{post['channel']}: {PILLARS[post['pillar']]['name']}",
                  f'<div class="grid3" style="grid-template-columns:330px 1fr 1fr"><img class="thumb" src="{images[post["image"]]}" alt="">'
                  f'<div class="box post" data-name="{e(post["id"])} metni">{e(post["text"])}</div>'
                  f'<div class="box"><b class="t">RTF istemi</b>{rtf(post["prompt"])}</div></div>')
            for i, post in enumerate(social, 1)]


def images_slide(images: dict) -> str:
    specs = load("media.json")["images"]
    with Image.open(SET / f"{specs[0]['id']}.png") as first:
        width, height = first.size
    cells = "".join(f'<div><img class="thumb" src="{images[img["id"]]}" alt="">'
                    f'<p class="muted" style="font-size:14px;margin-top:6px">{e(img["id"])}.png</p>'
                    f'<p class="alt"><b>Alt metin:</b> {e(img["alt"])}</p></div>' for img in specs)
    return slide("gorseller", "AŞAMA 3 · GÖRSELLER", f"Marka paletinde {len(specs)} görsel, {width}x{height}",
                 f'<div class="grid3">{cells}</div>')


def stories_slide(workdir: pathlib.Path) -> str:
    stories = {s["kind"]: s for s in load("media.json")["stories"]}
    poll, audio = stories["poll"], stories["audio"]
    story_video = SET / f"{audio['id']}.mp4"
    still = workdir / "story-still.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{build.duration(story_video) * 0.4:.2f}", "-i", str(story_video),
                    "-frames:v", "1", str(still)], check=True, capture_output=True, timeout=120)
    steps = joined([item.rstrip(".") for item in audio["items"]])
    text = (f'<b class="t">Cumartesi: anket</b><p>{e(poll["question"])} Seçenekler: {e(", ".join(poll["options"]))}. '
            f'Seçenekler Instagram\'ın anket çıkartmasıyla eklenir.</p>'
            f'<b class="t" style="margin-top:12px">Pazar: sesli hikâye ({seconds(build.duration(story_video))} sn)</b>'
            f'<p>{e(audio["headline"])}: {e(checks.tr_lower(steps[0]) + steps[1:])}. {e(audio["link"])} '
            f'Kartın altında: "{e(audio["disclosure"])}"</p><p style="margin-top:8px">İzleyin: {link(story_video)}</p>')
    return slide("hikayeler", "AŞAMA 3 · INSTAGRAM HİKÂYELERİ", "Cumartesi anketi ve pazar sesli hikâyesi",
                 f'<div class="grid3" style="grid-template-columns:220px 220px 1fr">'
                 f'<img class="story" src="{(SET / (poll["id"] + ".png")).as_uri()}" alt=""><img class="story" src="{still.as_uri()}" alt="">'
                 f'<div class="box mid">{text}</div></div>')


def media_slide(workdir: pathlib.Path) -> str:
    media = load("media.json")
    video, voice = SET / f"{media['video']['id']}.mp4", SET / f"{media['voiceover']['id']}.mp3"
    frames = "".join(f'<img src="{f.as_uri()}" alt="">' for f in sorted(FRAMES.glob("sahne-*.png")))
    narration = " ".join(s["narration"] for s in media["video"]["scenes"])
    video_wave = waveform(video, workdir / "video-wave.png").as_uri()
    voice_wave = waveform(voice, workdir / "voice-wave.png").as_uri()
    return slide("video-ve-ses", "AŞAMA 3 · VİDEO VE SES",
                 f"Dikey tanıtım videosu ({seconds(build.duration(video))} sn) ve seslendirme ({seconds(build.duration(voice))} sn)",
                 f'<div class="frames">{frames}</div><div class="grid2 even" style="margin-top:14px">'
                 f'<div class="box prompt tight"><b class="t">Video sesi: ekrandaki yazının aynısı</b>'
                 f'<img class="wave" src="{video_wave}" alt="">{e(narration)}</div>'
                 f'<div class="box prompt tight"><b class="t">Pazar seslendirmesi ({e(media["voiceover"]["voice"])})</b>'
                 f'<img class="wave" src="{voice_wave}" alt="">{e(media["voiceover"]["script"])}</div></div>'
                 f'<p class="mid" style="margin-top:10px">İzleyin: {link(video)} · Dinleyin: {link(voice)}</p>')


def prompts_slide() -> str:
    media = load("media.json")
    images = "".join(f'<div class="box"><b class="t">{e(img["id"])}.png</b>{rtf(img["prompt"], "prompt tight")}</div>'
                     for img in media["images"])
    return slide("istemler", "AŞAMA 3 · İSTEMLER", "Görsel, video ve ses istemleri (RTF tasarım özeti)",
                 f'<div class="grid3 even">{images}</div><div class="grid2 even" style="margin-top:14px">'
                 f'<div class="box"><b class="t">Tanıtım videosu</b>{rtf(media["video"]["prompt"], "prompt tight")}</div>'
                 f'<div class="box"><b class="t">Seslendirme</b>{rtf(media["voiceover"]["prompt"], "prompt tight")}</div></div>'
                 '<p class="muted" style="font-size:13px;margin-top:8px">Görseller, hikâyeler ve video bu özetlere göre marka '
                 'şablonundan (HTML) çizildi; ses edge-tts ile okundu.</p>')


def control_slide() -> str:
    rows = "".join(f"<tr><td>{e(r['piece'])}</td><td>{e(r['voice'])}</td><td>{e(r['numbers'])}</td>"
                   f"<td>{len(r['claims'])}</td><td>{e(r['rights_short'])}</td></tr>" for r in checklist_rows())
    notes = load("checklist.json")
    return slide("kontrol", "AŞAMA 4 · KONTROL", "Ses, telif ve halüsinasyon denetimi",
                 f'<div class="grid2" style="grid-template-columns:1.55fr 1fr"><table style="font-size:13px"><thead><tr><th>İçerik</th>'
                 f'<th>Marka sesi</th><th>Sayılar</th><th>Kaynaklı iddia</th><th>Telif</th></tr></thead><tbody>{rows}</tbody></table><div>'
                 f'<div class="box prompt tight"><b class="t">Parçalar arası tutarlılık</b>{bullets((e(x) for x in notes["consistency"]), "tight")}</div>'
                 f'<div class="box prompt tight" style="margin-top:12px"><b class="t">Ses hakkı</b>{e(notes["rights"]["audio"])}</div>'
                 f'<p class="muted" style="font-size:14px;margin-top:10px">Her iddianın kaynak dosyası ve satırı: kontrol-listesi.pdf, 2. sayfa</p></div></div>')


def files_slide() -> str:
    days = len(load("calendar.json"))
    files = bullets((e(x) for x in ("marka-stratejisi.pdf", "marka-sesi-rehberi.pdf", f"icerik-takvimi.xlsx ({days} gün)",
                                    "icerik-seti/: blog, görseller, hikâyeler, video, video kareleri, seslendirme",
                                    "ekran-goruntuleri/: içerik setinin ve kimlik kartının ekran görüntüleri",
                                    "kontrol-listesi.pdf", "sunum.pdf (bu sunum)",
                                    "sunum-slaytlar/: her slaytın PNG kopyası")), "tight")
    media = load("media.json")
    links = "".join(f'<p style="margin-top:10px">{label}:<br>{anchor}</p>' for label, anchor in (
        ("Panel", f'<a href="{e(BRAND["app_url"])}">{e(BRAND["app_url"])}</a>'),
        ("Kaynak kod", f'<a href="{e(REPO_URL)}">{e(REPO_URL)}</a>'),
        ("Tanıtım videosu", link(SET / f"{media['video']['id']}.mp4")),
        ("Seslendirme", link(SET / f"{media['voiceover']['id']}.mp3"))))
    return slide("teslim", "TESLİM", "Dosyalar ve bağlantılar",
                 f'<div class="grid2"><div class="box"><b class="t">Dosyalar</b>{files}</div>'
                 f'<div class="box"><b class="t">Bağlantılar</b>{links}</div></div>')


def deck() -> pathlib.Path:
    images = {img["id"]: (SET / f"{img['id']}.png").as_uri() for img in load("media.json")["images"]}
    shots_dir = OUT / "ekran-goruntuleri"
    shots_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        workdir = pathlib.Path(tmp)
        slides = [cover_slide(), analysis_slide(), identity_slide(), strategy_slide(), voice_slide(), voice_examples_slide(),
                  channels_slide(), pillars_slide(), calendar_slide(), calendar_reason_slide(), blog_slide(), *blog_text_slides(),
                  *social_slides(images), images_slide(images), stories_slide(workdir), media_slide(workdir), prompts_slide(),
                  control_slide(), files_slide()]
        slides = [html.replace(SLIDE_NUMBER, str(number)) for number, html in enumerate(slides, 1)]
        title = "ContentFlow: Harcama Takip Paneli"
        page_path = build.write_checked(build.page(title, DECK_CSS, "".join(slides)), workdir / "sunum.html", 1300, 800)
        target = OUT / "sunum.pdf"
        render.html_to_pdf(page_path, target)
        keys = [re.search(r'data-name="([^"]+)"', html).group(1) for html in slides]
        slide_pngs(target, keys)
        # The screenshots: the chosen slides alone on one tall page, captured at twice the size and cut apart.
        by_key = dict(zip(keys, slides))
        chosen = [by_key[key] for key in screenshot_keys()]
        shot_page = workdir / "shots.html"
        shot_page.write_text(build.page(title, DECK_CSS, "".join(chosen)), encoding="utf-8")
        tall = workdir / "shots.png"
        render.html_to_png(shot_page, tall, 1280, 720 * len(chosen), scale=SHOT_SCALE)
        for old in shots_dir.glob("*.png"):
            old.unlink()
        with Image.open(tall) as whole:
            height = 720 * SHOT_SCALE
            for i, name in enumerate(screenshot_names()):
                whole.crop((0, i * height, whole.width, (i + 1) * height)).save(shots_dir / f"{name}.png")
    return target


def build_all() -> list[pathlib.Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    return [strategy(), voice_guide(), checklist(), *blog(), deck()]
