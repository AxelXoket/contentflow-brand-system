"""The live panel in headless Edge: the frames of adding an expense, for the video.

Only the "panel" build step runs this. It needs the network; every other step builds from the files it leaves in
assets/video/, so a build always uses the same captured frames.
"""
import json
import pathlib

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
VIDEO = ROOT / "assets" / "video"
TIMELINE = VIDEO / "timeline.json"
# A phone-wide page at twice the pixels: one CSS pixel is two video pixels, so the panel fills an 888 px card sharply.
PHONE = {"width": 444, "height": 900}
SCALE = 2
MARGIN = 16  # CSS px of page shown around a card
EDGE_ARGS = ["--disable-gpu", "--no-first-run", "--lang=tr-TR"]
AMOUNT = "250,00"
CATEGORY = "Market"
SUBMIT = "form button[type=submit]"


def card_box(page, heading: str) -> tuple[float, float]:
    """Top and height of the card under a heading, in page CSS pixels."""
    return tuple(page.get_by_role("heading", name=heading).evaluate(
        "h => { const r = h.closest('section').getBoundingClientRect(); return [r.top + scrollY, r.height]; }"))


def capture(url: str) -> dict:
    """Add one expense on the sample page and keep a frame after every step, then the whole page after the add."""
    VIDEO.mkdir(parents=True, exist_ok=True)
    for old in VIDEO.glob("*.png"):
        old.unlink()
    steps = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True, args=EDGE_ARGS)
        try:
            page = browser.new_page(viewport=PHONE, device_scale_factor=SCALE, locale="tr-TR", color_scheme="light")
            page.goto(url, wait_until="networkidle")
            top, height = card_box(page, "Harcama ekle")
            clip = {"x": 0, "y": top - MARGIN, "width": PHONE["width"], "height": height + 2 * MARGIN}

            def shot(seconds: float, still: bool = False) -> None:
                name = f"form-{len(steps) + 1:02d}.png"
                page.screenshot(path=VIDEO / name, clip=clip, full_page=True, caret="initial")
                steps.append({"file": name, "seconds": seconds, "still": still})

            shot(0.4)
            page.click("#expense-amount")
            shot(0.25)
            for char in AMOUNT:
                page.keyboard.type(char)
                shot(0.12)
            page.select_option("#expense-category", label=CATEGORY)
            shot(0.45)
            page.hover(SUBMIT)
            shot(0.35, still=True)
            page.click(SUBMIT)
            page.wait_for_timeout(400)
            shot(0.5)
            budget_top, _ = card_box(page, "Aylık bütçe")
            share_top, share_height = card_box(page, "Kategori dağılımı")
            page.mouse.move(0, 0)
            page.screenshot(path=VIDEO / "page-after.png", full_page=True)
        finally:
            browser.close()
    timeline = {"source": url, "amount": AMOUNT, "category": CATEGORY, "form": steps,
                "pan": {"file": "page-after.png", "top": round((budget_top - MARGIN) * SCALE),
                        "bottom": round((share_top + share_height + MARGIN) * SCALE)}}
    TIMELINE.write_text(json.dumps(timeline, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return timeline
