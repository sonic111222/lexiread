import unittest

from backend.dictionary import normalize_query
from backend.providers.ecdict import EcdictProvider, available, entry_count


class DictionaryProviderTests(unittest.TestCase):
    def setUp(self):
        if not available():
            self.skipTest("bundled ECDICT subset is missing")
        self.provider = EcdictProvider()

    def test_bundled_dictionary_has_data(self):
        self.assertGreater(entry_count(), 20000)

    def test_lookup_common_word(self):
        entry = self.provider.lookup("deliberate")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["definition_lang"], "zh")
        self.assertEqual(entry["source"], "ECDICT 本地词库")
        self.assertTrue(any("故意" in item["meaning"] for item in entry["definitions"]))
        self.assertTrue(entry["forms"])

    def test_inflected_form_falls_back_to_lemma(self):
        entry = self.provider.lookup("children")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["matched_form"], "child")

    def test_unknown_word(self):
        self.assertIsNone(self.provider.lookup("zzzznotarealword"))

    def test_normalize_query(self):
        self.assertEqual(normalize_query("  “Deliberate,”  "), "Deliberate")
        self.assertEqual(normalize_query("look forward to"), "look forward to")


if __name__ == "__main__":
    unittest.main()
