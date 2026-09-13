import unittest

import torch

from fold_lm.v05.controller import ActionRouterConfig, SupervisedActionRouter


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


if __name__ == "__main__":
    unittest.main()
