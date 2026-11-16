"""Text helpers and the checklist rows: what reaches the page is escaped, kept whole and computed, not typed."""
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import fitz

from tests import ROOT  # noqa: F401

import build
import checks
import docs


def kept(text: str) -> str:
    return build.keep_together(build.e(text))


class KeepTogether(unittest.TestCase):
    def test_a_hyphenated_word_is_wrapped_whole(self):
        self.assertEqual(kept("e-posta adresi"), '<span class="nw">e-posta</span> adresi')
        self.assertEqual(kept("tr-TR-EmelNeural"), '<span class="nw">tr-TR-EmelNeural</span>')

    def test_a_number_is_bound_to_the_word_after_it(self):
        self.assertEqual(kept("6 saniye"), "6&nbsp;saniye")
        self.assertEqual(kept("1.250,50 TL ve %100,0 eder"), "1.250,50&nbsp;TL ve %100,0&nbsp;eder")

    def test_a_number_is_bound_to_the_unit_sign_after_it(self):
        self.assertEqual(kept("Premium 59,99 $ (App Store) ve 10 %"), "Premium 59,99&nbsp;$ (App Store) ve 10&nbsp;%")

    def test_a_range_is_kept_whole_with_its_unit(self):
        self.assertEqual(kept("20-35 yaş"), '<span class="nw">20-35&nbsp;yaş</span>')

    def test_ordinals_and_lone_hyphens_stay_as_they_are(self):
        self.assertEqual(kept("2. sayfa - kısa"), "2. sayfa - kısa")

    def test_a_particle_stays_with_the_word_before_it(self):
        self.assertEqual(kept("Ya da siz de bakın; var mı? Biliyorum ki"),
                         "Ya&nbsp;da siz&nbsp;de bakın; var&nbsp;mı? Biliyorum&nbsp;ki")

    def test_words_that_only_start_like_a_particle_stay_apart(self):
        self.assertEqual(kept("bir dakika mutlu kimse deniz"), "bir dakika mutlu kimse deniz")

    def test_markup_is_escaped_and_the_rules_do_not_touch_entities(self):
        self.assertEqual(kept('<b>"x"</b> & 6'), "&lt;b&gt;&quot;x&quot;&lt;/b&gt; &amp; 6")

    def test_a_page_applies_the_rules_to_its_body_but_never_inside_a_tag(self):
        page = build.page("t", "", '<p class="a-b" title="6 saniye">6 saniye ya da e-posta</p>')
        self.assertIn('<p class="a-b" title="6 saniye">6&nbsp;saniye ya&nbsp;da <span class="nw">e-posta</span></p>', page)

    def test_finished_html_changes_only_between_tags(self):
        html = '<a href="https://a.io/expense-tracker-dashboard">expense-tracker</a> 6 saniye'
        self.assertEqual(build.keep_together_html(html),
                         '<a href="https://a.io/expense-tracker-dashboard"><span class="nw">expense-tracker</span></a> 6&nbsp;saniye')


class Formats(unittest.TestCase):
    def test_seconds_use_a_decimal_comma(self):
        self.assertEqual(docs.seconds(17.53), "17,5")

    def test_dates_read_the_turkish_way(self):
        self.assertEqual(build.tr_date("2026-11-23"), "23 Kasım 2026")
        self.assertEqual(build.tr_day("2026-11-29"), "Pazar")
        self.assertEqual(docs.short_date("2026-11-23"), "23 Kasım, Pazartesi")

    def test_channel_limits_are_read_from_the_check_constants(self):
        x = docs.channel_limit("X")
        self.assertIn(str(checks.CHANNEL_LIMITS["X"]), x)
        self.assertIn(str(checks.HASHTAG_LIMITS["X"]), x)
        low, high = checks.BLOG_WORDS
        self.assertIn(f"{low}-{high}", docs.channel_limit("Blog"))
        media = build.load("media.json")
        for channel, spec in (("Video", media["video"]), ("Seslendirme", media["voiceover"])):
            self.assertEqual(docs.channel_limit(channel), f"{spec['min_seconds']}-{spec['max_seconds']} saniye")
        with self.assertRaises(KeyError):
            docs.channel_limit("Podcast")


