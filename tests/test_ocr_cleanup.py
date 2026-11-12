import unittest

from backend.ocr import _fix_digit_confusions, _fix_ocr_text, _fix_split_words


class OcrCleanupTests(unittest.TestCase):
    def test_common_ocr_confusions(self):
        self.assertEqual(
            _fix_ocr_text("The best way is tO read eve ry day."),
            "The best way is to read every day.",
        )

    def test_question_number_is_not_turned_into_letter(self):
        self.assertEqual(_fix_ocr_text("1. What is the best way?"), "1. What is the best way?")

    def test_digit_letter_confusions(self):
        self.assertEqual(_fix_digit_confusions("th1s 0f Engl1sh"), "this of English")

    def test_split_word_merge(self):
        self.assertEqual(_fix_split_words("read eve ry day"), "read every day")

    def test_contractions_are_not_rewritten(self):
        self.assertEqual(_fix_ocr_text("I'll go now."), "I'll go now.")
        self.assertEqual(_fix_ocr_text("We'll see."), "We'll see.")


if __name__ == "__main__":
    unittest.main()
