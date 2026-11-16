"""Build every deliverable from the sources in brand/ and content/.

python tools/build.py            all deliverables
python tools/build.py images     only the three images (also: voice, stories, video, calendar, docs, panel)

Nothing is written while a content check fails, and every rendered page must pass the fit check: no text outside its
box, no heading past its line limit. Output goes to deliverables/.
"""
import html
import json
import math
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import checks  # noqa: E402
import panel  # noqa: E402
import render  # noqa: E402

ROOT = checks.ROOT
BRAND = checks.BRAND
CONTENT = ROOT / "content"
OUT = ROOT / "deliverables"
SET = OUT / "icerik-seti"
FRAMES = SET / "video-kareleri"
PANEL_SHOT = ROOT / "assets" / "panel-2x.png"
# Card interiors in the 2x panel screenshot (left, top, right, bottom), 24 px inside each card so no border shows.
# "breakdown-top" is the title and the five largest rows, big enough to read on a phone.
SCREENSHOT_CROPS = {"form": (184, 576, 850, 1272), "breakdown": (184, 1882, 850, 2772),
                    "breakdown-top": (184, 1882, 850, 2424)}
COLOURS = {p["name"]: p["hex"] for p in BRAND["palette"]}
PILLARS = {p["id"]: p for p in BRAND["pillars"]}
TR_DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
TR_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def load(name: str):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def e(text) -> str:
    return html.escape(str(text))


# A word with a hyphen inside (e-posta, 20-35, tr-TR-EmelNeural) may not break at the hyphen.
HYPHENATED = re.compile(r"[^\s<>]*\w-\w[^\s<>]*")
# A number stays on the line of the word or unit sign after it: "6 saniye", "59,99 $".
NUMBER_AND_WORD = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)*) (?=[^\W\d]|[$%€₺])")
# "de", "da", "ki" and the question particle are written apart but read with the word before them:
# "ya da", "siz de", "var mı" never start a line with the particle.
CLITIC = re.compile(r"(?<=\w) (d[ae]|ki|m[iıuü])(?!\w)")


def keep_together(escaped: str) -> str:
    escaped = CLITIC.sub(r"&nbsp;\1", NUMBER_AND_WORD.sub(r"\1&nbsp;", escaped))
    return HYPHENATED.sub(lambda m: f'<span class="nw">{m.group(0)}</span>', escaped)


def keep_together_html(markup: str) -> str:
    """keep_together on finished HTML: only the text between tags changes, never a tag or an attribute."""
    parts = re.split(r"(<[^>]*>)", markup)
    return "".join(part if part.startswith("<") else keep_together(part) for part in parts)


def tr_date(iso: str) -> str:
    day = date.fromisoformat(iso)
    return f"{day.day} {TR_MONTHS[day.month - 1]} {day.year}"


def tr_day(iso: str) -> str:
    return TR_DAYS[date.fromisoformat(iso).weekday()]


BASE_CSS = f"""
:root {{ --zumrut: {COLOURS['Zümrüt']}; --gece: {COLOURS['Gece']}; --kagit: {COLOURS['Kâğıt']};
        --kehribar: {COLOURS['Kehribar']}; --sis: {COLOURS['Sis']}; }}
* {{ box-sizing: border-box; margin: 0; }}
html {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
body {{ font-family: "Segoe UI", sans-serif; color: var(--gece); }}
/* Words never break in the middle; a word that does not fit shows up as overflow in the fit report. */
* {{ hyphens: manual; overflow-wrap: normal; word-break: normal; }}
.nw {{ white-space: nowrap; }}
/* No single word alone on the last line of a paragraph; headings split into even lines. */
p, li, td, th, .box, .card {{ text-wrap: pretty; }}
h1, h2, h3 {{ text-wrap: balance; }}
"""


def page(title: str, css: str, body: str, head: str = "") -> str:
    """A whole page. The keep-together rules run over all of the body, so text written straight into markup is covered."""
    return (f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>{e(title)}</title>{head}'
            f"<style>{BASE_CSS}{css}</style></head><body>{keep_together_html(body)}{render.FIT_SCRIPT}</body></html>")


