"""Tests for the active parameter-matched local-only control."""
from __future__ import annotations

from dataclasses import asdict
import unittest

import torch

from fold_lm.model import FoldLanguageModel, ModelConfig, memory_parameter_budget


def tiny_config(**changes):
    values = asdict(ModelConfig(
        width=16,
        layers=1,
        heads=2,
        window=8,
        chunk=4,
        ff_mult=2,
        capsules=1,
        latent=6,
        rank=3,
        reads=3,
        memory=True,
    ))
    values.update(changes)
    return ModelConfig(**values)


class ParameterMatchedControlTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        torch.manual_seed(20260910)

    def test_control_parameter_count_exactly_matches_memory_model(self):
        for base in (
            tiny_config(),
            ModelConfig(
                width=128, layers=2, heads=4, window=64, chunk=32,
                ff_mult=2, capsules=2, latent=16, rank=8, reads=8,
                memory=True,
            ),
        ):
            memory_model = FoldLanguageModel(base)
            control = FoldLanguageModel(ModelConfig(**(
                asdict(base) | {"memory": False, "local_control": True}
            )))
            memory_parameters = sum(p.numel() for p in memory_model.parameters())
            control_parameters = sum(p.numel() for p in control.parameters())
            self.assertEqual(memory_parameters, control_parameters)

            plain = FoldLanguageModel(ModelConfig(**(
                asdict(base) | {"memory": False, "local_control": False}
            )))
            plain_parameters = sum(p.numel() for p in plain.parameters())
            self.assertEqual(
                control_parameters - plain_parameters,
                memory_parameter_budget(base),
            )

    def test_control_has_no_long_range_state_and_preserves_local_causality(self):
        config = tiny_config(memory=False, local_control=True)
        model = FoldLanguageModel(config).eval()
        x = torch.randint(0, 256, (2, 23))
        alternate = x.clone()
        alternate[:, 11:] = (alternate[:, 11:] + 17) % 256

        with torch.no_grad():
            original, state = model(x)
            changed, _ = model(alternate)

        torch.testing.assert_close(original[:, :11], changed[:, :11], atol=1e-6, rtol=1e-6)
        self.assertNotIn("W", state)
        self.assertNotIn("b", state)
        self.assertEqual(state["kv"][0][0].shape[-2], config.window - 1)

    def test_control_parameters_are_trainable_and_affect_output(self):
        config = tiny_config(memory=False, local_control=True)
        model = FoldLanguageModel(config)
        x = torch.randint(0, 256, (2, 12))

        # out_proj starts at zero so the control begins as the plain local model.
        logits, _ = model(x)
        logits.square().mean().backward()
        grad = model.local_control.out_proj.weight.grad
        self.assertIsNotNone(grad)
        self.assertTrue(torch.isfinite(grad).all())
        self.assertGreater(grad.norm().item(), 0.0)

        before = logits.detach()
        with torch.no_grad():
            model.local_control.out_proj.weight.add_(0.01)
            after, _ = model(x)
        self.assertGreater((before - after).abs().max().item(), 1e-8)

    def test_memory_and_local_control_are_mutually_exclusive(self):
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            tiny_config(memory=True, local_control=True)
        with self.assertRaisesRegex(ValueError, "boolean"):
            tiny_config(memory=False, local_control="true")


if __name__ == "__main__":
    unittest.main()