class MediaLength(unittest.TestCase):
    spec = {"min_seconds": 15, "max_seconds": 20}

    def test_both_limits_pass_and_anything_past_them_is_refused(self):
        self.assertIsNone(build.length_problem(15.0, self.spec, "video"))
        self.assertIsNone(build.length_problem(20.0, self.spec, "video"))
        self.assertEqual(build.length_problem(14.9, self.spec, "video"), "video is 14.9 s, 15 to 20 s wanted")
        self.assertEqual(build.length_problem(20.1, self.spec, "voiceover"), "voiceover is 20.1 s, 15 to 20 s wanted")


class VideoTiming(unittest.TestCase):
    def test_easing_runs_from_zero_to_one_and_stops_at_both_ends(self):
        self.assertEqual([build.smooth(x) for x in (-1, 0, 0.5, 1, 2)], [0.0, 0.0, 0.5, 1.0, 1.0])

    def test_each_form_step_shows_for_its_seconds_and_the_last_one_stays(self):
        steps = [{"seconds": 0.4}, {"seconds": 0.25}, {"seconds": 0.12}]
        self.assertEqual([build.step_at(t, steps) for t in (0, 0.39, 0.4, 0.64, 0.65, 0.76, 0.77, 9)], [0, 0, 1, 1, 2, 2, 2, 2])

    def test_the_pan_waits_at_both_ends_and_only_moves_down(self):
        top, bottom, window, length = 100, 2000, 860, 3.0
        offsets = [build.pan_offset(n / 30, length, top, bottom, window) for n in range(91)]
        self.assertEqual(offsets[0], top)
        self.assertEqual(build.pan_offset(build.EDGE_TIME, length, top, bottom, window), top)
        self.assertEqual(build.pan_offset(length - build.EDGE_TIME, length, top, bottom, window), bottom - window)
        self.assertEqual(offsets[-1], bottom - window)
        self.assertEqual(offsets, sorted(offsets))
        self.assertTrue(top < offsets[45] < bottom - window)

    def test_a_scene_lasts_its_sentence_or_its_motion_whichever_is_longer(self):
        spec = {"min_seconds": 2, "max_seconds": 20}
        pause = build.SPEECH_LEAD + build.SPEECH_TAIL
        self.assertEqual(build.scene_lengths([2.0, 1.0], [0.0, 3.0], spec), [round(2.0 + pause, 2), 3.0])

    def test_only_a_video_under_the_minimum_spreads_the_missing_time(self):
        spec = {"min_seconds": 15, "max_seconds": 20}
        lengths = build.scene_lengths([1.0] * 5, [0.0] * 5, spec)
        self.assertAlmostEqual(sum(lengths), 15.5, delta=0.02)
        self.assertEqual(len(set(lengths)), 1)


def tone(seconds):
    """A stand-in for edge-tts: a beep of the given length instead of the spoken sentence."""
    def write(sentence, voice, rate, target):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=f=440:d={seconds}", str(target)],
                       check=True, timeout=60)
    return write


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is not installed")
class Speech(unittest.TestCase):
    """Each sentence is read on its own and the sentences are joined with a short gap."""

    def speak(self, text, **gap):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(build, "tts", tone(1)):
            return build.duration(build.speak(text, "v", "+0%", pathlib.Path(tmp), "s", **gap))

    def test_three_sentences_take_three_readings_and_two_gaps(self):
        seconds = self.speak("Ay bitti. Para nereye gitti? Paneli açın!")
        self.assertAlmostEqual(seconds, 3 + 2 * build.SENTENCE_GAP, delta=0.15)

    def test_a_longer_gap_is_used_when_given(self):
        seconds = self.speak("Ay bitti. Para nereye gitti? Paneli açın!", gap=build.VOICEOVER_GAP)
        self.assertAlmostEqual(seconds, 3 + 2 * build.VOICEOVER_GAP, delta=0.15)

    def test_one_sentence_has_no_gap(self):
        seconds = self.speak("Ayın resmi tek ekranda: bütçe ve kategoriler.")
        self.assertAlmostEqual(seconds, 1.0, delta=0.15)