def text_on(background: str) -> str:
    """The text colour the brand pairs with a background (brand.json text_pairs, all at least 4.5:1)."""
    return next(pair["text"] for pair in BRAND["text_pairs"] if pair["background"] == background)


def write_checked(html_text: str, path: pathlib.Path, width: int, height: int) -> pathlib.Path:
    """Write the page and refuse it unless every text fits."""
    path.write_text(html_text, encoding="utf-8")
    problems = render.fit_report(path, width, height)
    if problems:
        raise SystemExit(f"{path.name} does not fit: {problems}")
    return path


def logo(size: int, background: str, bars: str) -> str:
    """The panel's mark: a small three-bar chart in a rounded square, as in the app's favicon."""
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" '
            f'fill="{background}"/><path d="M9 22V14M16 22V9M23 22v-5" stroke="{bars}" stroke-width="3" stroke-linecap="round"/></svg>')


def crop_panel(name: str, workdir: pathlib.Path) -> pathlib.Path:
    target = workdir / f"panel-{name}.png"
    Image.open(PANEL_SHOT).crop(SCREENSHOT_CROPS[name]).save(target)
    return target


# ---------- images ----------

IMAGE_CSS = """
.canvas { width: 1080px; height: 1080px; padding: 88px; display: flex; flex-direction: column; overflow: hidden; }
.eyebrow { font-size: 28px; font-weight: 700; letter-spacing: .14em; }
.headline { font-size: 72px; font-weight: 700; line-height: 1.12; margin-top: 22px; }
.body { font-size: 36px; line-height: 1.35; margin-top: 22px; }
.footer { margin-top: auto; display: flex; align-items: center; gap: 18px; font-size: 26px; }
.footer b { font-weight: 700; }
.dark { background: var(--gece); color: var(--kagit); } .dark .eyebrow { color: var(--kehribar); }
.light { background: var(--kagit); color: var(--gece); } .light .eyebrow { color: var(--zumrut); }
.green { background: var(--zumrut); color: #fff; } .green .eyebrow { color: var(--kagit); }
.shot { margin: 34px auto 0; height: 560px; border-radius: 28px; background: #fff; padding: 18px; box-shadow: 0 12px 40px rgba(0,0,0,.35); }
.shot img { height: 100%; display: block; border-radius: 14px; }
ol.steps { list-style: none; padding: 0; margin-top: 54px; display: grid; gap: 34px; }
ol.steps li { display: flex; align-items: center; gap: 28px; font-size: 38px; line-height: 1.3; }
ol.steps .n { flex: none; width: 72px; height: 72px; border-radius: 50%; background: var(--zumrut); color: #fff;
  font-size: 36px; font-weight: 700; display: grid; place-items: center; }
ul.checks { list-style: none; padding: 0; margin-top: 54px; display: grid; gap: 26px; }
ul.checks li { font-size: 44px; font-weight: 600; display: flex; align-items: center; gap: 22px; }
ul.checks svg { flex: none; }
.pill { margin-top: 56px; align-self: flex-start; background: var(--kagit); color: var(--zumrut); font-size: 34px; font-weight: 700;
  padding: 18px 40px; border-radius: 999px; }
.light .url { color: var(--sis); }
/* Without a screenshot the text block sits in the middle of the free space, not under the top edge. */
.light .eyebrow, .green .eyebrow { margin-top: auto; }
"""

CHECK_MARK = '<svg width="44" height="44" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>'


