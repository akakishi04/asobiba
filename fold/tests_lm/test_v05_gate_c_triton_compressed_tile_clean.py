from __future__ import annotations

import copy
import unittest

import torch

from fold_lm.v05_benchmarks.gate_c_triton_compressed_tile_clean import (
    DEFAULT_ROWS, DEFAULT_WIDTH, TILES, VARIANTS, make_diagnostic_bank,
    order_for_round, summarize_records, validate_scope,
)


def sample_records():
    records = []
    for role in ("up", "down"):
        for module, tile32 in ((0, 4.0), (1, 2.0)):
            for variant, device in (("dense", 1.0), ("ieee_16x16x32", 8.0),
                                    ("ieee_32x32x32", tile32)):
                records.append({"rows": 216, "role": role, "module_index": module, "round": 0,
                                "variant": variant, "device_per_forward_ms": device,
                                "wall_per_forward_ms": device*2})
    return records


def summary(records):
    return summarize_records(records, row_counts=(216,), rounds=1, module_count=2)


class V05GateCCompressedTileCleanTests(unittest.TestCase):
    def test_scope_and_variants_are_bounded(self):
        self.assertEqual(DEFAULT_WIDTH, 256)
        self.assertEqual(DEFAULT_ROWS, (1, 216))
        self.assertEqual(TILES, {"ieee_16x16x32": (16, 16, 32), "ieee_32x32x32": (32, 32, 32)})
        self.assertEqual(VARIANTS, ("dense", *TILES))
        with self.assertRaises(ValueError):
            make_diagnostic_bank(None, "tf32")

    def test_orders_are_balanced_over_three_rounds(self):
        orders = [order_for_round(r) for r in range(3)]
        for column in zip(*orders):
            self.assertEqual(set(column), set(VARIANTS))
        self.assertEqual(order_for_round(3), VARIANTS)
        for invalid in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                order_for_round(invalid)

    def test_invalid_scope_is_rejected_before_cuda(self):
        validate_scope(256, (1, 216), 0, 9, 100)
        for scope in ((255, (1,), 0, 1, 1), (256, (), 0, 1, 1),
                      (256, (1, 1), 0, 1, 1), (256, (True,), 0, 1, 1),
                      (256, (1,), -1, 1, 1), (256, (1,), 0, 0, 1)):
            with self.assertRaises(ValueError):
                validate_scope(*scope)

    def test_both_modules_contribute_and_module_zero_is_not_overwritten(self):
        records = sample_records()
        point = summary(records)["points"]["r216_up"]
        self.assertEqual(point["paired_samples"], 2)
        self.assertEqual(point["paired_ratios"]["ieee_32x32x32_vs_dense_device"]["median"], 3.0)
        self.assertEqual(point["paired_ratios"]["tile16_to_tile32_speedup_wall"]["median"], 3.0)
        for row in records:
            if row["module_index"] == 0 and row["variant"] == "ieee_32x32x32":
                row["device_per_forward_ms"] = 400.0
        altered = summary(records)["points"]["r216_up"]
        self.assertEqual(altered["paired_ratios"]["ieee_32x32x32_vs_dense_device"]["median"], 201.0)

    def test_complete_missing_module_and_missing_variant_are_rejected(self):
        records = sample_records()
        with self.assertRaises(ValueError):
            summary([row for row in records if row["module_index"] != 0])
        with self.assertRaises(ValueError):
            summary(records[:-1])
        with self.assertRaises(ValueError):
            summary([])

    def test_duplicates_and_unknown_variants_are_rejected(self):
        records = sample_records()
        with self.assertRaises(ValueError):
            summary(records + [copy.deepcopy(records[0])])
        records[0]["variant"] = "other"
        with self.assertRaises(ValueError):
            summary(records)

    def test_nonfinite_or_nonpositive_timings_are_rejected(self):
        for value in (0, -1, float("nan"), float("inf"), True):
            records = sample_records()
            records[0]["device_per_forward_ms"] = value
            with self.assertRaises(ValueError):
                summary(records)

    def test_out_of_scope_or_noninteger_indices_are_rejected(self):
        for name, value in (("module_index", 2), ("round", 1), ("rows", 32),
                            ("role", "bad"), ("module_index", 0.5), ("round", True)):
            records = sample_records()
            records[0][name] = value
            with self.assertRaises(ValueError):
                summary(records)

    def test_input_order_does_not_change_summary(self):
        records = sample_records()
        self.assertEqual(summary(records), summary(list(reversed(records))))

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA required")
    def test_tiles_match_dense_preserve_buffers_and_have_no_detected_sync(self):
        from fold_lm.v05 import triton_tiled_runtime as runtime
        from fold_lm.v05_benchmarks.gate_c_triton_width_scale import build_synthetic_initialization
        from fold_lm.v05_benchmarks.gate_c_triton_correction_ablation import without_correction
        if not runtime.triton_runtime_available():
            self.skipTest("Triton required")
        old_precision = torch.get_float32_matmul_precision()
        torch.set_float32_matmul_precision("highest")
        try:
            # Tail masking and both target width-256 roles.
            with torch.inference_mode():
                for k, m in ((34, 66), (256, 512), (512, 256)):
                    init = without_correction(build_synthetic_initialization(k, m))
                    baseline = runtime.TiledNoECompressedLinearBank(init).cuda()
                    banks = [make_diagnostic_bank(init, name).cuda() for name in TILES]
                    for bank in banks:
                        self.assertEqual(bank.resident_tensor_bytes, baseline.resident_tensor_bytes)
                        for name, buffer in baseline.named_buffers():
                            self.assertTrue(torch.equal(buffer, dict(bank.named_buffers())[name]))
                    for module, encoded in enumerate(init.encoded_weights):
                        weight = torch.tensor(encoded.materialize().copy(), dtype=torch.float32, device="cuda")
                        for n in (1, 33, 216):
                            x = torch.randn(n, k, device="cuda")
                            ref = torch.nn.functional.linear(x, weight)
                            for bank in banks:
                                out = bank(x, module_index=module)
                                torch.cuda.synchronize()
                                torch.testing.assert_close(out, ref, rtol=1e-4, atol=1e-5)
                                old_sync = torch.cuda.get_sync_debug_mode()
                                try:
                                    torch.cuda.set_sync_debug_mode("error")
                                    out = bank(x, module_index=module)
                                finally:
                                    torch.cuda.set_sync_debug_mode(old_sync)
                                torch.cuda.synchronize()
                                torch.testing.assert_close(out, ref, rtol=1e-4, atol=1e-5)
        finally:
            torch.set_float32_matmul_precision(old_precision)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA required")
    def test_nonzero_e_and_invalid_activations_are_rejected(self):
        from fold_lm.v05 import triton_tiled_runtime as runtime
        from fold_lm.v05_benchmarks.gate_c_triton_width_scale import build_synthetic_initialization
        from fold_lm.v05_benchmarks.gate_c_triton_correction_ablation import without_correction
        if not runtime.triton_runtime_available():
            self.skipTest("Triton required")
        full = build_synthetic_initialization(32, 64)
        with self.assertRaises(ValueError):
            make_diagnostic_bank(full, "ieee_32x32x32")
        bank = make_diagnostic_bank(without_correction(full), "ieee_32x32x32").cuda()
        with self.assertRaises(ValueError):
            bank(torch.randn(1, 32, device="cuda"), module_index=2)
        with self.assertRaises(TypeError):
            bank(torch.ones(1, 32, device="cuda", dtype=torch.float16), module_index=0)
        with self.assertRaises(ValueError):
            bank(torch.randn(1, 30, device="cuda"), module_index=0)
        with self.assertRaises(RuntimeError):
            bank(torch.randn(1, 32), module_index=0)


if __name__ == "__main__":
    unittest.main()
