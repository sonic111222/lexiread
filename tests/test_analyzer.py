import unittest

from backend.analyzer import analyze
from backend.samples import CLOZE, READING


class AnalyzerTests(unittest.TestCase):
    def test_reading_sample(self):
        result = analyze(READING["text"])
        self.assertEqual(result["kind"], "reading")
        self.assertEqual(len(result["paragraphs"]), 4)
        self.assertEqual(len(result["questions"]), 4)
        self.assertEqual(result["questions"][0]["type"], "main")
        self.assertEqual([q["number"] for q in result["questions"]], [1, 2, 3, 4])
        self.assertTrue(all(q["options"] for q in result["questions"]))
        self.assertTrue(result["vocabulary"])
        self.assertTrue(result["phrases"])
        self.assertTrue(result["key_sentences"])
        self.assertNotIn("__", result["paragraphs"][0]["text"])

    def test_cloze_sample(self):
        result = analyze(CLOZE["text"])
        self.assertEqual(result["kind"], "cloze")
        self.assertEqual(len(result["paragraphs"]), 4)
        self.assertEqual(len(result["questions"]), 5)
        self.assertTrue(all(q["type"] == "cloze" for q in result["questions"]))
        self.assertTrue(all(q["context"] for q in result["questions"]))
        self.assertIn("______", result["questions"][0]["context"])
        for question in result["questions"]:
            self.assertEqual([o["label"] for o in question["options"]], ["A", "B", "C", "D"])

    def test_vocabulary_has_usage_context(self):
        result = analyze(READING["text"])
        attention = next(item for item in result["vocabulary"] if item["lookup"] == "attention")
        self.assertIn("attention", attention["context"])
        self.assertNotIn("__", attention["context"])

    def test_empty_text_rejected(self):
        with self.assertRaises(ValueError):
            analyze("   \n\n ")

    def test_title_override(self):
        result = analyze(READING["text"], override_title="My Custom Title")
        self.assertEqual(result["title"], "My Custom Title")


if __name__ == "__main__":
    unittest.main()