def image_html(spec: dict, workdir: pathlib.Path) -> str:
    theme = spec["theme"]
    mark = {"dark": logo(48, COLOURS["Zümrüt"], "#fff"), "light": logo(48, COLOURS["Zümrüt"], "#fff"),
            "green": logo(48, COLOURS["Kâğıt"], COLOURS["Zümrüt"])}[theme]
    parts = [f'<div class="eyebrow" data-max-lines="1">{e(spec["eyebrow"])}</div>',
             f'<h1 class="headline" data-max-lines="2" data-name="headline">{e(spec["headline"])}</h1>']
    if spec.get("body"):
        parts.append(f'<p class="body" data-max-lines="2" data-name="body">{e(spec["body"])}</p>')
    if spec.get("screenshot"):
        shot = crop_panel(spec["screenshot"], workdir)
        parts.append(f'<div class="shot"><img src="{shot.as_uri()}" alt=""></div>')
    if theme == "light":
        items = "".join(f'<li><span class="n">{i}</span><span data-max-lines="1" data-name="item {i}">{e(text)}</span></li>'
                        for i, text in enumerate(spec["items"], 1))
        parts.append(f'<ol class="steps">{items}</ol>')
    if theme == "green":
        items = "".join(f'<li>{CHECK_MARK}<span data-max-lines="1">{e(text)}</span></li>' for text in spec["items"])
        parts.append(f'<ul class="checks">{items}</ul><div class="pill" data-max-lines="1">{e(BRAND["cta"]["primary"])}</div>')
    footer = (f'<div class="footer">{mark}<span data-max-lines="1" data-name="footer"><b>{e(BRAND["name"])}</b> · '
              f'<span class="url">{e(BRAND["short_url"])}</span></span></div>')
    return page(spec["headline"], IMAGE_CSS, f'<main class="canvas {theme}">{"".join(parts)}{footer}</main>')


def build_images() -> list[pathlib.Path]:
    SET.mkdir(parents=True, exist_ok=True)
    built = []
    with tempfile.TemporaryDirectory() as tmp:
        workdir = pathlib.Path(tmp)
        for spec in load("media.json")["images"]:
            page_path = write_checked(image_html(spec, workdir), workdir / f"{spec['id']}.html", 1080, 1080)
            target = SET / f"{spec['id']}.png"
            render.html_to_png(page_path, target, 1080, 1080)
            built.append(target)
    return built


# ---------- voice ----------

# Platforms play speech at about -14 LUFS; edge-tts returns about -19, which sounds quiet next to other posts.
LOUDNESS = "loudnorm=I=-14:TP=-1.5:LRA=11"


def loud(source: pathlib.Path, target: pathlib.Path) -> pathlib.Path:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-af", LOUDNESS, "-ar", "48000", "-b:a", "128k",
                    str(target)], check=True, capture_output=True, timeout=120)
    return target


def tts(text: str, voice: str, rate: str, target: pathlib.Path) -> None:
    subprocess.run([sys.executable, "-m", "edge_tts", "--voice", voice, f"--rate={rate}", "--text", text,
                    "--write-media", str(target)], check=True, capture_output=True, timeout=120)


def trim_silence(source: pathlib.Path, target: pathlib.Path) -> pathlib.Path:
    """Cut the silence before and after the speech (edge-tts leaves about 1 s at the end of every clip)."""
    edge = "silenceremove=start_periods=1:start_threshold=-45dB"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-af", f"{edge},areverse,{edge},areverse", str(target)],
                   check=True, capture_output=True, timeout=120)
    return target


SENTENCE_GAP = 0.25  # seconds between two sentences of one video scene
VOICEOVER_GAP = 0.6  # the voiceover has no picture, so its sentences get a longer, still natural pause


def speak(text: str, voice: str, rate: str, workdir: pathlib.Path, name: str, gap: float = SENTENCE_GAP) -> pathlib.Path:
    """Each sentence read on its own, trimmed and joined with a set gap: edge-tts leaves about 1 s between sentences."""
    parts = []
    for i, sentence in enumerate(re.split(r"(?<=[.?!])\s+", text.strip())):
        raw = workdir / f"{name}-{i}.mp3"
        tts(sentence, voice, rate, raw)
        parts.append(trim_silence(raw, workdir / f"{name}-{i}.wav"))
    inputs = [arg for part in parts for arg in ("-i", str(part))]
    pads = [f"[{i}:a]aresample=48000{f',apad=pad_dur={gap}' if i < len(parts) - 1 else ''}[s{i}]"
            for i in range(len(parts))]
    joined = "".join(f"[s{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[a]"
    target = workdir / f"{name}.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(pads + [joined]), "-map", "[a]",
                    str(target)], check=True, capture_output=True, timeout=120)
    return target


