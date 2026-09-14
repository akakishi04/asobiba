import unittest
from pathlib import Path

from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fold_lm" / "v05_benchmarks" / "fixtures" / "c133_structural_records.json"
)


class V05RetrievalAdapterTests(unittest.TestCase):
    def test_exact_retrieval_returns_persisted_evidence_and_provenance(self):
        adapter = PersistedStructuralRetrievalAdapter(FIXTURE)
        evidence, stats = adapter.retrieve(
            [0, 0, 0, 1, 0, 0, 0, 0],
            [0, 1],
            schema="decision-bit",
            exact=True,
        )
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.key, "q3")
        self.assertEqual(evidence.evidence_value, 1)
        self.assertEqual(evidence.source_sha256, adapter.source_sha256)
        self.assertEqual(evidence.index_fingerprint, adapter.index_fingerprint)
        self.assertEqual(stats["mode"], "exact")
        self.assertEqual(stats["records"], 8)

    def test_reloading_same_file_preserves_fingerprints(self):
        left = PersistedStructuralRetrievalAdapter(FIXTURE)
        right = PersistedStructuralRetrievalAdapter(FIXTURE)
        self.assertEqual(left.source_sha256, right.source_sha256)
        self.assertEqual(left.index_fingerprint, right.index_fingerprint)
        self.assertEqual(left.record_count, 8)

    def test_exact_search_scores_persisted_corpus_not_hidden_fallback(self):
        adapter = PersistedStructuralRetrievalAdapter(FIXTURE)
        evidence, stats = adapter.retrieve(
            [0, 0, 0, 0, 0, 0, 1, 0],
            [1, 0],
            schema="decision-bit",
            exact=True,
        )
        self.assertEqual(evidence.key, "q6")
        self.assertEqual(evidence.evidence_value, 0)
        self.assertEqual(stats["vectors_scored"], 8)
        self.assertEqual(stats["bucket_entries_visited"], 8)


if __name__ == "__main__":
    unittest.main()
