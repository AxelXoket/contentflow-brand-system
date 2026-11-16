"""The built files in deliverables/: sizes, lengths, page counts, and every printed word traced back to a source."""
import json
import re
import subprocess
import unittest
from datetime import date

import fitz
from openpyxl import load_workbook
from PIL import Image

from tests import ROOT

import build
import checks
import docs

OUT = ROOT / "deliverables"
SOURCES = [*ROOT.glob("brand/*.json"), *ROOT.glob("content/*"), *ROOT.glob("tools/*.py")]
LETTERS = re.compile(r"[^\W\d_]+")
NUMBER_TOKEN = re.compile(r"%?\d+(?:[.,]\d+)*")
TEXT_FLAGS = fitz.TEXTFLAGS_TEXT | fitz.TEXT_INHIBIT_SPACES


def source_words() -> set[str]:
    words = set()
    for path in SOURCES:
        words |= {checks.tr_lower(w) for w in LETTERS.findall(path.read_text(encoding="utf-8"))}
    return words


def unknown_words(text: str, known: set[str]) -> set[str]:
    """Words printed in a PDF that no source file contains: a typo, a split word or a garbled glyph."""
    return {w for w in LETTERS.findall(text) if checks.tr_lower(w) not in known}


def lines_ending_in_a_hyphen(text: str) -> list[str]:
    return [line for line in text.splitlines() if re.search(r"\w-$", line.strip())]


def pdf_text(pdf) -> str:
    """The text as printed. Without TEXT_INHIBIT_SPACES PyMuPDF guesses a space wherever letter spacing widens a gap."""
    with fitz.open(pdf) as doc:
        return "".join(page.get_text(flags=TEXT_FLAGS) for page in doc)


def numbers_split_from_their_word(doc) -> list[str]:
    """A number that ends a line while its text goes on in the line below: "59,99" over "$ (App Store)".
    Two spans side by side in one row (a footer) are not a wrap, so the next word must start below the number."""
    found = []
    for page in doc:
        words = page.get_text("words", flags=TEXT_FLAGS)  # x0, y0, x1, y1, text, block, line, word
        for a, b in zip(words, words[1:]):
            if a[5] == b[5] and b[1] >= a[3] - 1 and NUMBER_TOKEN.fullmatch(a[4]):
                found.append(f"{a[4]} / {b[4]}")
    return found