def duration(path: pathlib.Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def build_voice() -> pathlib.Path:
    spec = load("media.json")["voiceover"]
    SET.mkdir(parents=True, exist_ok=True)
    target = SET / f"{spec['id']}.mp3"
    with tempfile.TemporaryDirectory() as tmp:
        workdir = pathlib.Path(tmp)
        voice = workdir / target.name
        loud(speak(spec["script"], spec["voice"], spec["rate"], workdir, "voiceover", VOICEOVER_GAP), voice)
        problem = length_problem(duration(voice), spec, "voiceover")
        if problem:
            raise SystemExit(problem)
        shutil.copy(voice, target)
    return target


# ---------- video ----------

FPS = 30
# Fixed places in the 1080x1920 frame. The bottom 420 px sit under the Shorts and Reels controls, so nothing goes there.
CARD = {"left": 96, "top": 500, "width": 888, "height": 860, "radius": 28}
FOOTER_TOP = 1400
TEXT_FADE = 0.3  # seconds for the scene text to fade in
PUSH_IN = 0.03  # a text scene grows by this share over its length, so no frame stands still
EDGE_TIME = 0.3  # the pan waits this long at both ends
SPEECH_LEAD, SPEECH_TAIL = 0.15, 0.25  # silence before and after each sentence

SCENE_CSS = """
.canvas { position: relative; width: 1080px; height: 1920px; overflow: hidden; background: var(--gece); color: var(--kagit); }
.canvas.green { background: var(--zumrut); color: #fff; }
.say { font-size: 72px; font-weight: 700; line-height: 1.12; white-space: pre-line; }
.quiet .say { visibility: hidden; }
.top { position: absolute; left: 96px; right: 96px; top: 160px; }
.middle { position: absolute; left: 96px; right: 96px; top: 160px; height: 1180px; display: flex; flex-direction: column;
  justify-content: center; }
.footer { position: absolute; left: 96px; right: 96px; top: FOOTER_TOPpx; display: flex; align-items: center; gap: 22px;
  font-size: 40px; }
.footer b { font-weight: 700; }
""".replace("FOOTER_TOP", str(FOOTER_TOP))

# Scenes that show the panel moving in the card; the others are text on brand colour.
PANEL_SCENES = ("form", "breakdown")


def scene_html(scene: dict, quiet: bool) -> str:
    """One scene without the panel frames, which are laid on later. quiet hides the text for the fade-in."""
    visual = scene["visual"]
    theme = "green" if visual in ("promise", "cta") else ""
    mark = logo(64, COLOURS["Kâğıt"], COLOURS["Zümrüt"]) if theme else logo(64, COLOURS["Zümrüt"], "#fff")
    footer = f'<div class="footer">{mark}<b data-max-lines="1">{e(BRAND["name"])}</b></div>'
    # Every line written in the scene text stays one line on screen.
    lines = len(scene["text"].splitlines())
    text = f'<p class="say" data-max-lines="{lines}" data-name="scene text">{e(scene["text"])}</p>'
    inner = f'<div class="{"top" if visual in PANEL_SCENES else "middle"}">{text}</div>'
    return page(scene["text"], SCENE_CSS, f'<main class="canvas {theme} {"quiet" if quiet else ""}">{inner}{footer}</main>')


def smooth(x: float) -> float:
    """Ease in and out over 0..1."""
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def step_at(t: float, steps: list[dict]) -> int:
    """The captured form step on screen at time t; the last one stays until the scene ends."""
    end = 0.0
    for index, step in enumerate(steps):
        end += step["seconds"]
        if t < end:
            return index
    return len(steps) - 1


def pan_offset(t: float, length: float, top: int, bottom: int, window: int) -> int:
    """How far down the page the card shows at time t: from the top of the region to its bottom, eased."""
    return round(top + (bottom - window - top) * smooth((t - EDGE_TIME) / (length - 2 * EDGE_TIME)))


def scene_lengths(speech: list[float], motion: list[float], spec: dict) -> list[float]:
    """Each scene lasts its sentence with short pauses, or its motion if that is longer. Only when the whole is still
    under the brief's minimum do the scenes share the missing time."""
    lengths = [max(s + SPEECH_LEAD + SPEECH_TAIL, m) for s, m in zip(speech, motion)]
    missing = spec["min_seconds"] + 0.5 - sum(lengths)
    if missing > 0:
        lengths = [length + missing / len(lengths) for length in lengths]
    return [round(length, 2) for length in lengths]


def rounded(image: Image.Image) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width - 1, image.height - 1), radius=CARD["radius"], fill=255)
    image.putalpha(mask)
    return image


