import importlib
import json
import os
import tempfile
import unittest
from datetime import datetime


friday = importlib.import_module("friday")


class NextLevelAddonsTests(unittest.TestCase):
    def test_parse_reminder_in_minutes(self):
        now = datetime(2026, 6, 6, 10, 0)
        parsed = friday.parse_reminder_command("remind me in 15 minutes to drink water", now=now)

        self.assertEqual(parsed["text"], "drink water")
        self.assertEqual(parsed["due"], "2026-06-06 10:15")

    def test_task_round_trip_and_due_lookup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "tasks.json")
            task = friday.add_task("drink water", due="2026-06-06 10:15", path=path)
            due = friday.get_due_tasks(now=datetime(2026, 6, 6, 10, 16), path=path)

            friday.mark_task_done(task["id"], path=path)
            tasks = friday.load_tasks(path)

        self.assertEqual(due[0]["text"], "drink water")
        self.assertTrue(tasks[0]["done"])

    def test_build_file_index_and_search(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(os.path.join(temp_dir, "alpha.txt"), "w", encoding="utf-8") as f:
                f.write("FRIDAY can index project files and answer questions.")
            with open(os.path.join(temp_dir, "beta.txt"), "w", encoding="utf-8") as f:
                f.write("Unrelated notes.")

            index = friday.build_file_index(temp_dir)
            results = friday.search_file_index(index, "project files")

        self.assertEqual(len(index["items"]), 2)
        self.assertEqual(results[0]["name"], "alpha.txt")

    def test_dashboard_html_contains_core_sections(self):
        html = friday.build_dashboard_html(
            tasks=[{"text": "drink water", "due": "2026-06-06 10:15", "done": False}],
            research=[{"topic": "AI", "notes": ["note one"], "time": "now"}],
            history=[{"type": "command", "text": "open gmail", "time": "now"}],
            phone_url="http://127.0.0.1:8765/?key=test",
        )

        self.assertIn("FRIDAY Dashboard", html)
        self.assertIn("drink water", html)
        self.assertIn("open gmail", html)
        self.assertIn("127.0.0.1", html)

    def test_history_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "history.jsonl")
            friday.log_history("command", "open gmail", path=path, now=lambda: "10:00")
            items = friday.load_history(path=path)

        self.assertEqual(items[0]["type"], "command")
        self.assertEqual(items[0]["text"], "open gmail")


if __name__ == "__main__":
    unittest.main()
