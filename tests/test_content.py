"""The real content: it passes every check and holds together (calendar, pillars, posts, prompts, sources)."""
import json
import re
import unittest
from datetime import date, timedelta
from unittest import mock

from tests import ROOT

import build
import checks
from checks import BRAND

COMPETITORS = json.loads((ROOT / "brand" / "competitors.json").read_text(encoding="utf-8"))
PILLAR_IDS = {p["id"] for p in BRAND["pillars"]}
WEB_REPO = ROOT.parent / "expense-tracker-dashboard"


class ChecksPass(unittest.TestCase):
    def test_every_published_text_passes_the_checks(self):
        self.assertEqual(build.content_problems(), {})

    def test_the_gate_covers_every_piece(self):
        """content_problems must look at each published piece; a piece left out would never be checked."""
        media = build.load("media.json")
        expected = {"blog", "video", "voiceover", *(p["id"] for p in build.load("social.json")),
                    *(spec["id"] for spec in media["images"] + media["stories"]),
                    *(f"calendar {r['date']}" for r in build.load("calendar.json"))}
        seen = set()
        original = checks.voice_problems

        def spy(text):
            seen.add(text)
            return original(text)
        checks.voice_problems = spy
        try:
            build.content_problems()
        finally:
            checks.voice_problems = original
        # One checked text per piece: posts and the blog reach voice_problems through their own checks.
        self.assertEqual(len(seen), len(expected))

    def test_a_scene_whose_voice_differs_from_its_screen_is_refused(self):
        real = build.load

        def load(name):
            data = real(name)
            if name == "media.json":
                data["video"]["scenes"][1]["narration"] = "Hesap yok."
            return data
        with mock.patch.object(build, "load", side_effect=load):
            found = build.content_problems()
        self.assertEqual(found, {"video": ["scene 2: the screen and the voice say different things"]})


class Calendar(unittest.TestCase):
    rows = build.load("calendar.json")

    @staticmethod
    def reported(metric_text: str) -> set[str]:
        """The numbers a channel reports: each part between semicolons, and each side of its "ve", without notes in brackets."""
        parts = set()
        for part in re.sub(r"\s*\(.*?\)", "", checks.tr_lower(metric_text)).split(";"):
            part = part.strip()
            parts |= {part, *(side.strip() for side in part.split(" ve "))}
        return parts

    def test_every_post_is_measured_by_a_number_its_channel_reports(self):
        by_channel = {m["channel"].split()[0]: self.reported(m["metric"]) for m in BRAND["measures"]["channels"]}
        for row in self.rows:
            with self.subTest(day=row["date"]):
                self.assertIn(checks.tr_lower(row["metric"]), by_channel[row["channel"].split()[0]])
        self.assertTrue(BRAND["measures"]["target"].strip())

    def test_the_reported_numbers_are_whole_parts_not_single_words(self):
        parts = self.reported("Kaydetme ve paylaşım; hikâye anketinde yanıt sayısı (Instagram)")
        self.assertEqual(parts, {"kaydetme ve paylaşım", "kaydetme", "paylaşım", "hikâye anketinde yanıt sayısı"})
        self.assertNotIn("ve", parts)

    def test_seven_consecutive_days_from_a_monday(self):
        days = [date.fromisoformat(r["date"]) for r in self.rows]
        self.assertEqual(len(days), 7)
        self.assertEqual(days[0].weekday(), 0)
        self.assertEqual(days, [days[0] + timedelta(days=i) for i in range(7)])

    def test_every_row_names_a_known_pillar_and_every_pillar_is_used(self):
        used = {r["pillar"] for r in self.rows}
        self.assertLessEqual(used, PILLAR_IDS)
        self.assertEqual(used, PILLAR_IDS)

    @staticmethod
    def produced():
        media = build.load("media.json")
        return {"blog", media["video"]["id"], *(p["id"] for p in build.load("social.json")), *(s["id"] for s in media["stories"])}

    def test_every_piece_exists_and_text_only_rows_say_so(self):
        pieces = self.produced()
        for row in self.rows:
            with self.subTest(date=row["date"]):
                if row["piece"]:
                    self.assertIn(row["piece"], pieces)
                else:
                    self.assertEqual(row["status"], "Metin hazır")

    def test_every_produced_piece_is_on_the_calendar(self):
        self.assertEqual({r["piece"] for r in self.rows if r["piece"]}, self.produced())

    def test_every_row_has_a_posting_time(self):
        for row in self.rows:
            with self.subTest(date=row["date"]):
                self.assertRegex(row["time"], r"^([01]\d|2[0-3]):[0-5]\d$")

    def test_calls_to_action_come_from_the_brand(self):
        allowed = {BRAND["cta"]["primary"], BRAND["cta"]["sample"], "Ankete katılın"}
        for row in self.rows:
            self.assertIn(row["cta"], allowed)


