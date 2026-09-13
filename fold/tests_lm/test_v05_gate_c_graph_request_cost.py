from __future__ import annotations

import copy
import unittest
from unittest.mock import Mock

import torch
from fold_lm.v05_benchmarks import gate_c_graph_request_cost as b


class V05GateCGraphRequestCostTests(unittest.TestCase):
    def setUp(self):
        self.a = (
            torch.zeros(2, dtype=torch.int64),
            torch.zeros(2, 3, dtype=torch.int64),
            torch.zeros(2, 3, dtype=torch.int64),
        )
        self.spec = tuple((tuple(t.shape), t.dtype) for t in self.a)

    def records(self):
        return [
            dict(round=r, variant=v, wall_ms=(i + 1.0) * (r + 1))
            for r in range(4) for i, v in enumerate(b.VARIANTS)
        ]

    def test_balanced_order(self):
        orders = [b.order_for_round(r) for r in range(4)]
        for i in range(4):
            self.assertEqual(set(o[i] for o in orders), set(b.VARIANTS))
        for r in (True, -1, 1.5):
            with self.assertRaises(ValueError):
                b.order_for_round(r)

    def test_request_keeps_strict_validation(self):
        fn = Mock()
        b.validate_request(self.a, self.spec, fn)
        fn.assert_called_once_with(*self.a)

    def test_wrong_metadata_rejected_before_strict(self):
        cases = [
            self.a[:2], list(self.a), (None, *self.a[1:]),
            (self.a[0].float(), *self.a[1:]),
            (torch.ones(3, dtype=torch.int64), *self.a[1:]),
        ]
        for case in cases:
            fn = Mock()
            with self.assertRaises(ValueError):
                b.validate_request(case, self.spec, fn)
            fn.assert_not_called()

    def test_strict_range_exception_propagates(self):
        fn = Mock(side_effect=ValueError('range'))
        with self.assertRaisesRegex(ValueError, 'range'):
            b.validate_request(self.a, self.spec, fn)

    def test_valid_output(self):
        b.validate_output(torch.zeros(2, 4), (2, 4))

    def test_invalid_output(self):
        for out in (
            torch.zeros(2, 3), torch.zeros(2, 4, dtype=torch.float64),
            torch.full((2, 4), float('nan')), torch.full((2, 4), float('inf')),
        ):
            with self.assertRaises(ValueError):
                b.validate_output(out, (2, 4))

    def test_summary_ratios(self):
        summary = b.summarize(self.records(), 4)
        self.assertEqual(summary['record_count'], 16)
        self.assertEqual(summary['paired_ratios']['triton_vs_dense_graph']['median'], 4 / 3)
        self.assertEqual(summary['paired_ratios']['dense_eager_to_graph_speedup']['median'], 1 / 3)

    def test_summary_order_invariant(self):
        records = self.records()
        self.assertEqual(b.summarize(records, 4), b.summarize(list(reversed(records)), 4))

    def test_missing_duplicate_rejected(self):
        records = self.records()
        for bad in (records[:-1], records + [records[0]]):
            with self.assertRaises(ValueError):
                b.summarize(bad, 4)

    def test_bad_timings_rounds_variants_rejected(self):
        for field, value in (
            ('wall_ms', 0), ('wall_ms', -1), ('wall_ms', float('nan')),
            ('wall_ms', float('inf')), ('wall_ms', True), ('variant', 'unknown'),
            ('round', True), ('round', 4), ('round', -1),
        ):
            records = copy.deepcopy(self.records())
            records[0][field] = value
            with self.assertRaises(ValueError):
                b.summarize(records, 4)
        for rounds in (0, True, -1, 1.5):
            with self.assertRaises(ValueError):
                b.summarize([], rounds)


if __name__ == '__main__':
    unittest.main()
