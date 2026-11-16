"""The fit check in a real headless Edge: each rule fires on a broken layout and stays quiet on a fitting one."""
import pathlib
import tempfile
import unittest

from tests import ROOT  # noqa: F401

import build
import render

EDGE_FOUND = render.EDGE.is_file()


@unittest.skipUnless(EDGE_FOUND, "Microsoft Edge is not installed")
class FitReport(unittest.TestCase):
    def report(self, body: str, css: str = "") -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            page = pathlib.Path(tmp) / "page.html"
            page.write_text(build.page("test", css, body), encoding="utf-8")
            return render.fit_report(page, 800, 600)

    def test_a_fitting_page_has_no_problems(self):
        self.assertEqual(self.report('<p data-max-lines="1" data-name="kısa" style="width:300px">kısa bir satır</p>'), [])

    def test_text_wrapping_past_its_limit_is_reported_with_line_height_normal(self):
        body = ('<p data-max-lines="1" data-name="iki" style="width:120px;font-size:20px;line-height:normal">'
                'bir iki üç dört beş altı</p>')
        self.assertEqual(self.report(body), ["iki: 2 lines, at most 1"])

    def test_tight_line_heights_still_count_every_line(self):
        """Headlines use line-height 1.1 to 1.3, where the text boxes of two lines overlap."""
        for height in ("1.1", "1.12", "1.3"):
            with self.subTest(line_height=height):
                body = (f'<p data-max-lines="2" data-name="sıkı" style="width:160px;font-size:40px;line-height:{height}">'
                        'bir iki üç dört beş altı yedi</p>')
                self.assertEqual(len(self.report(body)), 1)
                self.assertRegex(self.report(body)[0], r"^sıkı: [3-9] lines, at most 2$")

    def test_a_real_image_headline_past_two_lines_is_refused(self):
        spec = {"theme": "dark", "eyebrow": "DENEME", "headline": "Bir iki üç dört beş altı yedi sekiz dokuz on on bir on iki",
                "body": "Kısa.", "items": []}
        with tempfile.TemporaryDirectory() as tmp:
            page = pathlib.Path(tmp) / "image.html"
            page.write_text(build.image_html(spec, pathlib.Path(tmp)), encoding="utf-8")
            found = render.fit_report(page, 1080, 1080)
        self.assertTrue(any(problem.startswith("headline: ") for problem in found), found)

    def test_text_pushed_out_above_its_box_is_reported(self):
        body = ('<div class="swatch" data-name="renk" style="height:40px;width:80px;display:flex;flex-direction:column;'
                'justify-content:flex-end;overflow:hidden"><b>Çok uzun bir renk adı burada üç dört satıra yayılır</b></div>')
        self.assertIn("renk: content above or left of the box", self.report(body))

    def test_an_image_that_did_not_load_is_reported(self):
        found = self.report('<img src="file:///C:/yok/olmayan-resim.png" alt="">')
        self.assertEqual(found, ["image did not load: file:///C:/yok/olmayan-resim.png"])

    def test_written_line_breaks_count_as_lines(self):
        body = '<p data-max-lines="2" data-name="üç" style="white-space:pre-line">a\nb\nc</p>'
        self.assertEqual(self.report(body), ["üç: 3 lines, at most 2"])

    def test_mixed_inline_styles_on_one_line_count_once(self):
        body = '<p data-max-lines="1" data-name="karışık" style="width:600px"><b>Kalın</b> ve <span style="font-size:30px">büyük</span></p>'
        self.assertEqual(self.report(body), [])

    def test_a_word_kept_whole_that_does_not_fit_is_reported_instead_of_split(self):
        body = f'<p data-max-lines="1" data-name="uzun" style="width:90px">{build.keep_together("expense-tracker-dashboard")}</p>'
        self.assertEqual(self.report(body), ["uzun: wider than its box"])

    def test_a_fixed_page_that_overflows_is_reported(self):
        body = '<section class="page" data-name="sayfa" style="height:100px;overflow:hidden"><div style="height:150px"></div></section>'
        self.assertEqual(self.report(body), ["sayfa: content 150px in a 100px box"])

    def test_a_slide_and_a_table_cell_are_watched_too(self):
        body = ('<section class="slide" data-name="slayt" style="height:50px;overflow:hidden"><div style="height:80px"></div></section>'
                '<table style="table-layout:fixed;width:60px"><tr><td data-name="hücre">'
                '<span class="nw">çokuzunbirkelimeburada</span></td></tr></table>')
        found = self.report(body)
        self.assertIn("slayt: content 80px in a 50px box", found)
        self.assertTrue(any(problem.startswith("hücre: content wider") for problem in found), found)


if __name__ == "__main__":
    unittest.main()
