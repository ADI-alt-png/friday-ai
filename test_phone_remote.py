import importlib
import os
import queue
import sys
import tempfile
import unittest


sys.path.insert(0, os.path.dirname(__file__))
friday = importlib.import_module("friday")


class PhoneRemoteTests(unittest.TestCase):
    def test_build_phone_remote_url_uses_ip_port_and_token(self):
        url = friday.build_phone_remote_url("192.168.1.25", 8765, "abc123")
        self.assertEqual(url, "http://192.168.1.25:8765/?key=abc123")

    def test_phone_remote_token_is_persisted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "phone_remote_token.txt")
            token = friday.get_or_create_phone_remote_token(path)
            self.assertEqual(token, friday.get_or_create_phone_remote_token(path))
            with open(path, encoding="utf-8") as f:
                self.assertEqual(token, f.read().strip())

    def test_phone_remote_page_contains_command_api_and_voice_button(self):
        page = friday.build_phone_remote_page("abc123", "http://192.168.1.25:8765/?key=abc123")
        self.assertIn("FRIDAY Phone Remote", page)
        self.assertIn("/api/command?key=abc123", page)
        self.assertIn("SpeechRecognition", page)
        self.assertIn("Start Voice", page)

    def test_submit_phone_command_queues_command_and_logs_user_message(self):
        command_queue = queue.Queue()
        log = []

        result = friday.submit_phone_command(
            "open gmail",
            command_queue=command_queue,
            log=log,
            now=lambda: "11:59",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(command_queue.get_nowait(), "open gmail")
        self.assertEqual(log[-1]["role"], "user")
        self.assertEqual(log[-1]["text"], "open gmail")
        self.assertEqual(log[-1]["time"], "11:59")

    def test_submit_phone_command_rejects_empty_text(self):
        result = friday.submit_phone_command("   ", command_queue=queue.Queue(), log=[])
        self.assertFalse(result["ok"])
        self.assertIn("empty", result["message"].lower())


if __name__ == "__main__":
    unittest.main()