class Scene:
    """Draws the frames of one scene: text fading in, then either a slow push-in or the panel moving in the card."""

    def __init__(self, scene: dict, length: float, workdir: pathlib.Path, index: int):
        self.visual, self.length = scene["visual"], length
        layers = []
        for quiet in (True, False):
            path = write_checked(scene_html(scene, quiet), workdir / f"scene{index}-{int(quiet)}.html", 1080, 1920)
            png = path.with_suffix(".png")
            render.html_to_png(path, png, 1080, 1920)
            layers.append(Image.open(png).convert("RGB"))
        self.quiet, self.full = layers
        self.timeline = json.loads(panel.TIMELINE.read_text(encoding="utf-8"))
        if self.visual == "form":
            self.steps = self.timeline["form"]
            self.cards = [rounded(Image.open(panel.VIDEO / s["file"]).convert("RGB")) for s in self.steps]
        if self.visual == "breakdown":
            self.page_image = Image.open(panel.VIDEO / self.timeline["pan"]["file"]).convert("RGB")

    def motion(self) -> float:
        return sum(s["seconds"] for s in self.steps) if self.visual == "form" else 0.0

    def frame(self, t: float) -> Image.Image:
        image = Image.blend(self.quiet, self.full, smooth(t / TEXT_FADE))
        if self.visual == "breakdown":
            pan = self.timeline["pan"]
            y = pan_offset(t, self.length, pan["top"], pan["bottom"], CARD["height"])
            card = rounded(self.page_image.crop((0, y, CARD["width"], y + CARD["height"])))
            image.paste(card, (CARD["left"], CARD["top"]), card)
            return image
        if self.visual == "form":
            card = self.cards[step_at(t, self.steps)]
            image.paste(card, (CARD["left"], CARD["top"] + (CARD["height"] - card.height) // 2), card)
        # Typing changes only a few pixels, so the form grows slowly too, as the text scenes do.
        scale = 1 + PUSH_IN * t / self.length
        size = (round(1080 * scale), round(1920 * scale))
        grown = image.resize(size, Image.BILINEAR)
        left, top = (size[0] - 1080) // 2, (size[1] - 1920) // 2
        return grown.crop((left, top, left + 1080, top + 1920))

    def still(self) -> Image.Image:
        """The frame shown on the presentation: the filled form before the click, or the scene's last frame."""
        if self.visual == "form":
            index = next(i for i, s in enumerate(self.steps) if s["still"])
            return self.frame(sum(s["seconds"] for s in self.steps[:index]) + 0.01)
        return self.frame(self.length - 1 / FPS)


def encode(frames, fps: int, audio: pathlib.Path, target: pathlib.Path) -> pathlib.Path:
    """1080x1920 frames from Pillow and an audio file into an H.264 and AAC mp4."""
    encoder = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1080x1920",
                                "-r", str(fps), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "medium",
                                "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest",
                                "-movflags", "+faststart", str(target)], stdin=subprocess.PIPE)
    try:
        for frame in frames:
            encoder.stdin.write(frame.tobytes())
    finally:
        encoder.stdin.close()
        encoder.wait(timeout=600)
    if encoder.returncode:
        raise SystemExit(f"ffmpeg stopped with {encoder.returncode}")
    return target


