from __future__ import annotations

import unittest

import torch

from fold_lm.v05.modules import (
    HighPrecisionFixedRoutingCore,
    LearnedCoreConfig,
    SharedBasisFixedRoutingCore,
)


class SharedBasisExecutionModeTests(unittest.TestCase):
    def setUp(self) -> None:
        torch.manual_seed(20260914)
        config = LearnedCoreConfig(width=16, slots=3, modules=2, hidden_mult=2)
        self.dense = HighPrecisionFixedRoutingCore(config)
        self.core = SharedBasisFixedRoutingCore(self.dense, rank=3)

    def test_default_is_gemm_native_and_mode_switch_is_parameter_neutral(self) -> None:
        self.assertEqual(self.core.execution_mode, "gemm_native")
        before = {name: value.detach().clone() for name, value in self.core.state_dict().items()}
        self.core.set_execution_mode("materialized")
        self.assertEqual(self.core.execution_mode, "materialized")
        after = self.core.state_dict()
        self.assertEqual(set(before), set(after))
        for name in before:
            self.assertTrue(torch.equal(before[name], after[name]), name)
        self.core.set_execution_mode("gemm_native")
        self.assertEqual(self.core.execution_mode, "gemm_native")

    def test_invalid_execution_modes_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.core.set_execution_mode("automatic")
        with self.assertRaises(ValueError):
            SharedBasisFixedRoutingCore(self.dense, rank=3, execution_mode="automatic")

    def test_materialized_and_native_share_parameters_but_not_hidden_policy(self) -> None:
        working = torch.randn(4, 3, 16) * 0.05
        context = torch.randn_like(working) * 0.05
        self.core.set_execution_mode("materialized")
        materialized = self.core(working, context, route_index=1)
        state_after_materialized = {
            name: value.detach().clone() for name, value in self.core.state_dict().items()
        }
        self.core.set_execution_mode("gemm_native")
        native = self.core(working, context, route_index=1)
        for name, value in self.core.state_dict().items():
            self.assertTrue(torch.equal(state_after_materialized[name], value), name)
        self.assertTrue(torch.allclose(native, materialized, rtol=5e-4, atol=1e-4))


if __name__ == "__main__":
    unittest.main()
