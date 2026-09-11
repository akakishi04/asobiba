from __future__ import annotations

import unittest

import numpy as np

from fold_lm.v05.accounting import ExecutionAccounting, measure_reference_steps
from fold_lm.v05.core import ReferenceLinearCore
from fold_lm.v05.state import BudgetState, EvidenceState, WorkingState


class V05ExecutionAccountingTests(unittest.TestCase):
    def setUp(self):
        self.evidence = EvidenceState(evidence_time=2, revision=3)
        self.working = WorkingState(
            evidence_time=2,
            internal_step=0,
            slots=np.array([[1.0, -1.0], [0.5, 0.25]], dtype=np.float64),
        )
        self.budget = BudgetState(internal_steps_remaining=3, acquisitions_remaining=4)
        self.core = ReferenceLinearCore(
            weight=np.array([[0.2, 0.1], [-0.3, 0.4]], dtype=np.float64),
            bias=np.array([0.05, -0.1], dtype=np.float64),
            gate=np.array([1.0, 0.5], dtype=np.float64),
        )

    @staticmethod
    def _clock(*values: float):
        iterator = iter(values)
        return lambda: next(iterator)

    def test_counts_steps_active_modules_and_wall_clock(self):
        contexts = [
            np.zeros((2, 2), dtype=np.float64),
            np.full((2, 2), 0.25, dtype=np.float64),
        ]
        evidence, working, budget, accounting = measure_reference_steps(
            self.evidence,
            self.working,
            self.budget,
            self.core,
            contexts,
            clock=self._clock(10.0, 10.25),
        )
        self.assertIs(evidence, self.evidence)
        self.assertEqual(working.evidence_time, 2)
        self.assertEqual(working.internal_step, 2)
        self.assertEqual(budget.internal_steps_remaining, 1)
        self.assertEqual(budget.acquisitions_remaining, 4)
        self.assertEqual(accounting.internal_steps, 2)
        self.assertEqual(accounting.active_module_invocations, 2)
        self.assertEqual(accounting.max_active_modules_per_step, 1)
        self.assertEqual(accounting.wall_clock_seconds, 0.25)

    def test_zero_steps_report_zero_active_modules(self):
        evidence, working, budget, accounting = measure_reference_steps(
            self.evidence,
            self.working,
            self.budget,
            self.core,
            [],
            clock=self._clock(4.0, 4.125),
        )
        self.assertIs(evidence, self.evidence)
        self.assertEqual(working.internal_step, 0)
        self.assertEqual(budget, self.budget)
        self.assertEqual(accounting.internal_steps, 0)
        self.assertEqual(accounting.active_module_invocations, 0)
        self.assertEqual(accounting.max_active_modules_per_step, 0)
        self.assertEqual(accounting.wall_clock_seconds, 0.125)

    def test_budget_exhaustion_is_not_hidden_by_accounting(self):
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            measure_reference_steps(
                self.evidence,
                self.working,
                BudgetState(internal_steps_remaining=1, acquisitions_remaining=0),
                self.core,
                [np.zeros((2, 2)), np.zeros((2, 2))],
                clock=self._clock(1.0),
            )

    def test_invalid_clock_is_rejected(self):
        with self.assertRaises(TypeError):
            measure_reference_steps(
                self.evidence,
                self.working,
                self.budget,
                self.core,
                [],
                clock=3.0,
            )
        with self.assertRaisesRegex(ValueError, "monotonic"):
            measure_reference_steps(
                self.evidence,
                self.working,
                self.budget,
                self.core,
                [],
                clock=self._clock(2.0, 1.0),
            )

    def test_execution_accounting_rejects_inconsistent_counts(self):
        with self.assertRaises(ValueError):
            ExecutionAccounting(0, 1, 1, 0.0)
        with self.assertRaises(ValueError):
            ExecutionAccounting(2, 1, 1, 0.0)
        with self.assertRaises(ValueError):
            ExecutionAccounting(1, 1, 0, 0.0)
        with self.assertRaises(ValueError):
            ExecutionAccounting(1, 1, 1, float("nan"))


if __name__ == "__main__":
    unittest.main()
