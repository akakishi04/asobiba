"""Offline tests for the local prototype. No external data, API, or GPU needed."""
from __future__ import annotations
import contextlib
from dataclasses import asdict
import io
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import torch
from fold_lm.capsule import compile_capsule
from fold_lm.data import Corpus, prepare, TOKENIZER
from fold_lm.model import BOS, EOS, PAD, FoldLanguageModel, ModelConfig
from fold_lm.runner import (TrainConfig, train, load_checkpoint,
                            evaluate_checkpoint, generate, device_for)


def tiny_config():
    return ModelConfig(width=16, layers=1, heads=2, window=8, chunk=4,
                       capsules=1, latent=6, rank=3, reads=3)


class CapsuleTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        torch.manual_seed(81)
        n, r, q = 7, 3, 2
        A = torch.randn(n, n, dtype=torch.float64)
        self.J = A @ A.T + 2 * torch.eye(n, dtype=torch.float64)
        self.eta = torch.randn(n, dtype=torch.float64)
        self.U = torch.randn(n, r, dtype=torch.float64)
        self.Q = torch.randn(q, n, dtype=torch.float64)

    def test_signed_update_chain_matches_full_system(self):
        cap = compile_capsule(self.J, self.eta, self.Q, self.U)
        W = torch.zeros(3, 3, dtype=torch.float64)
        b = torch.zeros(3, dtype=torch.float64)
        factors = []
        for i in range(30):
            a = torch.randn(3, dtype=torch.float64) / 5
            dW, db = torch.outer(a, a), a * torch.randn((), dtype=torch.float64)
            factors.append((dW, db))
            W, b = W + dW, b + db
            if i % 3 == 2:
                old_W, old_b = factors.pop(0)
                W, b = W - old_W, b - old_b
            expected = self.Q @ torch.linalg.solve(self.J + self.U @ W @ self.U.T,
                                                   self.eta + self.U @ b)
            torch.testing.assert_close(cap.response(W, b), expected, rtol=1e-10, atol=1e-10)

    def test_retract_factor_present_before_compilation(self):
        a = torch.tensor([0.1, 0.2, -0.3], dtype=torch.float64)
        W0, b0 = torch.outer(a, a), a * 2
        cap = compile_capsule(self.J + self.U @ W0 @ self.U.T,
                              self.eta + self.U @ b0, self.Q, self.U)
        torch.testing.assert_close(cap.response(-W0, -b0), self.Q @ torch.linalg.solve(self.J, self.eta))

    def test_unsafe_or_out_of_scope_updates_rejected(self):
        cap = compile_capsule(self.J, self.eta, self.Q, self.U)
        with self.assertRaisesRegex(ValueError, "OUT_OF_SCOPE"):
            cap.response(torch.eye(4), torch.zeros(4))
        with self.assertRaisesRegex(ValueError, "NUMERIC_UNSAFE"):
            cap.response(-1e6 * torch.eye(3, dtype=torch.float64), torch.zeros(3, dtype=torch.float64))
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            cap.response(torch.eye(3, dtype=torch.float64), torch.full((3,), float("nan")))
        with self.assertRaisesRegex(ValueError, "symmetric"):
            cap.response(torch.triu(torch.ones(3, 3, dtype=torch.float64)), torch.zeros(3, dtype=torch.float64))

    def test_compiler_rejects_non_spd_and_dependent_ports(self):
        with self.assertRaises(RuntimeError):
            compile_capsule(-self.J, self.eta, self.Q, self.U)
        with self.assertRaises(RuntimeError):
            compile_capsule(self.J, self.eta, self.Q, torch.zeros_like(self.U))

    def test_autograd_finite_difference(self):
        A = torch.randn(4, 4, dtype=torch.float64, requires_grad=True)
        eta = torch.randn(4, dtype=torch.float64, requires_grad=True)
        U = torch.randn(4, 2, dtype=torch.float64, requires_grad=True)
        Q = torch.randn(2, 4, dtype=torch.float64, requires_grad=True)
        a = torch.randn(2, dtype=torch.float64, requires_grad=True)
        b = torch.randn(2, dtype=torch.float64, requires_grad=True)
        def f(A, eta, U, Q, a, b):
            cap = compile_capsule(A @ A.T + torch.eye(4, dtype=A.dtype), eta, Q, U, check=False)
            return cap.response(a[:, None] * a[None, :], b, check=False)
        self.assertTrue(torch.autograd.gradcheck(f, (A, eta, U, Q, a, b), atol=1e-5, rtol=1e-4))


class ModelTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        torch.manual_seed(13)
        self.model = FoldLanguageModel(tiny_config()).eval()
        self.x = torch.randint(0, 256, (2, 23))

    def test_suffix_cannot_change_prefix_predictions(self):
        alternate = self.x.clone()
        alternate[:, 11:] = (alternate[:, 11:] + 3) % 256
        a, _ = self.model(self.x)
        b, _ = self.model(alternate)
        torch.testing.assert_close(a[:, :11], b[:, :11], atol=1e-6, rtol=1e-6)

    def test_streamed_decode_matches_full_sequence(self):
        with torch.no_grad():
            full, _ = self.model(self.x)
            state, values = None, []
            for part in self.x.split(1, 1):
                logits, state = self.model(part, state)
                values.append(logits)
        torch.testing.assert_close(full, torch.cat(values, 1), atol=2e-6, rtol=2e-6)
        self.assertEqual(state["position"], 23)
        self.assertEqual(state["kv"][0][0].shape[-2], 7)
        self.assertEqual(state["W"].shape, (2, 1, 3, 3))

    def test_gradients_reach_writer_reader_and_compiler(self):
        logits, _ = self.model(self.x)
        torch.nn.functional.cross_entropy(logits.flatten(0, 1), self.x.flatten()).backward()
        for name in ("writer.weight", "reader.weight", "base_A", "base_eta"):
            grad = dict(self.model.named_parameters())[name].grad
            self.assertTrue(torch.isfinite(grad).all(), name)
            self.assertGreater(grad.norm().item(), 0, name)

    def test_memory_ablation_changes_output(self):
        with torch.no_grad():
            expected, _ = self.model(self.x)
            self.model.reader.weight.zero_()
            without, _ = self.model(self.x)
        self.assertGreater((expected - without).abs().max().item(), 1e-8)

    def test_local_only_baseline(self):
        model = FoldLanguageModel(ModelConfig(**(asdict(tiny_config()) | {"memory": False})))
        out, state = model(self.x)
        self.assertEqual(out.shape, (2, 23, 259))
        self.assertNotIn("W", state)

    def test_bad_configuration(self):
        for values in ({"width": 15}, {"chunk": 1000}, {"rank": 100}, {"memory": "false"}):
            with self.assertRaises(ValueError):
                ModelConfig(**(asdict(tiny_config()) | values))


class DataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.raw = self.root / "raw"
        self.raw.mkdir()

    def write(self, path, texts):
        path.write_text("".join(json.dumps({"text": t}, ensure_ascii=False) + "\n" for t in texts), encoding="utf-8")

    def test_dedup_split_and_document_boundaries(self):
        self.write(self.raw / "data.jsonl", [f"文書{i}。hello." for i in range(50)] * 2)
        meta = prepare(self.raw, self.root / "ready")
        self.assertEqual(meta["duplicates_skipped"], 50)
        self.assertEqual(sum(meta["documents"].values()), 50)
        sets = []
        for split in ("train", "val"):
            corpus = Corpus(self.root / "ready", split, 128)
            x, y = corpus.batch(range(len(corpus)))
            self.assertTrue(np.all(x[:, 0] == BOS))
            for row in y:
                live = row[row != -100]
                self.assertEqual(live[-1], EOS)
                self.assertNotIn(BOS, live)
            sets.append({
                bytes(corpus.data[int(row[0]) + 1:int(row[0] + row[1]) - 1].astype(np.uint8))
                for row in corpus.rows
            })
        self.assertFalse(sets[0] & sets[1])

    def test_txt_utf8_and_explicit_validation(self):
        (self.raw / "train.txt").write_text("\ufeff日本語です。\n\n第二文書。\n", encoding="utf-8")
        val = self.root / "val.txt"
        val.write_text("別の文書です。", encoding="utf-8")
        meta = prepare(self.raw, self.root / "ready", val_source=val)
        self.assertEqual(meta["documents"], {"train": 2, "val": 1})
        self.assertEqual(meta["tokenizer"], TOKENIZER)

    def test_cross_split_duplicate_rejected_and_no_partial_output(self):
        self.write(self.raw / "a.jsonl", ["same"])
        val = self.root / "val.jsonl"
        self.write(val, ["same"])
        with self.assertRaisesRegex(ValueError, "BOTH"):
            prepare(self.raw, self.root / "ready", val_source=val)
        self.assertFalse((self.root / "ready").exists())
        self.assertFalse(list(self.root.glob(".prepare-*")))

    def test_bad_json_or_empty_split(self):
        (self.raw / "a.jsonl").write_text('{"other": 1}\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Expected"):
            prepare(self.raw, self.root / "ready")
        self.write(self.raw / "a.jsonl", ["only one document"])
        with self.assertRaisesRegex(ValueError, "nonempty"):
            prepare(self.raw, self.root / "ready")

    def test_prepared_data_not_overwritten_and_corruption_detected(self):
        self.write(self.raw / "a.jsonl", [str(i) for i in range(100)])
        prepare(self.raw, self.root / "ready")
        with self.assertRaises(FileExistsError):
            prepare(self.raw, self.root / "ready")
        with (self.root / "ready/train.bin").open("ab") as f:
            f.write(b"xx")
        with self.assertRaisesRegex(ValueError, "corrupted"):
            Corpus(self.root / "ready", "train", 8)

    def test_long_documents_are_sliced_without_losing_targets(self):
        self.write(self.raw / "a.jsonl", ["abcdefghij"])
        val = self.root / "v.jsonl"
        self.write(val, ["separate validation"])
        prepare(self.raw, self.root / "ready", val_source=val)
        corpus = Corpus(self.root / "ready", "train", 4)
        x, y = corpus.batch(range(len(corpus)))
        expected = [*b"abcdefghij", EOS]
        self.assertEqual(y[y != -100].tolist(), expected)
        self.assertTrue(np.any(x == PAD))


class TrainingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        source, val = self.root / "train.jsonl", self.root / "val.jsonl"
        source.write_text("".join(json.dumps({"text": f"Hello hello hello {i}."}) + "\n" for i in range(20)), encoding="utf-8")
        val.write_text("".join(json.dumps({"text": f"Hello hello hello {i}."}) + "\n" for i in range(20, 25)), encoding="utf-8")
        self.data = self.root / "data"
        prepare(source, self.data, val_source=val)
        self.config = self.root / "config.json"
        config = {"model": asdict(tiny_config()),
                  "train": asdict(TrainConfig(seq_len=24, batch_size=2, max_steps=4,
                    learning_rate=0.005, eval_every=2, eval_batches=2, save_every=2,
                    log_every=2, seed=8, cpu_threads=2))}
        self.config.write_text(json.dumps(config), encoding="utf-8")

    def run_train(self, **kw):
        with contextlib.redirect_stdout(io.StringIO()):
            return train(data=self.data, device_name="cpu", **kw)

    def test_training_resume_matches_uninterrupted_and_generation(self):
        self.run_train(config_path=self.config, out=self.root / "full", max_steps=6)
        self.run_train(config_path=self.config, out=self.root / "split", max_steps=4)
        self.run_train(resume=self.root / "split/last.pt", max_steps=6)
        full, split = (load_checkpoint(self.root / p / "last.pt") for p in ("full", "split"))
        self.assertEqual(split["step"], 6)
        for name in full["model"]:
            torch.testing.assert_close(full["model"][name], split["model"][name], atol=0, rtol=0)
        result = evaluate_checkpoint(self.root / "split/last.pt", self.data, "cpu")
        self.assertTrue(np.isfinite(result["nll"]))
        generated = generate(self.root / "split/last.pt", "Hello", max_new_tokens=8,
                             temperature=0, device_name="cpu")
        self.assertIsInstance(generated, str)
        self.assertFalse((self.root / "split/.training.lock").exists())

    def test_learning_reduces_validation_loss(self):
        self.run_train(config_path=self.config, out=self.root / "run", max_steps=20)
        events = [json.loads(line) for line in (self.root / "run/metrics.jsonl").read_text().splitlines()]
        loss = [e["nll"] for e in events if e["event"] == "validation"]
        self.assertLess(loss[-1], loss[0])

    def test_resume_refuses_wrong_data_and_nonempty_out(self):
        self.run_train(config_path=self.config, out=self.root / "run", max_steps=2)
        with self.assertRaises(FileExistsError):
            self.run_train(config_path=self.config, out=self.root / "run", max_steps=4)
        ckpt = self.root / "run/last.pt"
        with self.assertRaisesRegex(ValueError, "TOTAL"):
            self.run_train(resume=ckpt, max_steps=2)
        with self.assertRaisesRegex(ValueError, "do not also"):
            self.run_train(resume=ckpt, config_path=self.config, max_steps=4)
        with (self.data / "val.bin").open("ab") as f:
            f.write(b"xx")
        with self.assertRaisesRegex(ValueError, "corrupted"):
            self.run_train(resume=ckpt, max_steps=4)

    def test_lock_refuses_concurrent_trainer(self):
        self.run_train(config_path=self.config, out=self.root / "run", max_steps=2)
        lock = self.root / "run/.training.lock"
        lock.write_text("external-owner")
        with self.assertRaises(FileExistsError):
            self.run_train(resume=self.root / "run/last.pt", max_steps=4)
        self.assertEqual(lock.read_text(), "external-owner")

    def test_cuda_not_silently_falls_back(self):
        if not torch.cuda.is_available():
            with self.assertRaisesRegex(ValueError, "unavailable"):
                device_for("cuda")


if __name__ == "__main__":
    unittest.main()
