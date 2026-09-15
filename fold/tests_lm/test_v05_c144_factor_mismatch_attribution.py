from __future__ import annotations

import copy
import unittest

from fold_lm.v05_benchmarks import gate_e_c144_factor_mismatch_attribution as c144


class V05C144FactorMismatchAttributionTests(unittest.TestCase):
    def test_single_factor_masks(self):
        self.assertEqual(c144._mask("red round metal", "blue round metal"), "COLOR")
        self.assertEqual(c144._mask("red round metal", "red square metal"), "SHAPE")
        self.assertEqual(c144._mask("red round metal", "red round wood"), "MATERIAL")

    def test_multi_factor_masks_preserve_axis_order(self):
        self.assertEqual(c144._mask("red round metal", "blue square metal"), "COLOR+SHAPE")
        self.assertEqual(c144._mask("red round metal", "blue round wood"), "COLOR+MATERIAL")
        self.assertEqual(c144._mask("red round metal", "red square wood"), "SHAPE+MATERIAL")
        self.assertEqual(c144._mask("red round metal", "blue square wood"), "COLOR+SHAPE+MATERIAL")

    def test_identical_descriptor_is_not_an_error_mask(self):
        with self.assertRaises(ValueError):
            c144._mask("red round metal", "red round metal")

    def test_bad_descriptor_arity_is_rejected(self):
        with self.assertRaises(ValueError):
            c144._mask("red round", "blue round")

    def test_safe_rate(self):
        self.assertEqual(c144._safe_rate(0, 0), 0.0)
        self.assertEqual(c144._safe_rate(1, 4), 0.25)

    def test_arm_analysis_counts_masks_and_distances(self):
        rows = [
            dict(correct=True, bucket="TRAIN_COMBINATION", expected_descriptor="red round metal",
                 predicted_descriptor="red round metal", text="ruby circular alloy"),
            dict(correct=False, bucket="NEW_COMBINATION", expected_descriptor="red round metal",
                 predicted_descriptor="blue round metal", text="ruby circular alloy"),
            dict(correct=False, bucket="NEW_COMBINATION", expected_descriptor="red round metal",
                 predicted_descriptor="blue square wood", text="crimson curved metallic"),
        ]
        out = c144._arm_analysis(rows)
        self.assertEqual(out["errors"], 2)
        self.assertEqual(out["mismatch_masks"], {"COLOR": 1, "COLOR+SHAPE+MATERIAL": 1})
        self.assertEqual(out["mismatch_distance"], {1: 1, 3: 1})
        self.assertEqual(out["buckets"]["NEW_COMBINATION"]["errors"], 2)

    def test_arm_analysis_tracks_alias_error_rates(self):
        rows = [
            dict(correct=False, bucket="NEW_COMBINATION", expected_descriptor="green round stone",
                 predicted_descriptor="blue round stone", text="emerald curved rocky"),
            dict(correct=True, bucket="NEW_COMBINATION", expected_descriptor="green round stone",
                 predicted_descriptor="green round stone", text="jade curved rocky"),
        ]
        out = c144._arm_analysis(rows)
        self.assertEqual(out["alias_error_rates"]["COLOR"]["emerald"]["error_rate"], 1.0)
        self.assertEqual(out["alias_error_rates"]["COLOR"]["jade"]["error_rate"], 0.0)

    def test_expected_aggregate_constants_match_c143_console(self):
        self.assertEqual(c144.EXPECTED_AGGREGATES["BASELINE"]["all"], (20736, 17178))
        self.assertEqual(c144.EXPECTED_AGGREGATES["COLOR_AUX"]["all"], (20736, 19211))
        self.assertEqual(c144.EXPECTED_PAIRED, {"rescued_errors": 2141, "new_errors": 108})

    def test_axes_are_canonical_order(self):
        self.assertEqual(c144.AXES, ("COLOR", "SHAPE", "MATERIAL"))

    def test_arm_analysis_does_not_mutate_input(self):
        rows = [dict(correct=False, bucket="NEW_COMBINATION", expected_descriptor="red round metal",
                     predicted_descriptor="blue round metal", text="ruby circular alloy")]
        saved = copy.deepcopy(rows)
        c144._arm_analysis(rows)
        self.assertEqual(rows, saved)


if __name__ == "__main__":
    unittest.main()