class Posts(unittest.TestCase):
    posts = build.load("social.json")

    def test_three_posts_on_three_channels(self):
        self.assertEqual(len(self.posts), 3)
        self.assertEqual(len({p["channel"] for p in self.posts}), 3)

    def test_every_post_has_a_full_rtf_prompt(self):
        for post in self.posts:
            with self.subTest(post=post["id"]):
                self.assertEqual(set(post["prompt"]), {"role", "task", "format"})
                self.assertTrue(all(value.strip() for value in post["prompt"].values()))

    def test_every_post_points_at_an_image_and_a_pillar(self):
        images = {img["id"] for img in build.load("media.json")["images"]}
        for post in self.posts:
            self.assertIn(post["image"], images)
            self.assertIn(post["pillar"], PILLAR_IDS)

    def test_every_post_prompt_allows_the_hashtags_the_check_allows(self):
        for post in self.posts:
            with self.subTest(post=post["id"]):
                stated = re.search(r"en çok (\d+) etiket", post["prompt"]["format"])
                self.assertIsNotNone(stated)
                self.assertEqual(int(stated.group(1)), checks.HASHTAG_LIMITS[post["channel"]])

    def test_the_blog_prompt_has_every_co_star_part(self):
        prompt = build.load("prompts.json")["blog"]
        for part in ("context", "objective", "style", "tone", "audience", "response"):
            self.assertTrue(prompt[part].strip(), part)


class Media(unittest.TestCase):
    media = build.load("media.json")

    def test_video_limits_are_the_brief_s_15_to_20_seconds(self):
        self.assertEqual((self.media["video"]["min_seconds"], self.media["video"]["max_seconds"]), (15, 20))

    def test_every_image_and_story_has_alt_text(self):
        for spec in self.media["images"] + self.media["stories"]:
            with self.subTest(piece=spec["id"]):
                self.assertTrue(spec["alt"].endswith("."))
                self.assertGreater(len(checks.words(spec["alt"])), 5)

    def test_the_captured_panel_frames_hold_together(self):
        timeline = json.loads((ROOT / "assets" / "video" / "timeline.json").read_text(encoding="utf-8"))
        folder = ROOT / "assets" / "video"
        self.assertGreaterEqual(len(timeline["form"]), 5)
        self.assertEqual(sum(step["still"] for step in timeline["form"]), 1)
        for step in timeline["form"]:
            self.assertTrue((folder / step["file"]).is_file(), step["file"])
        pan = timeline["pan"]
        from PIL import Image
        with Image.open(folder / pan["file"]) as page:
            self.assertTrue(0 <= pan["top"] < pan["bottom"] - build.CARD["height"] <= page.height - build.CARD["height"])

    def test_three_images_each_with_an_rtf_prompt(self):
        self.assertEqual(len(self.media["images"]), 3)
        for img in self.media["images"]:
            self.assertEqual(set(img["prompt"]), {"role", "task", "format"})

    def test_screen_text_and_narration_say_the_same_words(self):
        scenes = self.media["video"]["scenes"]
        self.assertEqual(len(scenes), 5)
        for scene in scenes:
            with self.subTest(scene=scene["visual"]):
                self.assertTrue(checks.same_words(scene["text"], scene["narration"]))

    def test_voiceover_limits_hold_the_length_the_prompt_asks_for(self):
        voiceover = self.media["voiceover"]
        asked = int(re.search(r"(\d+) saniye", voiceover["prompt"]["format"]).group(1))
        self.assertLessEqual(voiceover["min_seconds"], asked)
        self.assertGreaterEqual(voiceover["max_seconds"], asked)


class Brand(unittest.TestCase):
    def test_three_or_four_pillars(self):
        self.assertIn(len(BRAND["pillars"]), (3, 4))

    def test_every_text_colour_pair_meets_wcag_aa(self):
        for pair in BRAND["text_pairs"]:
            with self.subTest(pair=pair):
                self.assertGreaterEqual(checks.contrast(pair["text"], pair["background"]), 4.5)

    def test_every_voice_channel_rule_covers_a_measured_channel(self):
        named = {c["channel"] for c in BRAND["voice"]["channels"]}
        self.assertLessEqual(set(checks.CHANNEL_LIMITS), named)
        self.assertIn("Blog", named)

    def test_every_number_has_a_meaning_or_a_claim_and_phrases_that_start_with_it(self):
        for item in BRAND["facts"]:
            self.assertTrue(item["claim"] and item["evidence"] and item["line"], item)
        for item in BRAND["own_numbers"]:
            self.assertTrue(item["meaning"], item)
        for item in BRAND["facts"] + BRAND["own_numbers"]:
            with self.subTest(value=item["value"]):
                self.assertTrue(item["forms"])
                for form in item["forms"]:
                    self.assertIn(item["value"], form.partition(" ")[0])

    def test_every_fact_and_claim_is_made_by_some_published_piece(self):
        texts = build.published_texts().values()
        made = {claim for text in texts for claim in checks.claims_in(text)}
        self.assertEqual(made, {item["id"] for item in BRAND["facts"] + BRAND["product_claims"]})

    @unittest.skipUnless(WEB_REPO.is_dir(), "the panel's repository is not next to this one")
    def test_every_cited_evidence_file_exists_and_holds_the_cited_line(self):
        cited = BRAND["facts"] + BRAND["product_claims"]
        self.assertGreaterEqual(len(cited), 14)
        for item in cited:
            with self.subTest(claim=item["claim"]):
                source = ROOT.parent / item["evidence"]
                self.assertTrue(source.is_file(), item["evidence"])
                self.assertIn(item["line"], source.read_text(encoding="utf-8"))


