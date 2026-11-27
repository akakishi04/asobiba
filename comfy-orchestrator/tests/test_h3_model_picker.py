"""Short model names and conditioning modes must preserve exact loader identities."""
import unittest

from comfy_orchestrator import h3
from comfy_orchestrator.h3_model_picker import (
    model_choices, select_model_key, OPENING, REFERENCE, TEXT_ONLY, REQUIRED_REFERENCE,
)


LEARNED = "10Eros_Max_8stepTurbo_v1.0_hybrid_activation_learned_HQ.safetensors"
COMPACT = "10Eros_Max_8stepTurbo_v1.0_hybrid_activation_learned_compact_w4w6int8_14.50gb.safetensors"


def key(filename, reference=False):
    return h3.h3_hybrid_model_key(filename, reference_only=reference)


class ModelPickerTests(unittest.TestCase):
    def test_hybrid_is_one_weight_with_distinct_modes(self):
        models = model_choices([key(LEARNED), key(LEARNED, True), key(COMPACT), key(COMPACT, True)], key(LEARNED))
        self.assertEqual([m.label for m in models], ["10Eros Max · Learned HQ", "10Eros Max · Compact 14.5GB"])
        choice = models[0]
        self.assertEqual(choice.mode_options(has_image=True), (OPENING, REFERENCE))
        self.assertEqual(choice.key_for_mode(OPENING), key(LEARNED))
        self.assertEqual(choice.key_for_mode(REFERENCE), key(LEARNED, True))
        self.assertEqual(choice.display_mode(key(LEARNED, True), has_image=False), TEXT_ONLY)
        self.assertEqual(choice.key_for_mode(TEXT_ONLY), key(LEARNED))

    def test_reference_only_model_has_no_text_mode(self):
        ref = h3.h3_ref2va_model_key("s3_ref2va_w4a8.safetensors")
        model = model_choices([ref], ref)[0]
        self.assertEqual(model.label, "S3 W4A8 · Ref2VA")
        self.assertEqual(model.mode_options(has_image=False), (REQUIRED_REFERENCE,))
        self.assertEqual(model.mode_options(has_image=True), (REFERENCE,))
        self.assertIsNone(model.key_for_mode(TEXT_ONLY))

    def test_removing_an_installed_weight_does_not_substitute_it(self):
        current = key(LEARNED, True)
        models = model_choices(["int8"], current)
        self.assertEqual(len(models), 2)
        self.assertEqual(select_model_key(models[1], current, has_image=False), current)

    def test_subfolders_disambiguate_identical_basenames(self):
        a = key("folder-a/" + LEARNED)
        b = key("folder-b/" + LEARNED)
        models = model_choices([a, b], a)
        self.assertEqual(len({item.label for item in models}), 2)
        self.assertEqual({item.opening for item in models}, {a, b})
        self.assertTrue(any("folder-a/" in item.label for item in models))

    def test_selection_preserves_reference_preference_only_where_supported(self):
        ref = h3.h3_ref2va_model_key("s3_ref2va_w4a8.safetensors")
        model = model_choices([key(LEARNED)], key(LEARNED))[0]
        self.assertEqual(select_model_key(model, ref, has_image=True), key(LEARNED, True))
        self.assertEqual(select_model_key(model, ref, has_image=False), key(LEARNED))
        base = model_choices(["int8"], "int8")[0]
        self.assertEqual(select_model_key(base, ref, has_image=True), "int8")

    def test_legacy_labels_and_loader_identity_are_unchanged(self):
        for value in ("int8", key(LEARNED), key(LEARNED, True)):
            self.assertEqual(h3.h3_model_from_label(h3.h3_model_label(value)), value)


if __name__ == "__main__":
    unittest.main()
