import unittest

import torch

from fold_lm.v05.controller import (
    ActionRouterConfig,
    ControlLaneActionRouter,
    ControlLaneRouterConfig,
    SupervisedActionRouter,
    canonicalize_boolean_channels,
)


class V05ControllerTests(unittest.TestCase):
    def test_default_two_action_contract_is_preserved(self):
        router = SupervisedActionRouter(ActionRouterConfig(width=8))
        working = torch.zeros(4, 1, 8)
        context = torch.zeros_like(working)
        operations = torch.tensor([0, 1, 0, 1], dtype=torch.int64)
        self.assertEqual(router(working, context, operations).shape, (4, 2))

    def test_configurable_five_action_contract(self):
        router = SupervisedActionRouter(ActionRouterConfig(width=8, action_count=5))
        working = torch.zeros(3, 1, 8)
        context = torch.zeros_like(working)
        operations = torch.tensor([0, 1, 0], dtype=torch.int64)
        self.assertEqual(router(working, context, operations).shape, (3, 5))

    def test_invalid_action_count_is_rejected(self):
        with self.assertRaises(ValueError):
            ActionRouterConfig(width=8, action_count=0)

    def test_control_lane_five_action_contract(self):
        router = ControlLaneActionRouter(
            ControlLaneRouterConfig(width=32, control_width=4, hidden_width=4, action_count=5)
        )
        working = torch.zeros(3, 1, 32)
        context = torch.zeros_like(working)
        operations = torch.tensor([0, 1, 0], dtype=torch.int64)
        self.assertEqual(router(working, context, operations).shape, (3, 5))

    def test_control_lane_parameter_count_is_core_width_independent(self):
        small = ControlLaneActionRouter(
            ControlLaneRouterConfig(width=32, control_width=4, hidden_width=4, action_count=5)
        )
        large = ControlLaneActionRouter(
            ControlLaneRouterConfig(width=5120, control_width=4, hidden_width=4, action_count=5)
        )
        small_count = sum(parameter.numel() for parameter in small.parameters())
        large_count = sum(parameter.numel() for parameter in large.parameters())
        self.assertEqual(small_count, large_count)

    def test_invalid_control_lane_width_is_rejected(self):
        with self.assertRaises(ValueError):
            ControlLaneRouterConfig(width=4, control_width=5)

    def test_boolean_canonicalizer_maps_only_selected_signed_channels(self):
        source = torch.tensor([[[9.0, -0.1, 4.0, -3.5, 7.0]]])
        result = canonicalize_boolean_channels(source, (1, 2, 3), threshold=0.0)
        expected = torch.tensor([[[9.0, -1.0, 1.0, -1.0, 7.0]]])
        self.assertTrue(torch.equal(result, expected))
        self.assertTrue(torch.equal(source, torch.tensor([[[9.0, -0.1, 4.0, -3.5, 7.0]]])))

    def test_boolean_canonicalizer_supports_zero_one_schema(self):
        source = torch.tensor([[[0.0, 1.0, 0.0, 1.0]]])
        result = canonicalize_boolean_channels(source, (0, 1, 2, 3), threshold=0.5)
        expected = torch.tensor([[[-1.0, 1.0, -1.0, 1.0]]])
        self.assertTrue(torch.equal(result, expected))

    def test_boolean_canonicalizer_rejects_ambiguous_threshold_value(self):
        source = torch.tensor([[[0.0, 1.0]]])
        with self.assertRaises(ValueError):
            canonicalize_boolean_channels(source, (0,), threshold=0.0)

    def test_boolean_canonicalizer_rejects_invalid_channels(self):
        source = torch.tensor([[[1.0, -1.0]]])
        with self.assertRaises(ValueError):
            canonicalize_boolean_channels(source, (0, 0), threshold=0.0)
        with self.assertRaises(ValueError):
            canonicalize_boolean_channels(source, (2,), threshold=0.0)


if __name__ == "__main__":
    unittest.main()
