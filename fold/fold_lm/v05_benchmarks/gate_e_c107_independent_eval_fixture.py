"""Independent C107 evaluator fixture.

This file intentionally does not import any C97-C106 benchmark/oracle/generator.
It reconstructs the registered V5-E mechanism-selection semantics independently
for cross-generator falsification.
"""
from __future__ import annotations

import itertools

ANSWER = 0
READ_MEMORY = 1
RETRIEVE = 2
OBSERVE = 3
ASK_USER = 4
STOP_UNRESOLVED = 5

ALL_MASKS = tuple(itertools.product((0, 1), repeat=4))


def independent_expected_action(
    dependency: int,
    evidence_present: int,
    mask: tuple[int, int, int, int],
) -> int:
    if dependency == 0 or evidence_present == 1:
        return ANSWER
    memory, retrieval, observation, ask_user = mask
    if memory:
        return READ_MEMORY
    if retrieval:
        return RETRIEVE
    if observation:
        return OBSERVE
    if ask_user:
        return ASK_USER
    return STOP_UNRESOLVED


def independent_visible(
    base: int,
    dependency: int,
    hidden: int,
    evidence_present: int,
) -> tuple[int, int, int, int]:
    observed_hidden = hidden if evidence_present else 0
    return (base, dependency, evidence_present, observed_hidden)


def independent_rows(base: int = 3):
    rows = []
    for dependency, hidden, evidence_present, mask in itertools.product(
        (0, 1), (0, 1), (0, 1), ALL_MASKS
    ):
        visible = independent_visible(base, dependency, hidden, evidence_present)
        rows.append(
            {
                "base": base,
                "dependency": dependency,
                "hidden": hidden,
                "evidence_present": evidence_present,
                "visible": visible,
                "eligible_mask": tuple(mask),
                "expected_action": independent_expected_action(
                    dependency, evidence_present, tuple(mask)
                ),
            }
        )
    # Deliberately use a different stable order than the training generator.
    rows.sort(
        key=lambda r: (
            -sum(r["eligible_mask"]),
            tuple(reversed(r["eligible_mask"])),
            r["evidence_present"],
            r["dependency"],
            -r["hidden"],
        )
    )
    return rows