def build_video() -> pathlib.Path:
    spec = load("media.json")["video"]
    SET.mkdir(parents=True, exist_ok=True)
    target = SET / f"{spec['id']}.mp4"
    with tempfile.TemporaryDirectory() as tmp:
        workdir = pathlib.Path(tmp)
        voices = []
        for i, scene in enumerate(spec["scenes"]):
            voices.append(speak(scene["narration"], spec["voice"], spec["rate"], workdir, f"scene{i}"))
        speech = [duration(v) for v in voices]
        scenes = [Scene(scene, 0.0, workdir, i) for i, scene in enumerate(spec["scenes"])]
        lengths = scene_lengths(speech, [s.motion() for s in scenes], spec)
        for scene, length in zip(scenes, lengths):
            scene.length = length
        # The sentences one after another, each SPEECH_LEAD into its scene, then made as loud as the platforms play.
        inputs, filters = [], []
        for i, (voice, length) in enumerate(zip(voices, lengths)):
            inputs += ["-i", str(voice)]
            lead = int(SPEECH_LEAD * 1000)
            filters.append(f"[{i}:a]aresample=48000,adelay={lead}|{lead},apad,atrim=0:{length}[a{i}]")
        joined = "".join(f"[a{i}]" for i in range(len(voices)))
        filters.append(f"{joined}concat=n={len(voices)}:v=0:a=1,{LOUDNESS}[a]")
        audio = workdir / "audio.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters), "-map", "[a]",
                        "-ar", "48000", str(audio)], check=True, capture_output=True, timeout=300)
        frames = (scene.frame(n / FPS) for scene in scenes for n in range(round(scene.length * FPS)))
        encode(frames, FPS, audio, workdir / "video.mp4")
        problem = length_problem(duration(workdir / "video.mp4"), spec, "video")
        if problem:
            raise SystemExit(problem)
        # Only a video that passed replaces the old one, together with its stills: the presentation shows them.
        FRAMES.mkdir(parents=True, exist_ok=True)
        for old in FRAMES.glob("sahne-*.png"):
            old.unlink()
        for i, scene in enumerate(scenes, 1):
            scene.still().save(FRAMES / f"sahne-{i}.png")
        shutil.copy(workdir / "video.mp4", target)
    return target


# ---------- stories ----------

# Instagram covers about 250 px at the top and 340 px at the bottom of a story with its own controls.
STORY_CSS = """
.canvas { position: relative; width: 1080px; height: 1920px; overflow: hidden; padding: 300px 96px 0; }
.dark { background: var(--gece); color: var(--kagit); } .light { background: var(--kagit); color: var(--gece); }
.eyebrow { font-size: 30px; font-weight: 700; letter-spacing: .14em; }
.dark .eyebrow { color: var(--kehribar); } .light .eyebrow { color: var(--zumrut); }
.headline { font-size: 76px; font-weight: 700; line-height: 1.12; margin-top: 26px; }
.sticker { height: 560px; margin-top: 64px; }
.hint { font-size: 38px; margin-top: 48px; opacity: .85; }
ol.steps { list-style: none; padding: 0; margin-top: 64px; display: grid; gap: 36px; }
ol.steps li { display: flex; align-items: center; gap: 30px; font-size: 46px; line-height: 1.25; }
ol.steps .n { flex: none; width: 84px; height: 84px; border-radius: 50%; background: var(--zumrut); color: #fff;
  font-size: 42px; font-weight: 700; display: grid; place-items: center; }
.link { margin-top: 64px; align-self: flex-start; display: inline-block; background: var(--zumrut); color: #fff; font-size: 40px;
  font-weight: 700; padding: 22px 44px; border-radius: 999px; }
.note { font-size: 32px; color: var(--sis); margin-top: 30px; }
.footer { position: absolute; left: 96px; right: 96px; top: 1500px; display: flex; align-items: center; gap: 22px; font-size: 40px; }
.footer b { font-weight: 700; }
"""
STORY_FPS = 15
# The audio story's progress bar, drawn on every frame so the card is never a still picture.
STORY_BAR = {"left": 96, "top": 1430, "width": 888, "height": 14}


def story_html(story: dict) -> str:
    theme = "dark" if story["kind"] == "poll" else "light"
    mark = logo(64, COLOURS["Zümrüt"], "#fff")
    parts = [f'<div class="eyebrow" data-max-lines="1">{e(story["eyebrow"])}</div>']
    if story["kind"] == "poll":
        # The options come from Instagram's own poll sticker, placed in this empty space; drawn here they would show twice.
        parts += [f'<h1 class="headline" data-max-lines="3" data-name="question">{e(story["question"])}</h1>',
                  f'<div class="sticker"></div><p class="hint" data-max-lines="2">{e(story["hint"])}</p>']
    else:
        steps = "".join(f'<li><span class="n">{i}</span><span data-max-lines="1" data-name="step {i}">{e(text)}</span></li>'
                        for i, text in enumerate(story["items"], 1))
        parts += [f'<h1 class="headline" data-max-lines="3" data-name="headline">{e(story["headline"])}</h1>',
                  f'<ol class="steps">{steps}</ol><div class="link" data-max-lines="1">{e(story["link"])}</div>',
                  f'<p class="note" data-max-lines="1">{e(story["disclosure"])}</p>']
    footer = f'<div class="footer">{mark}<b data-max-lines="1">{e(BRAND["name"])}</b></div>'
    return page(story.get("question") or story["headline"], STORY_CSS, f'<main class="canvas {theme}">{"".join(parts)}{footer}</main>')


