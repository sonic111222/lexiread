import unittest

from backend.ai import AIError, MAX_INPUT_CHARS, _build_messages


class AiInputTests(unittest.TestCase):
    def test_normal_analysis_builds_messages(self):
        analysis = {
            "paragraphs": [{"text": "A short passage."}],
            "questions": [{"number": 1, "stem": "Why?", "options": [{"label": "A", "text": "Because."}]}],
            "instructions": [],
            "kind": "reading",
            "title": "Test",
        }
        messages = _build_messages(analysis, "CET-4")
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("A short passage.", messages[1]["content"])

    def test_overlong_analysis_is_rejected(self):
        analysis = {
            "paragraphs": [{"text": "x" * (MAX_INPUT_CHARS + 1)}],
            "questions": [],
            "instructions": [],
            "kind": "reading",
            "title": "Too long",
        }
        with self.assertRaises(AIError):
            _build_messages(analysis, "CET-4")


if __name__ == "__main__":
    unittest.main()
