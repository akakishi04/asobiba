from __future__ import annotations

import unittest

from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter
from fold_lm.v05_benchmarks import gate_e_c133_real_retrieval_integration as c133


class V05RetrievalMissSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.adapter = PersistedStructuralRetrievalAdapter(c133.CORPUS)

    def test_structure_miss_returns_none_with_provenance_stats(self):
        _, structure, semantics, _ = c133.CASES[0]
        evidence, stats = self.adapter.retrieve(
            tuple(-x for x in structure), semantics, schema=c133.SCHEMA, exact=True
        )
        self.assertIsNone(evidence)
        self.assertEqual(stats["mode"], "exact")
        self.assertEqual(stats["vectors_scored"], self.adapter.record_count)
        self.assertEqual(stats["source_sha256"], self.adapter.source_sha256)
        self.assertEqual(stats["index_fingerprint"], self.adapter.index_fingerprint)

    def test_wrong_schema_returns_none_with_provenance_stats(self):
        _, structure, semantics, _ = c133.CASES[0]
        evidence, stats = self.adapter.retrieve(
            structure, semantics, schema="wrong-schema", exact=True
        )
        self.assertIsNone(evidence)
        self.assertEqual(stats["mode"], "exact")
        self.assertEqual(stats["vectors_scored"], self.adapter.record_count)
        self.assertEqual(stats["source_sha256"], self.adapter.source_sha256)
        self.assertEqual(stats["index_fingerprint"], self.adapter.index_fingerprint)


if __name__ == "__main__":
    unittest.main()