def progress_frame(card: Image.Image, share: float) -> Image.Image:
    """The card with the progress bar filled to share (0 to 1)."""
    frame = card.copy()
    draw = ImageDraw.Draw(frame)
    x, y, width, height = STORY_BAR["left"], STORY_BAR["top"], STORY_BAR["width"], STORY_BAR["height"]
    draw.rounded_rectangle((x, y, x + width, y + height), radius=height // 2, fill="#CAD5E2")
    filled = round(width * min(max(share, 0.0), 1.0))
    if filled >= height:
        draw.rounded_rectangle((x, y, x + filled, y + height), radius=height // 2, fill=COLOURS["Zümrüt"])
    return frame


def build_stories() -> list[pathlib.Path]:
    """The two Instagram stories: the poll card, and the Sunday voiceover on its own card with a progress bar."""
    media = load("media.json")
    voice = SET / f"{media['voiceover']['id']}.mp3"
    built = []
    with tempfile.TemporaryDirectory() as tmp:
        workdir = pathlib.Path(tmp)
        for story in media["stories"]:
            card = workdir / f"{story['id']}.png"
            render.html_to_png(write_checked(story_html(story), workdir / f"{story['id']}.html", 1080, 1920), card, 1080, 1920)
            if story["kind"] == "poll":
                target = SET / f"{story['id']}.png"
                shutil.copy(card, target)
            else:
                still = Image.open(card).convert("RGB")
                count = math.ceil(duration(voice) * STORY_FPS)
                frames = (progress_frame(still, n / (count - 1)) for n in range(count))
                target = SET / f"{story['id']}.mp4"
                shutil.copy(encode(frames, STORY_FPS, voice, workdir / "story.mp4"), target)
            built.append(target)
    return built


def length_problem(seconds: float, spec: dict, name: str) -> str | None:
    """The limits in media.json: the brief wants a 15-20 s video, the voiceover prompt about 30 s."""
    if spec["min_seconds"] <= seconds <= spec["max_seconds"]:
        return None
    return f"{name} is {seconds:.1f} s, {spec['min_seconds']} to {spec['max_seconds']} s wanted"


# ---------- calendar ----------

CALENDAR_COLUMNS = [("Tarih", 13), ("Gün", 11), ("Saat", 8), ("Kanal", 22), ("Format", 18), ("Konu", 40), ("İçerik sütunu", 20),
                    ("Amaç", 28), ("Çağrı", 20), ("Gerekçe (hedef kitle)", 64), ("Dosya", 37), ("Durum", 13)]


def piece_files() -> dict:
    """The file that holds each calendar piece; a row without a piece carries its text in the row itself."""
    media = load("media.json")
    files = {"blog": "icerik-seti/blog.pdf", media["video"]["id"]: f"icerik-seti/{media['video']['id']}.mp4",
             media["voiceover"]["id"]: f"icerik-seti/{media['voiceover']['id']}.mp3"}
    for post in load("social.json"):
        files[post["id"]] = f"icerik-seti/{post['image']}.png ve sunum.pdf (metin)"
    for story in media["stories"]:
        files[story["id"]] = f"icerik-seti/{story['id']}.{'png' if story['kind'] == 'poll' else 'mp4'}"
    return files


def build_calendar() -> pathlib.Path:
    OUT.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    sheet = book.active
    sheet.title = "7 günlük takvim"
    header_fill = PatternFill("solid", fgColor=COLOURS["Zümrüt"][1:])
    thin = Side(style="thin", color="CAD5E2")
    for column, (title, width) in enumerate(CALENDAR_COLUMNS, 1):
        cell = sheet.cell(row=1, column=column, value=title)
        cell.font = Font(name="Segoe UI", bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
        sheet.column_dimensions[cell.column_letter].width = width
    files = piece_files()
    for r, row in enumerate(load("calendar.json"), 2):
        values = [date.fromisoformat(row["date"]), tr_day(row["date"]), row["time"], row["channel"], row["format"], row["topic"],
                  PILLARS[row["pillar"]]["name"], row["goal"], row["cta"], row["rationale"], files.get(row["piece"], "Metin bu satırda"),
                  row["status"]]
        for column, value in enumerate(values, 1):
            cell = sheet.cell(row=r, column=column, value=value)
            cell.font = Font(name="Segoe UI")
            cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True, indent=1)
            cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)
        sheet.cell(row=r, column=1).number_format = "DD.MM.YYYY"
    sheet.freeze_panes = "A2"
    sheet.row_dimensions[1].height = 30
    # Printed or saved as PDF: A4 turned sideways, every column on one page width, the header on every page.
    sheet.page_setup.orientation = sheet.ORIENTATION_LANDSCAPE
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.print_title_rows = "1:1"
    target = OUT / "icerik-takvimi.xlsx"
    book.save(target)
    return target


# ---------- documents (strategy, voice guide, checklist, blog, deck) are built by docs.py ----------

def build_docs() -> list[pathlib.Path]:
    import docs  # noqa: PLC0415  (docs.py needs the images and video frames to exist first)
    return docs.build_all()


def visible_text(spec: dict, skip=("id", "kind", "theme", "screenshot", "prompt")) -> str:
    """Every word of an image or story spec that a reader meets, alt text included."""
    return "\n".join(value if isinstance(value, str) else "\n".join(value) for key, value in spec.items() if key not in skip)


def published_texts() -> dict:
    """Every published piece as the text a reader meets, keyed like the checks and the calendar."""
    media = load("media.json")
    texts = {"blog": checks.read_front_matter(CONTENT / "blog.md")[1]}
    texts.update({post["id"]: post["text"] for post in load("social.json")})
    texts.update({spec["id"]: visible_text(spec) for spec in media["images"] + media["stories"]})
    texts["video"] = "\n".join(s["text"] + "\n" + s["narration"] for s in media["video"]["scenes"])
    texts["voiceover"] = media["voiceover"]["script"]
    for row in load("calendar.json"):
        texts[f"calendar {row['date']}"] = "\n".join([row["topic"], row["goal"], row["rationale"]])
    return texts


def content_problems() -> dict:
    """Every published text through the checks; the build stops on the first non-empty list."""
    meta, body = checks.read_front_matter(CONTENT / "blog.md")
    found = {"blog": checks.blog_problems(meta, body)}
    for post in load("social.json"):
        found[post["id"]] = checks.post_problems(post)
    for piece, text in published_texts().items():
        if piece not in found:
            found[piece] = checks.voice_problems(text)
    scenes = load("media.json")["video"]["scenes"]
    found["video"] += [f"scene {i}: the screen and the voice say different things"
                       for i, s in enumerate(scenes, 1) if not checks.same_words(s["text"], s["narration"])]
    return {piece: problems for piece, problems in found.items() if problems}


def capture_panel() -> list[pathlib.Path]:
    """From the live app with its sample data: the screenshot behind the images and the blog, and the video frames."""
    render.url_to_png(BRAND["sample_url"], PANEL_SHOT, 1280, 1520, scale=2)
    panel.capture(BRAND["sample_url"])
    return [PANEL_SHOT, panel.TIMELINE]


STEPS = {"images": build_images, "voice": build_voice, "stories": build_stories, "video": build_video, "calendar": build_calendar, "docs": build_docs,
         "panel": capture_panel}
# "panel" runs only when named: it reads the live site, and the screenshot in assets/ is the one the outputs were built from.
DEFAULT_STEPS = ["images", "voice", "stories", "video", "calendar", "docs"]


def main(argv: list[str]) -> None:
    problems = content_problems()
    if problems:
        raise SystemExit(f"content checks failed: {json.dumps(problems, ensure_ascii=False, indent=2)}")
    before = render.windowed_edges()
    for name in argv or DEFAULT_STEPS:
        result = STEPS[name]()
        print(name, ":", result)
    after = render.windowed_edges()
    if after != before:
        raise SystemExit(f"a visible Edge window appeared: {before} before, {after} after")


if __name__ == "__main__":
    main(sys.argv[1:])
