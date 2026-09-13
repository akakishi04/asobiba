from __future__ import annotations
import copy
import unittest
import torch
from fold_lm.v05_benchmarks import gate_c_graph_memory_accounting as b


class V05GateCGraphMemoryAccountingTests(unittest.TestCase):
    def workers(self):
        results = []
        for i, variant in enumerate(b.VARIANTS):
            row = {field: 100 + 10 * i for field in b.FIELDS}
            results.append(dict(variant=variant, fixture_sha256=b.FIXTURE_SHA,
                                parity_passed=True, model_state_unchanged=True,
                                score_A=1.0, accounting=row))
        return results

    def test_variants_are_bounded(self):
        self.assertEqual(b.VARIANTS, ('dense_eager', 'triton_eager', 'dense_graph', 'triton_graph'))

    def test_storage_aliases_are_not_double_counted(self):
        source = torch.ones(16, dtype=torch.float32)
        result = b.tensor_accounting((source, source[4:8], source.view(4, 4)))
        self.assertEqual(result['unique_storage_bytes'], 64)
        self.assertEqual(result['logical_tensor_bytes'], (16 + 4 + 16) * 4)

    def test_independent_storages_count_separately(self):
        source = torch.ones(5, dtype=torch.int32)
        self.assertEqual(b.tensor_accounting((source, source.clone()))['unique_storage_bytes'], 40)

    def test_empty_tensor_zero_storage(self):
        self.assertEqual(b.tensor_accounting((torch.empty(0),))['unique_storage_bytes'], 0)

    def test_invalid_tensor_and_meta_rejected(self):
        for value in (None, 5):
            with self.assertRaises(TypeError):
                b.tensor_accounting((value,))
        with self.assertRaises(ValueError):
            b.tensor_accounting((torch.empty(3, device='meta'),))

    def test_all_variants_reported_and_bytes_not_added(self):
        summary = b.summarize(self.workers())
        self.assertEqual(set(summary['variants']), set(b.VARIANTS))
        pair = summary['comparisons']['triton_vs_dense_graph']['idle_reserved_bytes']
        self.assertEqual(pair['triton_minus_dense_bytes'], 10)
        self.assertEqual(pair['ratio'], 130 / 120)

    def test_order_independence(self):
        records = self.workers()
        self.assertEqual(b.summarize(records), b.summarize(records[::-1]))

    def test_missing_duplicate_unknown_rejected(self):
        records = self.workers()
        unknown = copy.deepcopy(records)
        unknown[0]['variant'] = 'unknown'
        for sample in (records[:-1], records + [records[0]], unknown):
            with self.assertRaises(ValueError):
                b.summarize(sample)

    def test_invalid_byte_counts_rejected(self):
        for val in (-1, True, 0.1, float('nan')):
            rows = self.workers()
            rows[0]['accounting']['model_unique_storage_bytes'] = val
            with self.assertRaises(ValueError):
                b.summarize(rows)

    def test_failed_validation_or_fixture_mismatch_rejected(self):
        for key, val in (('parity_passed', False), ('model_state_unchanged', False),
                         ('fixture_sha256', 'bad'), ('score_A', float('nan')),
                         ('score_A', True), ('score_A', 1.1)):
            rows = self.workers()
            rows[0][key] = val
            with self.assertRaises(ValueError):
                b.summarize(rows)

    def test_allocator_inconsistency_rejected(self):
        rows = self.workers()
        rows[0]['accounting']['idle_reserved_bytes'] = 50
        with self.assertRaises(ValueError):
            b.summarize(rows)
        rows = self.workers()
        rows[0]['accounting']['steady_peak_allocated_bytes'] = 50
        with self.assertRaises(ValueError):
            b.summarize(rows)

    def test_prior_c37_preserved_without_recursive_nesting(self):
        prior = {'experiment_id': 'C37-request-cost', 'records': [1, 2]}
        current = {'experiment_id': 'C38-memory'}
        first = b.preserve_c37(current, prior)
        second = b.preserve_c37(current, first)
        self.assertEqual(first, second)
        self.assertEqual(second['retained_C37_result'], prior)
        self.assertTrue(second['C37_result_retained'])
        self.assertFalse(b.preserve_c37(current, None)['C37_result_retained'])

    def test_unrelated_prior_result_not_discarded(self):
        with self.assertRaises(ValueError):
            b.preserve_c37({}, {'experiment_id': 'other'})

    def test_zero_denominator_reported_without_fake_ratio(self):
        rows = self.workers()
        rows[0]['accounting']['idle_allocated_bytes'] = 0
        result = b.summarize(rows)
        self.assertIsNone(result['comparisons']['triton_vs_dense_eager']['idle_allocated_bytes']['ratio'])


if __name__ == '__main__':
    unittest.main()