class Competitors(unittest.TestCase):
    def test_three_to_five_rivals_each_with_https_sources(self):
        self.assertTrue(3 <= len(COMPETITORS["apps"]) <= 5)
        for app in COMPETITORS["apps"]:
            with self.subTest(app=app["name"]):
                self.assertTrue(app["sources"])
                self.assertTrue(all(re.match(r"https://", url) for url in app["sources"]))

    def test_every_row_fills_every_column(self):
        columns = {"name", "account", "bank", "data", "price", "turkish"}
        for row in [*COMPETITORS["apps"], COMPETITORS["ours"]]:
            self.assertLessEqual(columns, set(row))
            self.assertTrue(all(str(row[key]).strip() for key in columns))

    def test_no_cell_is_left_as_unknown(self):
        for row in COMPETITORS["apps"]:
            for key, value in row.items():
                with self.subTest(app=row["name"], column=key):
                    self.assertNotIn("bulunamadı", checks.tr_lower(str(value)))

    def test_the_unknown_check_reads_turkish_capitals(self):
        self.assertIn("bulunamadı", checks.tr_lower("BİLGİ BULUNAMADI"))

    def test_access_date_is_a_real_date_not_in_the_future(self):
        self.assertLessEqual(date.fromisoformat(COMPETITORS["accessed"]), date.today())


# A call that would send data from the browser; the privacy claim says the panel makes none.
NETWORK_CALL = re.compile(r"\bfetch\b|\bsendBeacon\s*\(|\bnew\s+(?:window\.)?(?:XMLHttpRequest|WebSocket|EventSource|RTCPeerConnection)\b"
                          r"|\bwindow\.open\s*\(|\blocation\.(?:href\s*=|assign\s*\(|replace\s*\()")


class PanelPrivacy(unittest.TestCase):
    @unittest.skipUnless(WEB_REPO.is_dir(), "the panel's repository is not next to this one")
    def test_the_panel_code_sends_nothing_and_its_page_allows_only_its_own_address(self):
        shipped = [path for path in (WEB_REPO / "src").rglob("*") if path.suffix in (".js", ".jsx") and ".test." not in path.name]
        self.assertGreaterEqual(len(shipped), 10)
        for path in shipped:
            with self.subTest(file=path.name):
                self.assertIsNone(NETWORK_CALL.search(path.read_text(encoding="utf-8")))
        # The cited CSP line is checked by the evidence test; here only that nothing widens it for connections.
        self.assertNotIn("connect-src", (WEB_REPO / "vite.config.js").read_text(encoding="utf-8"))

    def test_the_scan_finds_each_kind_of_call(self):
        for code in ("await fetch('/x')", "const get = fetch; get(url)", "navigator.sendBeacon(url, body)", "new XMLHttpRequest()",
                     "new window.XMLHttpRequest()", "new WebSocket(url)", "new EventSource(url)", "new RTCPeerConnection()",
                     "window.open(url)", "location.href = url", "location.assign(url)", "location.replace(url)"):
            self.assertIsNotNone(NETWORK_CALL.search(code), code)
        self.assertIsNone(NETWORK_CALL.search("const prefetched = refetchLater; // fetching is described here"))


class AiUsage(unittest.TestCase):
    def test_the_readme_table_and_the_deck_slide_share_one_source(self):
        from tests.test_text_hygiene import AI_SECTION
        section = AI_SECTION.search((ROOT / "README.md").read_text(encoding="utf-8")).group(0)
        lines = [line for line in section.splitlines() if line.startswith("| ")][2:]
        table = [[cell.strip().replace("`", "") for cell in line.strip().strip("|").split(" | ")] for line in lines]
        rows = build.load("ai_usage.json")
        self.assertEqual(len(rows), 4)
        self.assertEqual(table, [[r["task"], r["tool"], r["why"], r["risk"]] for r in rows])


if __name__ == "__main__":
    unittest.main()