class StoryBar(unittest.TestCase):
    card = build.Image.new("RGB", (1080, 1920), "white")
    green = build.ImageDraw.ImageColor.getrgb(build.COLOURS["Zümrüt"])

    def pixel(self, share, at):
        bar = build.STORY_BAR
        frame = build.progress_frame(self.card, share)
        return frame.getpixel((bar["left"] + round(bar["width"] * at), bar["top"] + bar["height"] // 2))

    def test_the_bar_fills_with_the_share_of_the_voice_played(self):
        self.assertNotEqual(self.pixel(0, 0.02), self.green)
        self.assertEqual(self.pixel(0.5, 0.25), self.green)
        self.assertNotEqual(self.pixel(0.5, 0.75), self.green)
        self.assertEqual(self.pixel(1, 0.98), self.green)

    def test_the_card_itself_is_not_changed(self):
        build.progress_frame(self.card, 1)
        self.assertEqual(self.card.getpixel((540, 1436)), (255, 255, 255))


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is not installed")
class VoiceoverGate(unittest.TestCase):
    """build_voice keeps the old file unless the new voice is within the limits in media.json."""

    def build(self, folder, seconds):
        def spoken(text, voice, rate, workdir, name, gap):
            target = workdir / f"{name}.wav"
            tone(seconds)(text, voice, rate, target)
            return target
        with mock.patch.object(build, "SET", folder), mock.patch.object(build, "speak", spoken):
            return build.build_voice()

    def test_the_script_is_read_sentence_by_sentence_with_the_voiceover_gap(self):
        spec = build.load("media.json")["voiceover"]
        read = []
        reading = tone(2.5)

        def fake_tts(sentence, voice, rate, target):
            read.append(sentence)
            reading(sentence, voice, rate, target)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(build, "SET", pathlib.Path(tmp)), \
                mock.patch.object(build, "tts", fake_tts):
            seconds = build.duration(build.build_voice())
        self.assertGreater(len(read), 3)
        self.assertEqual(" ".join(read), spec["script"])
        self.assertAlmostEqual(seconds, len(read) * 2.5 + (len(read) - 1) * build.VOICEOVER_GAP, delta=0.3)

    def test_a_voice_past_the_limit_is_refused_and_the_old_file_stays(self):
        spec = build.load("media.json")["voiceover"]
        middle = (spec["min_seconds"] + spec["max_seconds"]) / 2
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            old = folder / f"{spec['id']}.mp3"
            old.write_bytes(b"old")
            with self.assertRaises(SystemExit) as refused:
                self.build(folder, spec["max_seconds"] + 1)
            self.assertTrue(str(refused.exception).startswith("voiceover is"))
            self.assertEqual(old.read_bytes(), b"old")
            self.assertEqual(self.build(folder, middle), old)
            self.assertAlmostEqual(build.duration(old), middle, delta=0.2)


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is not installed")
class SilenceTrim(unittest.TestCase):
    def test_silence_before_and_after_a_tone_is_cut(self):
        """A 1 s tone between 0.5 s and 1.5 s of silence comes back as about 1 s of sound."""
        with tempfile.TemporaryDirectory() as tmp:
            source, target = pathlib.Path(tmp) / "in.wav", pathlib.Path(tmp) / "out.wav"
            graph = ("anullsrc=r=48000:cl=mono:d=0.5[a];sine=f=440:r=48000:d=1[b];anullsrc=r=48000:cl=mono:d=1.5[c];"
                     "[a][b][c]concat=n=3:v=0:a=1")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-filter_complex", graph, str(source)], check=True, timeout=60)
            self.assertAlmostEqual(build.duration(source), 3.0, delta=0.05)
            build.trim_silence(source, target)
            self.assertAlmostEqual(build.duration(target), 1.0, delta=0.1)


class ChecklistRows(unittest.TestCase):
    def rows(self, problems):
        with mock.patch.object(build, "content_problems", return_value=problems):
            return {row["piece"]: row for row in docs.checklist_rows()}

    def test_clean_content_shows_passed_everywhere(self):
        rows = self.rows({})
        self.assertTrue(all(r["voice"] == docs.PASSED and r["numbers"] == docs.PASSED for r in rows.values()))

    def test_number_and_voice_problems_land_in_their_own_columns(self):
        rows = self.rows({"blog": [f"{checks.NUMBER_PROBLEM} 7", "long sentence (x)"]})
        self.assertEqual(rows["Blog yazısı"]["numbers"], f"{checks.NUMBER_PROBLEM} 7")
        self.assertEqual(rows["Blog yazısı"]["voice"], "long sentence (x)")
        self.assertEqual(rows["Tanıtım videosu"]["voice"], docs.PASSED)

    def test_a_problem_on_any_calendar_day_shows_on_the_calendar_row(self):
        day = build.load("calendar.json")[3]["date"]
        rows = self.rows({f"calendar {day}": ["avoided word israf"]})
        self.assertEqual(rows["Takvim metinleri (7 gün)"]["voice"], "avoided word israf")

    def test_one_row_per_published_piece(self):
        media = build.load("media.json")
        expected = 1 + len(build.load("social.json")) + len(media["images"]) + len(media["stories"]) + 3
        self.assertEqual(len(self.rows({})), expected)

    def test_the_claims_column_lists_what_each_piece_says_about_the_product(self):
        rows = self.rows({})
        self.assertIn("kaynak-acik", rows["LinkedIn gönderisi"]["claims"])
        self.assertIn("geri-al-6-saniye", rows["Blog yazısı"]["claims"])
        self.assertEqual(rows["X gönderisi"]["claims"], ["butce-uyarisi-80"])
        self.assertEqual(rows["Hikâye: anket"]["claims"], [])

    def test_items_joined_into_one_sentence_start_in_lower_case(self):
        self.assertEqual(docs.joined(["Ayın resmi", "Bütçe", "İzmir"]), "Ayın resmi; bütçe; izmir")


class DeckFiles(unittest.TestCase):
    def test_a_link_opens_the_file_on_the_pages_site(self):
        anchor = docs.link(build.SET / "tanitim-videosu.mp4")
        self.assertEqual(anchor, f'<a href="{docs.PAGES_URL}/deliverables/icerik-seti/tanitim-videosu.mp4">'
                                 'tanitim-videosu.mp4</a>')

    def pdf(self, folder, pages):
        path = folder / "deck.pdf"
        with fitz.open() as doc:
            for number in range(pages):
                doc.new_page(width=960, height=540).insert_text((72, 72), f"Slayt {number + 1}")
            doc.save(path)
        return path

    def test_every_page_becomes_a_numbered_png_at_twice_the_slide_size(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(docs, "OUT", pathlib.Path(tmp)):
            folder = pathlib.Path(tmp) / "sunum-slaytlar"
            folder.mkdir()
            (folder / "09-eski.png").write_bytes(b"old")
            saved = docs.slide_pngs(self.pdf(pathlib.Path(tmp), 2), ["kapak", "teslim"])
            self.assertEqual(sorted(p.name for p in folder.iterdir()), ["01-kapak.png", "02-teslim.png"])
            self.assertEqual(saved, [folder / "01-kapak.png", folder / "02-teslim.png"])
            for path in saved:
                with build.Image.open(path) as image:
                    self.assertEqual(image.size, (1280 * docs.SHOT_SCALE, 720 * docs.SHOT_SCALE))

    def test_a_page_without_a_name_stops_the_export(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(docs, "OUT", pathlib.Path(tmp)):
            with self.assertRaises(ValueError):
                docs.slide_pngs(self.pdf(pathlib.Path(tmp), 2), ["kapak"])


class PollCard(unittest.TestCase):
    def test_the_card_leaves_the_options_to_instagram_s_sticker(self):
        poll = next(s for s in build.load("media.json")["stories"] if s["kind"] == "poll")
        card = build.story_html(poll)
        self.assertIn(build.e(poll["question"]), card)
        self.assertIn('class="sticker"', card)
        self.assertGreaterEqual(len(poll["options"]), 2)
        for option in poll["options"]:
            with self.subTest(option=option):
                self.assertNotIn(build.e(option), card)


if __name__ == "__main__":
    unittest.main()
