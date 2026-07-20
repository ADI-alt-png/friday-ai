import importlib
import os
import tempfile
import unittest


friday = importlib.import_module("friday")


class ContextResearchTests(unittest.TestCase):
    def test_read_path_context_reads_text_file_and_saves_last_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "notes.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("Alpha project deadline is Monday.")

            result = friday.read_path_context(path)

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], path)
        self.assertIn("Alpha project deadline", result["text"])
        self.assertIn("Alpha project deadline", friday.LAST_CONTEXT_TEXT)

    def test_answer_from_context_uses_last_context(self):
        friday.LAST_CONTEXT_TEXT = "The laptop owner is Himesh. The project is FRIDAY."
        friday.LAST_CONTEXT_SOURCE = "test"
        original_ask_ai = friday.ask_ai
        try:
            friday.ask_ai = lambda prompt, use_history=False: "The owner is Himesh."
            answer = friday.answer_from_last_context("who is the owner")
        finally:
            friday.ask_ai = original_ask_ai

        self.assertIn("Himesh", answer)

    def test_research_memory_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "research.json")
            friday.record_research_memory(
                "AI assistants",
                ["AI assistants can read screens", "Local tools need permission"],
                path=path,
                now=lambda: "2026-06-05 10:00",
            )
            memory = friday.load_research_memory(path)

        self.assertEqual(memory[0]["topic"], "AI assistants")
        self.assertIn("read screens", memory[0]["notes"][0])

    def test_extract_command_payload_handles_prefixes(self):
        payload = friday.extract_command_payload(
            "ask screen what is written here",
            ["ask screen", "ask app"],
        )
        self.assertEqual(payload, "what is written here")


if __name__ == "__main__":
    unittest.main()
