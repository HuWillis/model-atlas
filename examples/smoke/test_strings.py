import unittest

from strings import normalize_names


class NormalizeNamesTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(normalize_names([]), [])

    def test_whitespace(self):
        self.assertEqual(normalize_names([" ", "\t", " Alice "]), ["Alice"])

    def test_duplicates_preserve_first_casing(self):
        self.assertEqual(normalize_names(["Alice", "ALICE", "alice"]), ["Alice"])

    def test_order(self):
        self.assertEqual(normalize_names([" Bob ", "Alice", "BOB", "Carol"]), ["Bob", "Alice", "Carol"])

    def test_unicode_casefold(self):
        self.assertEqual(normalize_names(["Straße", "STRASSE", "中文", " 中文 "]), ["Straße", "中文"])

    def test_input_unchanged(self):
        source = [" Alice ", "alice", ""]
        normalize_names(source)
        self.assertEqual(source, [" Alice ", "alice", ""])


if __name__ == "__main__":
    unittest.main()
