from __future__ import annotations

import unittest

from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter
from fold_lm.v05_benchmarks import gate_e_c133_real_retrieval_integration as c133


class V05RetrievalBoundedRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.adapter = PersistedStructuralRetrievalAdapter(c133.CORPUS)

    def test_real_bounded_false_negative_recovers_exact_q6(self):
        evidence, trace = self.adapter.retrieve_with_exact_recovery(
            (0, 0, 0, 0, 0, 0, 1, 0),
            (1, 0),
            schema=c133.SCHEMA,
            scan_limit=1,
            probes=1,
        )
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.key, "q6")
        self.assertEqual(evidence.evidence_value, 0)
        self.assertEqual(trace["bounded"]["mode"], "bounded_lsh")
        self.assertEqual(trace["bounded"]["vectors_scored"], 1)
        self.assertTrue(trace["exact_attempted"])
        self.assertTrue(trace["recovered_from_bounded_miss"])
        self.assertEqual(trace["final_mode"], "exact")
        self.assertEqual(trace["exact"]["mode"], "exact")
        self.assertEqual(trace["exact"]["vectors_scored"], self.adapter.record_count)

    def test_bounded_hit_does_not_pay_exact_fallback_q5(self):
        evidence, trace = self.adapter.retrieve_with_exact_recovery(
            (0, 0, 0, 0, 0, 1, 0, 0),
            (0, 1),
            schema=c133.SCHEMA,
            scan_limit=1,
            probes=1,
        )
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.key, "q5")
        self.assertFalse(trace["exact_attempted"])
        self.assertFalse(trace["recovered_from_bounded_miss"])
        self.assertEqual(trace["final_mode"], "bounded_lsh")
        self.assertIsNone(trace["exact"])

    def test_true_miss_remains_none_after_exact_fallback(self):
        evidence, trace = self.adapter.retrieve_with_exact_recovery(
            (-1, 0, 0, 0, 0, 0, 0, 0),
            (1, 0),
            schema=c133.SCHEMA,
            scan_limit=1,
            probes=1,
        )
        self.assertIsNone(evidence)
        self.assertTrue(trace["exact_attempted"])
        self.assertFalse(trace["recovered_from_bounded_miss"])
        self.assertEqual(trace["final_mode"], "none")
        self.assertIsNotNone(trace["exact"])


if __name__ == "__main__":
    unittest.main()
