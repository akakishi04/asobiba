import unittest

from resource_policy import (
    DutyPacer,
    effective_gpu_duty_percent,
    effective_seedvr2_blocks_to_swap,
    pacing_sleep_seconds,
)
from ai_backends import AIConfig


class ResourcePolicyTests(unittest.TestCase):
    def test_profile_duty_presets(self):
        self.assertEqual(
            effective_gpu_duty_percent(AIConfig(resource_profile="max")), 100
        )
        self.assertEqual(
            effective_gpu_duty_percent(AIConfig(resource_profile="balanced")), 75
        )
        self.assertEqual(
            effective_gpu_duty_percent(AIConfig(resource_profile="background")), 50
        )
        self.assertEqual(
            effective_gpu_duty_percent(
                AIConfig(resource_profile="custom", gpu_duty_cycle_percent=63)
            ),
            63,
        )

    def test_background_profile_reserves_more_seed_vram(self):
        cfg = AIConfig(
            resource_profile="background",
            seedvr2_blocks_to_swap=20,
        )
        self.assertEqual(effective_seedvr2_blocks_to_swap(cfg), 28)

    def test_user_can_request_more_blockswap_than_profile_minimum(self):
        cfg = AIConfig(
            resource_profile="background",
            seedvr2_blocks_to_swap=31,
        )
        self.assertEqual(effective_seedvr2_blocks_to_swap(cfg), 31)

    def test_duty_sleep_math(self):
        self.assertAlmostEqual(pacing_sleep_seconds(10.0, 50), 10.0)
        self.assertAlmostEqual(pacing_sleep_seconds(10.0, 75), 10.0 / 3.0)
        self.assertEqual(pacing_sleep_seconds(10.0, 100), 0.0)


if __name__ == "__main__":
    unittest.main()
