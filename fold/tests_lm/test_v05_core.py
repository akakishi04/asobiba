from __future__ import annotations

import unittest

import numpy as np

from fold_lm.v05.core import ReferenceLinearCore, reference_internal_step
from fold_lm.v05.state import (
    BudgetState,
    EvidenceRef,
    EvidenceState,
    Provenance,
    ProvenanceKind,
    WorkingState,
)


class V05ReferenceCoreTests(unittest.TestCase):
    def _evidence(self) -> EvidenceState:
        return EvidenceState(
            evidence_time=3,
            revision=7,
            observations=(
                EvidenceRef(
                    "obs-1",
                    Provenance(
                        source_id="user",
                        kind=ProvenanceKind.OBSERVED,
                        revision=7,
                        evidence_time=3,
                    ),
                ),
            ),
        )

    def _core(self) -> ReferenceLinearCore:
        return ReferenceLinearCore(
            weight=np.array([[2.0, -1.0], [0.5, 3.0]], dtype=np.float64),
            bias=np.array([0.25, -0.5], dtype=np.float64),
            gate=np.array([0.5, 1.0], dtype=np.float64),
        )

    def test_matches_manual_float64_reference(self):
        working = WorkingState(
            evidence_time=3,
            internal_step=4,
            slots=np.array([[1.0, 2.0], [-1.0, 0.5]], dtype=np.float64),
        )
        context = np.array([[0.5, -0.5], [2.0, 1.5]], dtype=np.float64)
        core = self._core()

        mixed = working.slots + context
        expected_delta = mixed @ core.weight.T + core.bias
        expected = working.slots + core.gate * expected_delta
        actual = core.compute_slots(working, context)

        self.assertEqual(actual.dtype, np.float64)
        np.testing.assert_array_equal(actual, expected)

    def test_reference_step_preserves_evidence_and_consumes_budget(self):
        evidence = self._evidence()
        working = WorkingState(3, 0, np.zeros((2, 2), dtype=np.float64))
        budget = BudgetState(internal_steps_remaining=2, acquisitions_remaining=5)

        next_evidence, next_working, next_budget = reference_internal_step(
            evidence,
            working,
            budget,
            self._core(),
            np.ones((2, 2), dtype=np.float64),
        )

        self.assertIs(next_evidence, evidence)
        self.assertEqual(next_evidence.evidence_time, 3)
        self.assertEqual(next_evidence.revision, 7)
        self.assertEqual(next_evidence.observations, evidence.observations)
        self.assertEqual(next_working.evidence_time, 3)
        self.assertEqual(next_working.internal_step, 1)
        self.assertEqual(next_budget.internal_steps_remaining, 1)
        self.assertEqual(next_budget.acquisitions_remaining, 5)

    def test_core_parameters_are_copied_read_only_and_deterministic(self):
        weight = np.eye(2, dtype=np.float64)
        bias = np.zeros(2, dtype=np.float64)
        gate = np.ones(2, dtype=np.float64)
        core = ReferenceLinearCore(weight, bias, gate)
        weight[0, 0] = 99.0
        bias[0] = 99.0
        gate[0] = 0.0

        self.assertEqual(core.weight[0, 0], 1.0)
        self.assertEqual(core.bias[0], 0.0)
        self.assertEqual(core.gate[0], 1.0)
        self.assertFalse(core.weight.flags.writeable)
        self.assertFalse(core.bias.flags.writeable)
        self.assertFalse(core.gate.flags.writeable)

        working = WorkingState(0, 0, np.array([[1.0, 2.0]], dtype=np.float64))
        context = np.array([[3.0, 4.0]], dtype=np.float64)
        first = core.compute_slots(working, context)
        second = core.compute_slots(working, context)
        np.testing.assert_array_equal(first, second)

    def test_rejects_invalid_shapes_values_and_gate(self):
        with self.assertRaises(ValueError):
            ReferenceLinearCore(np.ones((2, 3)), np.zeros(2), np.ones(2))
        with self.assertRaises(ValueError):
            ReferenceLinearCore(np.eye(2), np.zeros(3), np.ones(2))
        with self.assertRaises(ValueError):
            ReferenceLinearCore(np.eye(2), np.zeros(2), np.array([1.1, 0.5]))
        with self.assertRaises(ValueError):
            ReferenceLinearCore(np.array([[1.0, np.nan], [0.0, 1.0]]), np.zeros(2), np.ones(2))

        core = self._core()
        working = WorkingState(0, 0, np.zeros((1, 2), dtype=np.float64))
        with self.assertRaises(ValueError):
            core.compute_slots(working, np.zeros((2, 2), dtype=np.float64))
        with self.assertRaises(ValueError):
            core.compute_slots(working, np.array([[0.0, np.inf]], dtype=np.float64))

    def test_budget_exhaustion_prevents_reference_step(self):
        evidence = EvidenceState(0, 0)
        working = WorkingState(0, 0, np.zeros((1, 2), dtype=np.float64))
        budget = BudgetState(internal_steps_remaining=0, acquisitions_remaining=0)
        with self.assertRaises(ValueError):
            reference_internal_step(
                evidence,
                working,
                budget,
                self._core(),
                np.zeros((1, 2), dtype=np.float64),
            )


if __name__ == "__main__":
    unittest.main()
