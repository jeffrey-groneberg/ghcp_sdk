"""Offline checks for the introduction's structure and source-code fidelity."""

import ast
from html import unescape
import importlib.util
from pathlib import Path
import re
import tempfile
import textwrap
import unittest
from unittest.mock import patch
from xml.dom import minidom
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("build_slides", ROOT / "scripts/build_slides.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class ExcerptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def extract(self, source, **options):
        (self.root / "sample.py").write_text(source, encoding="utf-8")
        with patch.object(build, "ROOT", self.root):
            return build.code_excerpt({"source": "sample.py", **options})

    def test_symbol_keeps_decorator_types_and_body(self):
        source = "@define_tool\nasync def inspect_file(params: FileParams):\n    return params.path\n"
        self.assertEqual(self.extract(source, symbol="inspect_file"), source.rstrip())

    def test_exact_range_keeps_final_message_guard_and_cleanup(self):
        source = textwrap.dedent("""\
            async def main():
                unsubscribe = session.on(on_event)
                try:
                    reply = await session.send_and_wait(prompt, timeout=60)
                    if reply is None:
                        raise RuntimeError("No final message")
                finally:
                    unsubscribe()
                print("done")
            """)
        excerpt = self.extract(source, start="unsubscribe = session.on(on_event)", end="unsubscribe()")
        self.assertIn("if reply is None:", excerpt)
        self.assertIn("finally:\n    unsubscribe()", excerpt)
        self.assertNotIn('print("done")', excerpt)

    def test_ambiguous_or_missing_markers_fail(self):
        for source in ("start()\nend()\nstart()\nend()\n", "start()\n"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.extract(source, start="start()", end="end()")

    def test_unknown_symbol_and_outside_file_fail(self):
        with self.assertRaises(ValueError):
            self.extract("def actual():\n    pass\n", symbol="missing")
        with patch.object(build, "ROOT", self.root), self.assertRaises(ValueError):
            build.code_excerpt({"source": str(ROOT / "scripts/build_slides.py"), "symbol": "main"})


class DeckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deck = build.read_deck()
        cls.html = build.HTML.read_text(encoding="utf-8")

    def test_main_flow_and_optional_appendix(self):
        slides = self.deck["slides"]
        self.assertEqual(len(slides), 22)
        self.assertEqual(sum(not slide.get("optional") for slide in slides), 18)
        self.assertTrue(all(slide.get("optional") for slide in slides[18:]))
        self.assertEqual([s["sample"] for s in slides if "sample" in s],
                         [f"{i:02d}" for i in range(1, 9)])
        optional = re.findall(r'<section[^>]*data-optional="true"[^>]*hidden>', self.html)
        self.assertEqual(len(optional), 4)

    def test_generated_decks_are_current(self):
        self.assertEqual(build.render_html(self.deck, self.html), self.html)
        build.check_powerpoint(self.deck)

    def test_python_excerpts_parse(self):
        for slide in self.deck["slides"]:
            code = slide.get("code")
            if not code or code.get("language", "python") != "python":
                continue
            with self.subTest(slide=slide["id"]):
                excerpt = build.code_excerpt(code)
                ast.parse("async def snippet():\n" + textwrap.indent(excerpt, "    "))
                self.assertNotIn("******", excerpt)

    def test_required_behavior_is_visible_in_excerpts(self):
        by_id = {s["id"]: s for s in self.deck["slides"]}
        streaming = build.code_excerpt(by_id["sample-01"]["code"])
        self.assertIn("reply is None", streaming)
        self.assertIn("finally:", streaming)
        self.assertIn("unsubscribe()", streaming)
        selection = build.code_excerpt(by_id["sample-03"]["code"])
        self.assertIn('current.agent.name != "reviewer"', selection)
        self.assertIn("raise RuntimeError", selection)
        mcp = build.code_excerpt(by_id["sample-05"]["code"])
        self.assertIn('"Authorization"', mcp)
        self.assertIn("token", mcp)
        self.assertNotIn("******", mcp)

    def test_all_source_excerpts_appear_in_html_and_powerpoint(self):
        with ZipFile(build.PPTX) as package:
            for index, slide in enumerate(self.deck["slides"], 1):
                code = slide.get("code")
                if not code:
                    continue
                with self.subTest(slide=slide["id"]):
                    expected = build.code_excerpt(code)
                    self.assertIn(expected, unescape(self.html))
                    xml = minidom.parseString(package.read(f"ppt/slides/slide{index}.xml"))
                    shape_texts = [
                        "\n".join(
                            "".join(
                                node.firstChild.data
                                for node in paragraph.getElementsByTagName("a:t")
                                if node.firstChild
                            )
                            for paragraph in body.getElementsByTagName("a:p")
                        )
                        for body in xml.getElementsByTagName("p:txBody")
                    ]
                    self.assertIn(expected, shape_texts)

    def test_powerpoint_appendix_is_hidden_in_slideshow(self):
        with ZipFile(build.PPTX) as package:
            for index, slide in enumerate(self.deck["slides"], 1):
                xml = minidom.parseString(package.read(f"ppt/slides/slide{index}.xml"))
                self.assertEqual(xml.documentElement.getAttribute("show") == "0",
                                 bool(slide.get("optional")))

    def test_narrative_text_matches_in_both_formats(self):
        with ZipFile(build.PPTX) as package:
            for index, slide in enumerate(self.deck["slides"], 1):
                if slide["layout"] == "title":
                    continue
                expected = [slide["title"]] + slide.get("items", [])
                expected += [slide[key] for key in ("lead", "note") if key in slide]
                for card in slide.get("cards", []):
                    expected += [card["title"], card["text"]]
                for column in slide.get("columns", []):
                    expected += [column["title"]] + column["items"]
                for row in slide.get("rows", []):
                    expected += row
                xml = minidom.parseString(package.read(f"ppt/slides/slide{index}.xml"))
                text = "\n".join(
                    node.firstChild.data for node in xml.getElementsByTagName("a:t")
                    if node.firstChild
                )
                for phrase in expected:
                    with self.subTest(slide=slide["id"], phrase=phrase):
                        self.assertIn(phrase.replace("`", ""), text)
                        self.assertIn(build.inline(phrase), self.html)

    def test_no_old_examples_or_slogans(self):
        for phrase in ("fictional weather", "What is your name?", "hot swap",
                       "Understand first.", "get to green", "******"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase.lower(), self.html.lower())


if __name__ == "__main__":
    unittest.main()
