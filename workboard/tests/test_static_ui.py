import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


class StaticElementParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.by_id = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ids.append(element_id)
            self.by_id[element_id] = {"tag": tag, "attrs": attributes}


class StaticUITest(unittest.TestCase):
    def setUp(self):
        self.html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.script = (STATIC / "script.js").read_text(encoding="utf-8")
        self.parser = StaticElementParser()
        self.parser.feed(self.html)

    def test_main_sections_are_ordered_for_task_first_workflow(self):
        ids = self.parser.ids
        self.assertLess(ids.index("sec-todos"), ids.index("sec-projects"))
        self.assertLess(ids.index("sec-projects"), ids.index("sec-heatmap"))

    def test_todo_edit_dialog_contains_result_and_local_path_fields(self):
        self.assertEqual(self.parser.by_id["todoEditDialog"]["tag"], "dialog")
        self.assertEqual(self.parser.by_id["todoEditResultDescription"]["tag"], "textarea")
        self.assertEqual(self.parser.by_id["todoEditLocalPath"]["tag"], "input")
        self.assertEqual(self.parser.by_id["todoEditForm"]["tag"], "form")
        self.assertEqual(self.parser.by_id["todoArchiveRetry"]["tag"], "button")

    def test_script_contains_observable_task_edit_and_archive_handlers(self):
        for handler in ("openTodoEditor", "openTodoFolder", "saveTodoEdit", "retryArchive"):
            with self.subTest(handler=handler):
                self.assertRegex(self.script, r"\b" + re.escape(handler) + r"\s*\(")
        self.assertIn("addEventListener('dblclick'", self.script)
        self.assertIn("stopPropagation()", self.script)
        self.assertIn("workboard://open", self.script)
        self.assertIn("archive/retry", self.script)


if __name__ == "__main__":
    unittest.main()
