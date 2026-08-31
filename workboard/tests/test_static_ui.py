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

    def test_top_status_cards_are_removed_and_task_count_moves_into_task_panel(self):
        ids = self.parser.ids
        self.assertNotIn("statusCards", self.parser.by_id)
        self.assertNotIn("projectCount", self.parser.by_id)
        self.assertNotIn("todoCount", self.parser.by_id)
        self.assertNotIn("commitCount", self.parser.by_id)
        self.assertLess(ids.index("searchInput"), ids.index("sec-todos"))
        self.assertEqual(self.parser.by_id["todoLimit"]["tag"], "span")
        self.assertIn("task-count-badge", self.parser.by_id["todoLimit"]["attrs"].get("class", ""))

    def test_task_panel_contains_archive_toggle_and_timeline(self):
        self.assertEqual(self.parser.by_id["archiveToggle"]["tag"], "button")
        self.assertEqual(self.parser.by_id["archiveTimeline"]["tag"], "div")
        self.assertIn("archive-timeline", self.parser.by_id["archiveTimeline"]["attrs"].get("class", ""))
        self.assertIn("renderArchiveTimeline", self.script)
        self.assertIn("toggleArchiveTimeline", self.script)
        self.assertIn("this.filteredTodos('done')", self.script)
        self.assertIn("resultDescription || item.notes || item.name", self.script)

    def test_local_import_controls_live_inside_settings_dialog(self):
        self.assertEqual(self.parser.by_id["localImportForm"]["tag"], "form")
        self.assertEqual(self.parser.by_id["localImportRoot"]["tag"], "input")
        self.assertEqual(self.parser.by_id["localImportResult"]["tag"], "p")
        self.assertIn("settings-import-form", self.parser.by_id["localImportForm"]["attrs"].get("class", ""))
        self.assertLess(self.html.index('id="settingsDialog"'), self.html.index('id="localImportForm"'))
        self.assertNotIn("inline-import-form", self.html)
        self.assertIn("D:\\01工作日志", self.html)
        self.assertIn("importLocalTasks", self.script)
        self.assertIn("/import/local-tasks", self.script)

    def test_dashboard_contains_unified_settings_dialog(self):
        self.assertEqual(self.parser.by_id["settingsButton"]["tag"], "button")
        self.assertEqual(self.parser.by_id["settingsDialog"]["tag"], "dialog")
        self.assertEqual(self.parser.by_id["aiSettingsForm"]["tag"], "form")
        self.assertEqual(self.parser.by_id["aiApiKey"]["tag"], "input")
        self.assertEqual(self.parser.by_id["aiBaseUrl"]["tag"], "input")
        self.assertEqual(self.parser.by_id["aiModel"]["tag"], "input")
        self.assertNotIn("aiSettingsButton", self.parser.by_id)
        self.assertNotIn("aiSettingsDialog", self.parser.by_id)
        self.assertIn("openSettings", self.script)
        self.assertIn("loadAiSettings", self.script)
        self.assertIn("saveAiSettings", self.script)
        self.assertIn("/settings/ai", self.script)

    def test_dialogs_are_centered_after_global_reset(self):
        self.assertIn("dialog {", self.css)
        self.assertIn("margin: auto;", self.css)
        self.assertIn(".settings-section", self.css)

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

    def test_search_bar_filters_projects_active_tasks_and_archive_timeline(self):
        self.assertIn("placeholder=\"搜索项目、任务、联系人、标签、分类或描述\"", self.html)
        self.assertIn("getSearchQuery", self.script)
        self.assertIn("projectMatchesSearch", self.script)
        self.assertIn("todoMatchesSearch", self.script)
        self.assertIn("this.filteredTodos('todo')", self.script)
        self.assertIn("this.filteredTodos('done')", self.script)
        self.assertIn("没有匹配的任务。", self.script)
        self.assertIn("没有匹配的归档任务。", self.script)


if __name__ == "__main__":
    unittest.main()
