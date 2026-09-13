from __future__ import annotations

import copy
import unittest

import torch
from torch.nn import functional as F

from fold_lm.v05.modules import (
    HighPrecisionFixedRoutingCore,
    LearnedCoreConfig,
    SharedBasisFixedRoutingCore,
)


def _materialized_forward(
    core: SharedBasisFixedRoutingCore,
    working: torch.Tensor,
    context: torch.Tensor,
    route_index: int,
) -> torch.Tensor:
    z = working + context
    shared_delta = core.shared(z)
    normalized = core.norms[route_index](z)
    up, down = core.materialized_role_weights(route_index)
    hidden = F.gelu(F.linear(normalized, up, core.up_biases[route_index]))
    routed_delta = F.linear(hidden, down, core.down_biases[route_index])
    gate = torch.sigmoid(core.gate_logits).to(dtype=working.dtype, device=working.device)
    return working + gate * (shared_delta + routed_delta)


class SharedBasisFixedRoutingCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        torch.manual_seed(1234)
        self.config = LearnedCoreConfig(width=16, slots=3, modules=2, hidden_mult=2)
        self.dense = HighPrecisionFixedRoutingCore(self.config)
        self.core = SharedBasisFixedRoutingCore(self.dense, rank=3)

    def test_is_explicit_opt_in_and_keeps_config(self) -> None:
        self.assertIsInstance(self.dense, HighPrecisionFixedRoutingCore)
        self.assertIsInstance(self.core, SharedBasisFixedRoutingCore)
        self.assertEqual(self.core.config, self.config)
        self.assertEqual(self.core.rank, 3)

    def test_initial_working_state(self) -> None:
        state = self.core.initial_working_state(4)
        self.assertEqual(tuple(state.shape), (4, 3, 16))
        self.assertTrue(torch.equal(state, torch.zeros_like(state)))

    def test_gemm_native_matches_materialized_forward(self) -> None:
        working = torch.randn(5, 3, 16) * 0.05
        context = torch.randn_like(working) * 0.05
        for route in range(2):
            native = self.core(working, context, route_index=route)
            reference = _materialized_forward(self.core, working, context, route)
            self.assertTrue(torch.allclose(native, reference, rtol=5e-4, atol=1e-4))

    def test_gemm_native_matches_materialized_gradients(self) -> None:
        native_core = copy.deepcopy(self.core)
        reference_core = copy.deepcopy(self.core)
        working = torch.randn(4, 3, 16) * 0.05
        context = torch.randn_like(working) * 0.05
        target = torch.randn_like(working) * 0.05

        # Exercise every routed normalization before comparing the full parameter
        # gradient set. A single explicit route legitimately leaves the other
        # route's LayerNorm parameters unused with grad=None.
        native_loss = torch.zeros((), dtype=working.dtype)
        reference_loss = torch.zeros((), dtype=working.dtype)
        for route in range(self.config.modules):
            native_out = native_core(working, context, route_index=route)
            reference_out = _materialized_forward(reference_core, working, context, route)
            self.assertTrue(torch.allclose(native_out, reference_out, rtol=5e-4, atol=1e-4))
            native_loss = native_loss + F.mse_loss(native_out, target)
            reference_loss = reference_loss + F.mse_loss(reference_out, target)

        native_loss.backward()
        reference_loss.backward()

        native_parameters = dict(native_core.named_parameters())
        reference_parameters = dict(reference_core.named_parameters())
        self.assertEqual(set(native_parameters), set(reference_parameters))
        for name in native_parameters:
            left = native_parameters[name].grad
            right = reference_parameters[name].grad
            self.assertIsNotNone(left, name)
            self.assertIsNotNone(right, name)
            self.assertTrue(
                torch.allclose(left, right, rtol=5e-4, atol=1e-5),
                f"gradient mismatch for {name}",
            )

    def test_state_dict_round_trip(self) -> None:
        clone = SharedBasisFixedRoutingCore(self.dense, rank=3)
        clone.load_state_dict(self.core.state_dict(), strict=True)
        working = torch.randn(2, 3, 16) * 0.05
        context = torch.randn_like(working) * 0.05
        for route in range(2):
            expected = self.core(working, context, route_index=route)
            actual = clone(working, context, route_index=route)
            self.assertTrue(torch.equal(expected, actual))

    def test_recurrence_matches_materialized_through_64_updates(self) -> None:
        generator = torch.Generator(device="cpu").manual_seed(999)
        native = self.core.initial_working_state(3)
        reference = native.clone()
        checkpoints = {1, 2, 4, 8, 16, 32, 64}
        for step in range(1, 65):
            context = torch.randn(3, 3, 16, generator=generator) * 0.05
            route = (step - 1) % 2
            native = self.core(native, context, route_index=route)
            reference = _materialized_forward(self.core, reference, context, route)
            if step in checkpoints:
                self.assertTrue(
                    torch.allclose(native, reference, rtol=5e-4, atol=1e-4),
                    f"recurrence mismatch at depth {step}",
                )

    def test_materialized_role_weight_shapes(self) -> None:
        up, down = self.core.materialized_role_weights(0)
        self.assertEqual(tuple(up.shape), (32, 16))
        self.assertEqual(tuple(down.shape), (16, 32))

    def test_invalid_rank_and_source_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SharedBasisFixedRoutingCore(self.dense, rank=0)
        with self.assertRaises(TypeError):
            SharedBasisFixedRoutingCore(object(), rank=3)  # type: ignore[arg-type]

    def test_input_validation_matches_core_contract(self) -> None:
        working = torch.zeros(2, 3, 16)
        context = torch.zeros_like(working)
        with self.assertRaises(ValueError):
            self.core(working, context, route_index=2)
        with self.assertRaises(ValueError):
            self.core(torch.zeros(2, 2, 16), torch.zeros(2, 2, 16), route_index=0)
        with self.assertRaises(TypeError):
            self.core(working.to(torch.int64), context.to(torch.int64), route_index=0)
        bad = context.clone()
        bad[0, 0, 0] = float("nan")
        with self.assertRaises(ValueError):
            self.core(working, bad, route_index=0)


if __name__ == "__main__":
    unittest.main()
