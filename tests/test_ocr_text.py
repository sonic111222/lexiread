import unittest

from backend import samples
from backend.ocr_text import correct_text, score_text


class OcrTextCorrectionTests(unittest.TestCase):
    def test_common_photographed_word_errors(self):
        cases = {
            "Reading ComprehenS1011": "Reading Comprehension",
            "The best way is to memonze long lists.": "The best way is to memorize long lists.",
            "These connectlons make it easier.": "These connections make it easier.",
            "an interesting StOIY": "an interesting Story",
            "their EngIish is good": "their English is good",
            "the meamng of unfamiliar words": "the meaning of unfamiliar words",
            "Guessmg is not always correct.": "Guessing is not always correct.",
            "the effort strengthens mem01Y.": "the effort strengthens memory.",
            "Teachers should not use dictionanes in class.": "Teachers should not use dictionaries in class.",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(correct_text(source), expected)

    def test_joined_and_split_words(self):
        cases = {
            "used to con finn a guess": "used to confirm a guess",
            "the effort its elf strengthens memory": "the effort itself strengthens memory",
            "the meaning ofunfamiliar words": "the meaning of unfamiliar words",
            "itselfstrengthens memory": "itself strengthens memory",
            "Read the follo 、 ving P assage carefully.": "Read the following Passage carefully.",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(correct_text(source), expected)

    def test_question_and_option_formatting(self):
        self.assertEqual(
            correct_text("Directions： Read the passage， then answer．"),
            "Directions: Read the passage, then answer.",
        )
        self.assertEqual(correct_text("1 ， What is the main idea?"), "1. What is the main idea?")
        self.assertEqual(correct_text("１． What is the main idea?"), "1. What is the main idea?")
        self.assertEqual(
            correct_text("A. check B lgnore"),
            "A. check\nB. ignore",
        )
        self.assertEqual(
            correct_text("A. one B. two C. three D. four"),
            "A. one\nB. two\nC. three\nD. four",
        )

    def test_proper_nouns_and_titles_are_preserved(self):
        self.assertEqual(
            correct_text("Harvard University is in Cambridge."),
            "Harvard University is in Cambridge.",
        )
        self.assertEqual(correct_text("Why We Keep Old Photographs"), "Why We Keep Old Photographs")
        self.assertEqual(
            correct_text("On 12 March, Dr. Smith visited St. Mary's Hospital in New York."),
            "On 12 March, Dr. Smith visited St. Mary's Hospital in New York.",
        )
        self.assertEqual(correct_text("I met Will Smith yesterday."), "I met Will Smith yesterday.")

    def test_clean_prose_is_not_overcorrected(self):
        self.assertEqual(
            correct_text("She finished her homework when the phone rang."),
            "She finished her homework when the phone rang.",
        )
        self.assertEqual(
            correct_text("The hotel is three miles from here."),
            "The hotel is three miles from here.",
        )

    def test_clean_sample_text_is_unchanged(self):
        for sample in samples.sample_list():
            item = samples.get_sample(sample["id"])
            with self.subTest(sample=sample["id"]):
                self.assertEqual(correct_text(item["text"]), item["text"])

    def test_chinese_text_is_unchanged(self):
        text = "请阅读下面短文，然后回答问题。"
        self.assertEqual(correct_text(text), text)

    def test_clean_text_scores_higher_than_noise(self):
        self.assertGreater(
            score_text("The students read the passage and answer the questions."),
            score_text("Qxz zvx qq vbn"),
        )


if __name__ == "__main__":
    unittest.main()
