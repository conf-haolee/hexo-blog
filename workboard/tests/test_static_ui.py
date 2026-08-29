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
        self.css = (STATIC / "style.css").read_text(encoding="utf-8")
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

    def test_project_cards_open_local_paths_and_show_three_git_commits(self):
        for handler in ("openProjectFolder", "projectCommitList"):
            with self.subTest(handler=handler):
                self.assertRegex(self.script, r"\b" + re.escape(handler) + r"\s*\(")
        self.assertIn("project.localPath", self.script)
        self.assertIn("gitInfo.commits.slice(0, 3)", self.script)
        self.assertIn("project-commit-list", self.script)

    def test_quick_find_precedes_compact_status_cards(self):
        ids = self.parser.ids
        self.assertLess(ids.index("searchInput"), ids.index("projectCount"))
        self.assertLess(ids.index("searchInput"), ids.index("todoCount"))
        self.assertLess(ids.index("searchInput"), ids.index("commitCount"))
        self.assertIn("compact-status", self.parser.by_id["statusCards"]["attrs"].get("class", ""))
        self.assertIn(".compact-status .hero-card", self.css)

    def test_dashboard_uses_panel_names_and_overflow_safe_due_row(self):
        self.assertIn("<h2>任务面板</h2>", self.html)
        self.assertIn("<h2>项目面板</h2>", self.html)
        self.assertIn("capture-date-row", self.html)
        self.assertIn(".capture-date-row", self.css)
        self.assertIn("minmax(0, 1fr)", self.css)

    def test_project_card_double_click_prompts_without_local_path(self):
        self.assertIn("card.addEventListener('dblclick'", self.script)
        self.assertIn("this.openProjectFolder(project)", self.script)
        self.assertIn("项目未配置本地路径", self.script)


if __name__ == "__main__":
    unittest.main()
