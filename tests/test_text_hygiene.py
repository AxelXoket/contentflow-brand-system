"""Every text file in the repository: no long dash, no banned style word, no trace of who asked or wrote, LF endings."""
import re
import subprocess
import unittest

from tests import ROOT

import checks

TEXT_SUFFIXES = {".py", ".json", ".md", ".html", ".txt", ".gitignore"}
# The banned list has to be written down once; its own definition is the only text the scan skips.
BANNED_LIST = re.compile(r"^STYLE_BANNED = \(.*?\)\n", re.MULTILINE | re.DOTALL)
# Phrases that would say who asked for or wrote the work. Built from parts so this file does not match itself.
TRACES = ["own" + "er", "maint" + "ainer", "ag" + "ent", "aj" + "an", "kullanıcı " + "istedi", "talep " + "üzerine",
          "istendiği " + "gibi", "clau" + "de", "anthro" + "pic", "co-" + "authored", "generated " + "with"]


def repo_text_files() -> list:
    """Files git would commit (tracked or new, ignored ones left out), limited to text."""
    listed = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.splitlines()
    return [ROOT / name for name in listed if (ROOT / name).suffix in TEXT_SUFFIXES or name.endswith(".gitignore")]


# The README's AI-usage section names the tools it describes; the tool names stay out of every other text.
AI_SECTION = re.compile(r"^## Yapay zekâyı nerede ve nasıl kullandım\n.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL)
TOOL_NAMES = ("clau" + "de", "anthro" + "pic")


def problems(text: str, tools_named: bool = False) -> list[str]:
    found = checks.style_problems(text)
    low = checks.tr_lower(text)
    traces = [word for word in TRACES if not (tools_named and word in TOOL_NAMES)]
    found += [f"trace {word}" for word in traces if re.search(rf"(?<![\w-]){re.escape(word)}(?!\w)", low)]
    if "\r" in text:
        found.append("CRLF line ending")
    return found


class RepositoryText(unittest.TestCase):
    def test_every_text_file_is_clean(self):
        files = repo_text_files()
        self.assertGreaterEqual(len(files), 20)
        for path in files:
            with self.subTest(file=path.relative_to(ROOT).as_posix()):
                text = path.read_bytes().decode("utf-8")
                if path.name == "checks.py":
                    text, removed = BANNED_LIST.subn("", text)
                    self.assertEqual(removed, 1)
                if path == ROOT / "README.md":
                    sections = AI_SECTION.findall(text)
                    self.assertEqual(len(sections), 1)
                    self.assertEqual(problems(sections[0], tools_named=True), [])
                    text = AI_SECTION.sub("", text)
                self.assertEqual(problems(text), [])

    def test_the_scan_sees_the_code_the_content_and_the_built_blog(self):
        names = {path.relative_to(ROOT).as_posix() for path in repo_text_files()}
        for expected in ("tools/checks.py", "content/blog.md", "brand/brand.json", "deliverables/icerik-seti/blog.html"):
            self.assertIn(expected, names)


class Detector(unittest.TestCase):
    def test_each_rule_fires_on_a_planted_violation(self):
        self.assertIn(f"long dash U+{0x2014:04X}", problems(f"a {chr(0x2014)} b"))
        self.assertIn(f"banned word {checks.STYLE_BANNED[0]}", problems(f"we {checks.STYLE_BANNED[0]} here"))
        self.assertIn(f"trace {TRACES[0]}", problems(f"the {TRACES[0]} decided"))
        self.assertIn("CRLF line ending", problems("a\r\nb"))

    def test_tool_names_pass_only_where_the_ai_section_allows_them_and_other_traces_never(self):
        tool = TOOL_NAMES[0]
        self.assertIn(f"trace {tool}", problems(f"metni {tool} ile yazdım"))
        self.assertEqual(problems(f"metni {tool} ile yazdım", tools_named=True), [])
        self.assertIn(f"trace {TRACES[0]}", problems(f"the {TRACES[0]} decided", tools_named=True))

    def test_the_ai_section_ends_at_the_next_heading(self):
        text = "## Giriş\nx\n## Yapay zekâyı nerede ve nasıl kullandım\ny\n## Testler\nz\n"
        self.assertEqual(AI_SECTION.sub("", text), "## Giriş\nx\n## Testler\nz\n")

    def test_clean_text_passes(self):
        self.assertEqual(problems("Sade bir satır.\nİkinci satır - kısa çizgiyle.\n"), [])


if __name__ == "__main__":
    unittest.main()
