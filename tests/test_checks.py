"""The content checks: every rule fires on a breaking input and stays quiet on the input next to the limit."""
import unittest

from tests import ROOT  # noqa: F401  (puts tools/ on the path)

import checks
from checks import BRAND

APP_URL = BRAND["app_url"]
SHORT_URL = BRAND["short_url"]
FILLER = "Panelde harcama listesi sade ve okunur bir düzende görünür."  # 9 words, no number, no avoided word


def make_blog(word_count=700, title="Harcama takibi rehberi", description=None, h1="Harcama takibi rehberi",
              h2="Harcama takibi için ilk adım", first="Harcama takibi ayın resmini gösterir.", link=True, disclaimer=True,
              extra=""):
    """A blog post that passes every rule, with exactly `word_count` counted words; each argument breaks one rule."""
    if description is None:
        description = "Harcama takibi için sade bir rehber. " + "a" * (130 - 37)
    parts = [f"# {h1}" if h1 else "", first, f"## {h2}", "{filler}", extra]
    if link:
        parts.append(f"[Paneli açın]({APP_URL})")
    if disclaimer:
        parts.append(BRAND["disclaimer"])
    body = "\n\n".join(part for part in parts if part)
    base = len(checks.words(body.replace("{filler}", "").replace(f"({APP_URL})", "")))
    need = word_count - base
    filler = " ".join([FILLER] * (need // 9) + (["Harcama " * (need % 9)] if need % 9 else []))
    body = body.replace("{filler}", filler.strip())
    meta = {"title": title, "description": description, "keyword": "harcama takibi", "slug": "x"}
    return meta, body


class TurkishText(unittest.TestCase):
    def test_turkish_lowercase_keeps_dotless_and_dotted_i(self):
        self.assertEqual(checks.tr_lower("IŞIK İZMİR"), "ışık izmir")

    def test_sentences_end_at_punctuation_and_line_breaks_and_skip_urls(self):
        text = f"Bir iki. Üç dört!\nBeş altı {APP_URL}"
        self.assertEqual(checks.sentences(text), ["Bir iki.", "Üç dört!", "Beş altı"])

    def test_same_words_ignore_case_punctuation_and_line_breaks_but_not_order_or_extra_words(self):
        self.assertTrue(checks.same_words("Ay bitti.\nPara nereye gitti?", "Ay bitti. Para nereye gitti?"))
        self.assertTrue(checks.same_words("Paneli açın", "PANELİ AÇIN."))
        self.assertFalse(checks.same_words("Hesap yok.", "Hesap yok. Banka yok."))
        self.assertFalse(checks.same_words("ay bitti", "bitti ay"))


class Urls(unittest.TestCase):
    def test_an_address_ends_before_the_punctuation_that_ends_the_sentence(self):
        text = "Açın: axelxoket.github.io/a-b. Sonra (https://x.io/1?q=2), bitti"
        self.assertEqual(checks.URL.findall(text), ["axelxoket.github.io/a-b", "https://x.io/1?q=2"])

    def test_a_turkish_number_is_not_an_address(self):
        self.assertEqual(checks.URL.findall("Tutar 1.250,50 TL, oran 0,1."), [])


class LongSentences(unittest.TestCase):
    LIMIT = BRAND["voice"]["max_sentence_words"]

    def test_limit_words_pass_and_one_more_fails(self):
        at_limit = " ".join(["harcama"] * self.LIMIT) + "."
        over = " ".join(["harcama"] * (self.LIMIT + 1)) + "."
        self.assertEqual(checks.long_sentences(at_limit), [])
        self.assertEqual(len(checks.long_sentences(over)), 1)

    def test_a_line_break_ends_a_sentence(self):
        half = " ".join(["harcama"] * 15)
        self.assertEqual(checks.long_sentences(f"{half}\n{half}"), [])

    def test_words_of_a_url_do_not_count(self):
        text = " ".join(["harcama"] * self.LIMIT) + f" {APP_URL}"
        self.assertEqual(checks.long_sentences(text), [])


class AvoidedWords(unittest.TestCase):
    def test_suffixed_and_upper_case_forms_are_caught(self):
        self.assertEqual(checks.avoided_words("Bu israfı durdurun."), ["israf"])
        self.assertEqual(checks.avoided_words("GARANTİLİ sonuç"), ["garanti"])
        self.assertEqual(checks.avoided_words("KESIN sonuç"), ["kesin"])

    def test_the_word_must_start_the_match(self):
        self.assertEqual(checks.avoided_words("akesin ve yatrack"), [])

    def test_text_inside_a_url_is_ignored(self):
        self.assertEqual(checks.avoided_words("Bakın: https://example.com/track"), [])


class SingularAddress(unittest.TestCase):
    def test_sen_forms_are_caught_in_any_case(self):
        self.assertEqual(checks.singular_address("Sen de deneyin, seninle başlar."), ["sen", "seninle"])

    def test_words_that_only_look_alike_pass(self):
        self.assertEqual(checks.singular_address("Bu sene sendika toplantısı var."), [])


class StyleRules(unittest.TestCase):
    def test_long_dashes_are_caught(self):
        self.assertEqual(checks.style_problems(f"a {chr(0x2014)} b {chr(0x2013)} c"), ["long dash U+2013", "long dash U+2014"])

    def test_banned_words_are_caught_at_the_start_of_a_word_with_any_suffix(self):
        banned = checks.STYLE_BANNED[2]
        self.assertEqual(checks.style_problems(f"A {banned.capitalize()} plan."), [f"banned word {banned}"])
        self.assertEqual(checks.style_problems(f"{banned}ness"), [f"banned word {banned}"])
        self.assertEqual(checks.style_problems(f"un{banned}"), [])

    def test_clean_text_passes(self):
        self.assertEqual(checks.style_problems("Sade bir cümle - kısa çizgiyle."), [])


class Numbers(unittest.TestCase):
    def test_a_number_passes_only_in_a_cited_phrase(self):
        self.assertEqual(checks.unexplained_numbers("Düğme 6 saniye ekranda kalır; toplamı tam %100,0 eder."), [])
        self.assertEqual(checks.unexplained_numbers("Düğme 6 dakika ekranda kalır."), ["6 dakika"])

    def test_suffixes_on_the_number_and_the_next_word_still_match(self):
        self.assertEqual(checks.unexplained_numbers("Harcama %80'ine ulaştığında; 5 adımda ayın resmi."), [])

    def test_a_number_without_a_source_is_reported_with_its_word(self):
        self.assertEqual(checks.unexplained_numbers("Kullanıcıların 7 katı daha hızlı."), ["7 katı"])

    def test_a_turkish_number_is_one_token(self):
        self.assertEqual(checks.unexplained_numbers("Örnek: 1.250,50 TL"), [])
        self.assertEqual(checks.unexplained_numbers("Örnek: 1.250 TL"), ["1.250 tl"])

    def test_number_words_are_checked_like_digits(self):
        self.assertEqual(checks.unexplained_numbers("Haftada beş dakika ayırın; on kategori var."), [])
        self.assertEqual(checks.unexplained_numbers("Haftada beş saat ayırın."), ["5 saat"])
        self.assertEqual(checks.unexplained_numbers("Harcama bütçenin yüzde seksenine ulaştıysa"), [])
        self.assertEqual(checks.unexplained_numbers("Harcama yüzde doksanı geçti."), ["%90 geçti"])

    def test_bir_yedi_and_words_holding_a_number_word_stay_words(self):
        self.assertEqual(checks.unexplained_numbers("Bir harcama yedi gün sonra online görünür."), [])

    def test_a_point_makes_an_ordinal_only_after_a_whole_number_that_starts_its_line(self):
        self.assertEqual(checks.unexplained_numbers("## 1. Harcama takibi\n- 2. madde"), [])
        self.assertEqual(checks.unexplained_numbers("Toplam 5. Sonra bakın."), ["5 sonra"])
        self.assertEqual(checks.unexplained_numbers("Toplamı tam %100,0."), ["%100,0"])

    def test_numbers_in_urls_and_hashtags_are_ignored(self):
        self.assertEqual(checks.unexplained_numbers("https://example.com/2026/9 ve #kasım2026"), [])

    def test_the_allowed_forms_come_from_the_brand_file_in_turkish_lower_case(self):
        brand = {"facts": [{"forms": ["9 Gün"]}], "own_numbers": [{"forms": ["8.", "%80 UYARI"]}]}
        self.assertEqual(checks.allowed_forms(brand), [("9", "gün"), ("8.", ""), ("%80", "uyarı")])

    def test_voice_problems_label_number_problems_with_the_shared_prefix(self):
        found = checks.voice_problems("Tam 7 kat.")
        self.assertEqual(found, [f"{checks.NUMBER_PROBLEM} 7 kat"])


class Posts(unittest.TestCase):
    @staticmethod
    def post(channel, length=None, text=None):
        link = checks.LINK_IN_BIO.get(channel, SHORT_URL)
        if text is None:
            text = link + " " + "x" * (length - len(link) - 1)
        return {"channel": channel, "text": text}

    def test_every_channel_allows_its_limit_and_refuses_one_more(self):
        for channel, limit in checks.CHANNEL_LIMITS.items():
            with self.subTest(channel=channel):
                self.assertEqual(checks.post_problems(self.post(channel, limit)), [])
                self.assertEqual(checks.post_problems(self.post(channel, limit + 1)),
                                 [f"{limit + 1} characters, {channel} allows {limit}"])

    def test_every_channel_allows_its_hashtags_and_refuses_one_more(self):
        for channel, limit in checks.HASHTAG_LIMITS.items():
            with self.subTest(channel=channel):
                tags = " ".join(f"#etiket{chr(97 + i)}" for i in range(limit + 1))
                link = checks.LINK_IN_BIO.get(channel, SHORT_URL)
                at_limit = self.post(channel, text=f"{link} {tags.rsplit(' ', 1)[0]}")
                over = self.post(channel, text=f"{link} {tags}")
                self.assertEqual(checks.post_problems(at_limit), [])
                self.assertEqual(checks.post_problems(over), [f"{limit + 1} hashtags, the guide allows {limit} on {channel}"])

    def test_a_post_without_the_panel_link_fails(self):
        self.assertEqual(checks.post_problems(self.post("X", text="Sade bir gönderi.")), ["no link to the panel"])

    def test_instagram_sends_the_reader_to_the_profile_instead_of_an_address(self):
        self.assertEqual(checks.post_problems(self.post("Instagram", text=f"Paneli açın: {SHORT_URL}")), ["no link to the panel"])
        self.assertEqual(checks.post_problems(self.post("Instagram", text="Paneli açın: BAĞLANTI PROFİLDE.")), [])
        self.assertEqual(checks.post_problems(self.post("X", text="Paneli açın: bağlantı profilde.")), ["no link to the panel"])

    def test_voice_rules_apply_to_posts(self):
        self.assertIn("avoided word israf", checks.post_problems(self.post("X", text=f"İsraf yok. {SHORT_URL}")))


class Blog(unittest.TestCase):
    def test_the_reference_post_passes(self):
        meta, body = make_blog()
        self.assertEqual(checks.blog_word_count(body), 700)
        self.assertEqual(checks.blog_problems(meta, body), [])

    def test_title_length_limit(self):
        limit = checks.BLOG_TITLE_MAX
        ok = "Harcama takibi " + "a" * (limit - 15)
        meta, body = make_blog(title=ok)
        self.assertEqual(checks.blog_problems(meta, body), [])
        meta, body = make_blog(title=ok + "a")
        self.assertEqual(checks.blog_problems(meta, body), [f"title has {limit + 1} characters, at most {limit}"])

    def test_description_length_limits(self):
        low, high = checks.BLOG_DESCRIPTION
        head = "Harcama takibi "
        for length, passes in ((low - 1, False), (low, True), (high, True), (high + 1, False)):
            with self.subTest(length=length):
                meta, body = make_blog(description=head + "a" * (length - len(head)))
                problems = checks.blog_problems(meta, body)
                expected = [] if passes else [f"description has {length} characters, {low} to {high} wanted"]
                self.assertEqual(problems, expected)

    def test_word_count_limits(self):
        low, high = checks.BLOG_WORDS
        for count, passes in ((low - 1, False), (low, True), (high, True), (high + 1, False)):
            with self.subTest(count=count):
                meta, body = make_blog(word_count=count)
                self.assertEqual(checks.blog_word_count(body), count)
                expected = [] if passes else [f"{count} words, {low} to {high} wanted"]
                self.assertEqual(checks.blog_problems(meta, body), expected)

    def test_exactly_one_h1(self):
        meta, body = make_blog(extra="# Harcama takibi ikinci başlık")
        self.assertIn("2 H1 headings, exactly 1 wanted", checks.blog_problems(meta, body))
        meta, body = make_blog(h1="")
        self.assertIn("0 H1 headings, exactly 1 wanted", checks.blog_problems(meta, body))

    def test_keyword_must_appear_in_each_place(self):
        cases = {"title": {"title": "Ay sonu rehberi"}, "H1": {"h1": "Ay sonu rehberi"},
                 "first paragraph": {"first": "Ayın resmi burada başlar."},
                 "description": {"description": "Ay sonu için sade bir rehber. " + "a" * 100}}
        for place, change in cases.items():
            with self.subTest(place=place):
                meta, body = make_blog(**change)
                self.assertEqual(checks.blog_problems(meta, body), [f"keyword missing from the {place}"])
        meta, body = make_blog(h2="İlk adım")
        self.assertEqual(checks.blog_problems(meta, body), ["keyword missing from every H2"])

    def test_a_paragraph_that_starts_with_a_number_is_still_the_first_paragraph(self):
        meta, body = make_blog(first="2026 boyunca harcama takibi ayın resmini gösterir.", extra="")
        self.assertNotIn("keyword missing from the first paragraph", checks.blog_problems(meta, body))
        meta, body = make_blog(first="- harcama takibi listesi\n\nAyın resmi burada başlar.")
        self.assertIn("keyword missing from the first paragraph", checks.blog_problems(meta, body))

    def test_keyword_match_follows_turkish_case(self):
        meta, body = make_blog(title="HARCAMA TAKİBİ REHBERİ")
        self.assertEqual(checks.blog_problems(meta, body), [])

    def test_link_and_disclaimer_are_required(self):
        meta, body = make_blog(link=False, word_count=700)
        self.assertEqual(checks.blog_problems(meta, body), ["no link to the panel"])
        meta, body = make_blog(disclaimer=False)
        self.assertEqual(checks.blog_problems(meta, body), ["no disclaimer"])

    def test_voice_rules_apply_to_the_blog(self):
        meta, body = make_blog(extra="Bu israf olmasın.")
        self.assertEqual(checks.blog_problems(meta, body), ["avoided word israf"])

    def test_link_and_picture_addresses_are_not_words(self):
        self.assertEqual(checks.blog_word_count("![Panel formu](blog-ekle.png) ve [Paneli açın](https://x.io/a)"), 3)

    def test_front_matter_is_read_from_the_real_post(self):
        meta, body = checks.read_front_matter(ROOT / "content" / "blog.md")
        self.assertEqual(set(meta), {"title", "slug", "keyword", "description"})
        self.assertTrue(body.startswith("# "))


class Claims(unittest.TestCase):
    def test_a_fact_is_found_by_its_number_phrase_only(self):
        self.assertEqual(checks.claims_in("Düğme 6 saniye ekranda kalır."), ["geri-al-6-saniye"])
        self.assertEqual(checks.claims_in("Düğme 6 dakika ekranda kalır."), [])

    def test_a_claim_is_found_by_its_phrase_in_any_case(self):
        self.assertEqual(checks.claims_in("VERİLERİNİZ TARAYICINIZDA KALIR."), ["veri-tarayicida"])

    def test_an_address_makes_no_claim(self):
        self.assertEqual(checks.claims_in("Bakın: https://example.com/csv"), [])

    def test_claims_come_from_the_brand_file(self):
        brand = {"facts": [{"id": "f", "forms": ["9 gün"]}], "product_claims": [{"id": "c", "phrases": ["kurulum"]}]}
        self.assertEqual(checks.claims_in("Kurulum yok, 9 günde biter.", brand), ["f", "c"])
        self.assertEqual(checks.claims_in("Hesap yok.", brand), [])


class Contrast(unittest.TestCase):
    def test_black_on_white_is_21_and_a_colour_on_itself_is_1(self):
        self.assertAlmostEqual(checks.contrast("#000000", "#FFFFFF"), 21.0, places=2)
        self.assertAlmostEqual(checks.contrast("#007A55", "#007A55"), 1.0, places=6)

    def test_order_does_not_matter(self):
        self.assertAlmostEqual(checks.contrast("#FE9A00", "#0F172B"), checks.contrast("#0F172B", "#FE9A00"), places=9)


if __name__ == "__main__":
    unittest.main()