def size(path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def probe(path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


class Images(unittest.TestCase):
    def test_three_square_images_1080(self):
        for spec in build.load("media.json")["images"]:
            with self.subTest(image=spec["id"]):
                self.assertEqual(size(OUT / "icerik-seti" / f"{spec['id']}.png"), (1080, 1080))

    def test_one_vertical_frame_per_scene(self):
        scenes = build.load("media.json")["video"]["scenes"]
        frames = sorted((OUT / "icerik-seti" / "video-kareleri").glob("sahne-*.png"))
        self.assertEqual(len(frames), len(scenes))
        for frame in frames:
            self.assertEqual(size(frame), (1080, 1920))

    def test_screenshots_of_the_content_set_at_twice_the_slide_size(self):
        shots = sorted(path.stem for path in (OUT / "ekran-goruntuleri").glob("*.png"))
        self.assertEqual(shots, docs.screenshot_names())
        self.assertGreaterEqual(len(shots), 9)
        for name in shots:
            with self.subTest(shot=name):
                self.assertEqual(size(OUT / "ekran-goruntuleri" / f"{name}.png"),
                                 (1280 * docs.SHOT_SCALE, 720 * docs.SHOT_SCALE))

    def test_every_slide_has_a_png_copy_in_deck_order(self):
        slides = sorted((OUT / "sunum-slaytlar").glob("*.png"))
        with fitz.open(OUT / "sunum.pdf") as deck:
            self.assertEqual(len(slides), deck.page_count)
        self.assertEqual([int(path.stem[:2]) for path in slides], list(range(1, len(slides) + 1)))
        keys = {path.stem[3:] for path in slides}
        self.assertLessEqual(set(docs.screenshot_keys()), keys)
        for path in slides:
            with self.subTest(slide=path.name):
                self.assertEqual(size(path), (1280 * docs.SHOT_SCALE, 720 * docs.SHOT_SCALE))


def ffmpeg_report(path, *filters) -> str:
    """What ffmpeg's analysis filters print for a file (silence, frozen frames, loudness)."""
    return subprocess.run(["ffmpeg", "-v", "info", "-i", str(path), *filters, "-f", "null", "-"], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", check=True, timeout=300).stderr


def loudness(path) -> float:
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", ffmpeg_report(path, "-af", "ebur128"))[-1])


class VideoAndVoice(unittest.TestCase):
    def test_video_is_vertical_with_sound_and_within_the_brief_s_length(self):
        spec = build.load("media.json")["video"]
        info = probe(OUT / "icerik-seti" / f"{spec['id']}.mp4")
        video = [s for s in info["streams"] if s["codec_type"] == "video"]
        audio = [s for s in info["streams"] if s["codec_type"] == "audio"]
        self.assertEqual((video[0]["width"], video[0]["height"]), (spec["width"], spec["height"]))
        self.assertEqual(len(audio), 1)
        self.assertTrue(spec["min_seconds"] <= float(info["format"]["duration"]) <= spec["max_seconds"])

    def test_the_picture_never_stands_still_for_a_second(self):
        report = ffmpeg_report(OUT / "icerik-seti" / "tanitim-videosu.mp4", "-vf", "freezedetect=n=-60dB:d=1")
        self.assertNotIn("freeze_start", report)

    def test_no_pause_of_more_than_six_tenths_between_sentences(self):
        path = OUT / "icerik-seti" / "tanitim-videosu.mp4"
        report = ffmpeg_report(path, "-af", "silencedetect=noise=-40dB:d=0.6")
        starts = [float(s) for s in re.findall(r"silence_start: ([\d.]+)", report)]
        length = float(probe(path)["format"]["duration"])
        # The first sentence starts after a short lead and the last one ends before the closing frame.
        self.assertEqual([s for s in starts if 0.5 < s < length - 1.0], [])

    def test_sound_is_as_loud_as_the_platforms_play(self):
        for name in ("tanitim-videosu.mp4", "seslendirme.mp3", "hikaye-pazar.mp4"):
            with self.subTest(file=name):
                self.assertTrue(-15.5 <= loudness(OUT / "icerik-seti" / name) <= -12.5)

    def test_voiceover_pauses_stay_shorter_than_the_old_one_second(self):
        report = ffmpeg_report(OUT / "icerik-seti" / "seslendirme.mp3", "-af", "silencedetect=noise=-40dB:d=0.9")
        self.assertNotIn("silence_start", report)

    def test_voiceover_is_an_audio_file_within_its_length(self):
        spec = build.load("media.json")["voiceover"]
        info = probe(OUT / "icerik-seti" / f"{spec['id']}.mp3")
        self.assertEqual([s["codec_type"] for s in info["streams"]], ["audio"])
        self.assertTrue(spec["min_seconds"] <= float(info["format"]["duration"]) <= spec["max_seconds"])


class Stories(unittest.TestCase):
    def test_the_poll_is_a_vertical_card_and_the_audio_story_a_vertical_video_of_the_voiceover(self):
        self.assertEqual(size(OUT / "icerik-seti" / "hikaye-anket.png"), (1080, 1920))
        info = probe(OUT / "icerik-seti" / "hikaye-pazar.mp4")
        video = [s for s in info["streams"] if s["codec_type"] == "video"]
        self.assertEqual((video[0]["width"], video[0]["height"]), (1080, 1920))
        self.assertEqual([s["codec_type"] for s in info["streams"]].count("audio"), 1)
        voice = float(probe(OUT / "icerik-seti" / "seslendirme.mp3")["format"]["duration"])
        self.assertAlmostEqual(float(info["format"]["duration"]), voice, delta=0.3)


class Calendar(unittest.TestCase):
    def test_header_rows_and_dates_match_the_calendar_file(self):
        sheet = load_workbook(OUT / "icerik-takvimi.xlsx").active
        rows = list(sheet.iter_rows(values_only=True))
        self.assertEqual(list(rows[0]), [title for title, _ in build.CALENDAR_COLUMNS])
        calendar = build.load("calendar.json")
        self.assertEqual(len(rows) - 1, len(calendar))
        self.assertEqual([r[0].date() for r in rows[1:]], [date.fromisoformat(c["date"]) for c in calendar])
        topic = list(rows[0]).index("Konu")
        self.assertEqual([r[topic] for r in rows[1:]], [c["topic"] for c in calendar])

    def test_prints_on_sideways_a4_one_page_wide(self):
        sheet = load_workbook(OUT / "icerik-takvimi.xlsx").active
        self.assertEqual(sheet.page_setup.orientation, sheet.ORIENTATION_LANDSCAPE)
        self.assertEqual(int(sheet.page_setup.fitToWidth), 1)
        self.assertTrue(sheet.sheet_properties.pageSetUpPr.fitToPage)


class Documents(unittest.TestCase):
    known = source_words()
    pdfs = sorted(OUT.rglob("*.pdf"))

    def test_page_counts_follow_the_brief(self):
        pages = {pdf.name: fitz.open(pdf).page_count for pdf in self.pdfs}
        self.assertIn(pages["marka-stratejisi.pdf"], (1, 2))
        self.assertEqual(pages["marka-sesi-rehberi.pdf"], 1)
        self.assertEqual(pages["kontrol-listesi.pdf"], 2)

    def test_no_blank_page_and_slides_are_16_by_9(self):
        self.assertEqual(len(self.pdfs), 5)
        for pdf in self.pdfs:
            for number, page in enumerate(fitz.open(pdf), 1):
                with self.subTest(pdf=pdf.name, page=number):
                    self.assertTrue(page.get_text().strip())
        for page in fitz.open(OUT / "sunum.pdf"):
            self.assertAlmostEqual(page.rect.width / page.rect.height, 16 / 9, places=3)

    def test_the_deck_links_open_the_video_the_sound_and_the_source(self):
        media = build.load("media.json")
        video = f"{docs.REPO_URL}/blob/main/deliverables/icerik-seti/{media['video']['id']}.mp4"
        voice = f"{docs.REPO_URL}/blob/main/deliverables/icerik-seti/{media['voiceover']['id']}.mp3"
        with fitz.open(OUT / "sunum.pdf") as deck:
            links = {number: {link["uri"] for link in page.get_links() if "uri" in link}
                     for number, page in enumerate(deck, 1)}
            media_page = next(number for number, page in enumerate(deck, 1) if "VİDEO VE SES" in page.get_text())
            last = deck.page_count
        self.assertLessEqual({video, voice}, links[media_page])
        self.assertLessEqual({video, voice, docs.REPO_URL, build.BRAND["app_url"]}, links[last])
        blob = f"{docs.REPO_URL}/blob/main/"
        files = {uri.removeprefix(blob) for uris in links.values() for uri in uris if uri.startswith(blob)}
        self.assertGreaterEqual(len(files), 3)
        for file in files:
            with self.subTest(file=file):
                self.assertTrue((ROOT / file).is_file())

    def test_every_printed_word_comes_from_a_source_file(self):
        checked = 0
        for pdf in self.pdfs:
            text = pdf_text(pdf)
            checked += len(LETTERS.findall(text))
            with self.subTest(pdf=pdf.name):
                self.assertEqual(unknown_words(text, self.known), set())
        self.assertGreater(checked, 3000)

    def test_no_line_ends_in_a_split_word_and_no_long_dash(self):
        for pdf in self.pdfs:
            text = pdf_text(pdf)
            with self.subTest(pdf=pdf.name):
                self.assertEqual(lines_ending_in_a_hyphen(text), [])
                self.assertFalse(any(dash in text for dash in checks.LONG_DASHES))

    def test_no_number_is_printed_apart_from_the_word_after_it(self):
        numbers = 0
        for pdf in self.pdfs:
            with fitz.open(pdf) as doc, self.subTest(pdf=pdf.name):
                numbers += sum(1 for page in doc for w in page.get_text("words", flags=TEXT_FLAGS)
                               if NUMBER_TOKEN.fullmatch(w[4]))
                self.assertEqual(numbers_split_from_their_word(doc), [])
        self.assertGreater(numbers, 100)

    def test_the_published_blog_page_carries_its_share_tags_and_pictures(self):
        page = (OUT / "icerik-seti" / "blog.html").read_text(encoding="utf-8")
        meta, _ = checks.read_front_matter(ROOT / "content" / "blog.md")
        self.assertIn(f'<meta property="og:title" content="{meta["title"]}">', page)
        schema = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page).group(1))
        self.assertEqual((schema["@type"], schema["headline"]), ("Article", meta["title"]))
        pictures = re.findall(r'<img alt="([^"]+)" src="([^"]+)"', page)
        self.assertEqual(len(pictures), 2)
        for alt, src in pictures:
            self.assertTrue((OUT / "icerik-seti" / src).is_file(), src)

    def test_the_published_blog_page_has_no_build_script(self):
        page = (OUT / "icerik-seti" / "blog.html").read_text(encoding="utf-8")
        self.assertNotIn("fit-report", page)
        self.assertIn('<html lang="tr">', page)


class Detectors(unittest.TestCase):
    """The word and line detectors fire on broken text, so their silence above means something."""

    def test_unknown_word_detector_fires_on_a_typo(self):
        self.assertEqual(unknown_words("Geçti Gecti", {"geçti"}), {"Gecti"})

    def test_hyphen_detector_fires_on_a_split_address(self):
        self.assertEqual(lines_ending_in_a_hyphen("axelxoket.github.io/expense-tracker-\ndashboard"),
                         ["axelxoket.github.io/expense-tracker-"])
        self.assertEqual(lines_ending_in_a_hyphen("a - b\n20-35 yaş"), [])

    def test_split_number_detector_fires_on_a_wrap_and_not_on_a_row(self):
        def found(text, *more):
            with fitz.open() as doc:
                page = doc.new_page()
                page.insert_text((72, 72), text, fontsize=11)
                for x, line in more:
                    page.insert_text((x, 72), line, fontsize=11)
                return numbers_split_from_their_word(doc)
        self.assertEqual(found("Premium 59,99\n$ (App Store)"), ["59,99 / $"])
        self.assertEqual(found("Premium 59,99 $\n(App Store)"), [])
        self.assertEqual(found("Kasım 2026", (300, "axelxoket.github.io")), [])


if __name__ == "__main__":
    unittest.main()
