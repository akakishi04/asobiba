import unittest

from fold_lm.v05.commit_context import commit_context_matches


class V05CommitContextTests(unittest.TestCase):
    def test_unchanged_context_matches(self):
        self.assertTrue(
            commit_context_matches(
                verified_request_epoch=10,
                current_request_epoch=10,
                verified_provider_generation=4,
                current_provider_generation=4,
            )
        )

    def test_advanced_request_epoch_is_rejected(self):
        self.assertFalse(
            commit_context_matches(
                verified_request_epoch=10,
                current_request_epoch=11,
                verified_provider_generation=4,
                current_provider_generation=4,
            )
        )

    def test_advanced_provider_generation_is_rejected(self):
        self.assertFalse(
            commit_context_matches(
                verified_request_epoch=10,
                current_request_epoch=10,
                verified_provider_generation=4,
                current_provider_generation=5,
            )
        )

    def test_both_advanced_are_rejected(self):
        self.assertFalse(
            commit_context_matches(
                verified_request_epoch=10,
                current_request_epoch=11,
                verified_provider_generation=4,
                current_provider_generation=5,
            )
        )

    def test_negative_versions_are_rejected(self):
        with self.assertRaises(ValueError):
            commit_context_matches(
                verified_request_epoch=-1,
                current_request_epoch=0,
                verified_provider_generation=0,
                current_provider_generation=0,
            )


if __name__ == "__main__":
    unittest.main()
