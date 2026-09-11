from __future__ import annotations

import unittest

import numpy as np

from fold_lm.v05.state import (
    BudgetState,
    EvidenceRef,
    EvidenceState,
    Provenance,
    ProvenanceKind,
    WorkingState,
    advance_internal,
)


class V05StateTests(unittest.TestCase):
    def _observed(self, evidence_id: str = "obs-1") -> EvidenceRef:
        return EvidenceRef(
            evidence_id=evidence_id,
            provenance=Provenance(
                source_id="user-turn-1",
                kind=ProvenanceKind.OBSERVED,
                revision=3,
                evidence_time=2,
            ),
        )

    def test_evidence_state_accepts_observation_and_rejects_hypothesis(self):
        state = EvidenceState(evidence_time=2, revision=3, observations=(self._observed(),))
        self.assertEqual(state.observations[0].evidence_id, "obs-1")

        hypothesis = EvidenceRef(
            evidence_id="hyp-1",
            provenance=Provenance(
                source_id="internal-step-1",
                kind=ProvenanceKind.HYPOTHESIS,
                revision=3,
                evidence_time=2,
            ),
        )
        with self.assertRaisesRegex(ValueError, "hypothesis provenance"):
            EvidenceState(evidence_time=2, revision=3, observations=(hypothesis,))

    def test_evidence_state_rejects_duplicate_and_future_provenance(self):
        observed = self._observed()
        with self.assertRaisesRegex(ValueError, "duplicate evidence_id"):
            EvidenceState(evidence_time=2, revision=3, observations=(observed, observed))

        future = EvidenceRef(
            evidence_id="future",
            provenance=Provenance(
                source_id="tool-result",
                kind=ProvenanceKind.OBSERVED,
                revision=4,
                evidence_time=3,
            ),
        )
        with self.assertRaisesRegex(ValueError, "future evidence time|future revision"):
            EvidenceState(evidence_time=2, revision=3, observations=(future,))

    def test_working_slots_are_float64_copied_and_read_only(self):
        source = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        working = WorkingState(evidence_time=2, internal_step=0, slots=source)
        source[0, 0] = 99.0

        self.assertEqual(working.slots.dtype, np.float64)
        self.assertEqual(float(working.slots[0, 0]), 1.0)
        self.assertFalse(working.slots.flags.writeable)
        with self.assertRaises(ValueError):
            working.slots[0, 0] = 5.0

    def test_internal_step_preserves_evidence_time_revision_and_provenance(self):
        evidence = EvidenceState(evidence_time=2, revision=3, observations=(self._observed(),))
        working = WorkingState(evidence_time=2, internal_step=7, slots=np.zeros((2, 3)))
        budget = BudgetState(internal_steps_remaining=2, acquisitions_remaining=4)

        next_evidence, next_working, next_budget = advance_internal(
            evidence,
            working,
            budget,
            slots=np.ones((2, 3)),
        )

        self.assertIs(next_evidence, evidence)
        self.assertEqual(next_evidence.evidence_time, 2)
        self.assertEqual(next_evidence.revision, 3)
        self.assertIs(next_evidence.observations[0].provenance, evidence.observations[0].provenance)
        self.assertEqual(next_working.evidence_time, 2)
        self.assertEqual(next_working.internal_step, 8)
        self.assertEqual(next_budget.internal_steps_remaining, 1)
        self.assertEqual(next_budget.acquisitions_remaining, 4)

    def test_budget_is_hard_and_evidence_time_must_match(self):
        evidence = EvidenceState(evidence_time=2, revision=3, observations=(self._observed(),))
        exhausted = BudgetState(internal_steps_remaining=0, acquisitions_remaining=1)
        working = WorkingState(evidence_time=2, internal_step=0, slots=np.zeros((1, 1)))
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            advance_internal(evidence, working, exhausted)

        mismatched = WorkingState(evidence_time=1, internal_step=0, slots=np.zeros((1, 1)))
        with self.assertRaisesRegex(ValueError, "does not match"):
            advance_internal(
                evidence,
                mismatched,
                BudgetState(internal_steps_remaining=1, acquisitions_remaining=1),
            )


if __name__ == "__main__":
    unittest.main()
