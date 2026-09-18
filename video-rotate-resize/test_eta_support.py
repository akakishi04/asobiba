import unittest

from eta_support import _format_remaining


class EtaSupportTests(unittest.TestCase):
    def test_seconds_format(self):
        self.assertEqual(_format_remaining(42), "42秒")

    def test_minutes_format(self):
        self.assertEqual(_format_remaining(125), "2分")

    def test_hours_format(self):
        self.assertEqual(_format_remaining(2 * 3600 + 13 * 60), "2時間13分")

    def test_days_format(self):
        self.assertEqual(_format_remaining(27 * 3600), "1日3時間")


if __name__ == "__main__":
    unittest.main()
