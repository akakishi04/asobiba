"""Target-only supervision tests. No network, external data, or GPU required."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from fold_lm.data import BOS, EOS, Corpus, TOKENIZER, digest_file, json_text, prepare


class SftDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write_jsonl(self, path, rows):
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    def test_prompt_is_masked_target_and_eos_are_supervised(self):
        train, val = self.root / "train.jsonl", self.root / "val.jsonl"
        self.write_jsonl(train, [{"prompt": "Question? Answer: ", "target": "Alice."}])
        self.write_jsonl(val, [{"prompt": "Other? Answer: ", "target": "Bob."}])
        meta = prepare(train, self.root / "ready", val_source=val)
        self.assertEqual(meta["schema"], 2)
        self.assertEqual(meta["document_kinds"]["train"], {"text": 0, "targeted": 1})
        corpus = Corpus(self.root / "ready", "train", 64)
        x, y = corpus.batch([0])
        live = y[0][y[0] != -100].tolist()
        self.assertEqual(live, [*b"Alice.", EOS])
        self.assertEqual(int((y[0] != -100).sum()), len(b"Alice.") + 1)
        # The prompt remains model input, even though it is excluded from loss.
        prompt = b"Question? Answer: "
        self.assertEqual(x[0, 0], BOS)
        self.assertEqual(bytes(x[0, 1:1 + len(prompt)].astype(np.uint8)), prompt)

    def test_text_records_keep_full_next_token_loss(self):
        train, val = self.root / "train.jsonl", self.root / "val.jsonl"
        self.write_jsonl(train, [{"text": "abc"}])
        self.write_jsonl(val, [{"text": "xyz"}])
        prepare(train, self.root / "ready", val_source=val)
        corpus = Corpus(self.root / "ready", "train", 16)
        _, y = corpus.batch([0])
        self.assertEqual(y[0][y[0] != -100].tolist(), [*b"abc", EOS])

    def test_extra_metadata_is_allowed_but_ambiguous_forms_are_rejected(self):
        val = self.root / "val.jsonl"
        self.write_jsonl(val, [{"prompt": "v", "target": "x", "id": 3}])
        good = self.root / "good.jsonl"
        self.write_jsonl(good, [{"prompt": "p", "target": "t", "id": 2, "source": "unit"}])
        prepare(good, self.root / "ready", val_source=val)
        bad_cases = [
            {"text": "x", "prompt": "p", "target": "t"},
            {"prompt": "p"},
            {"target": "t"},
            {"prompt": "p", "target": ""},
            {"other": 1},
        ]
        for i, row in enumerate(bad_cases):
            path = self.root / f"bad-{i}.jsonl"
            self.write_jsonl(path, [row])
            with self.subTest(row=row), self.assertRaises(ValueError):
                prepare(path, self.root / f"bad-ready-{i}", val_source=val)

    def test_cross_split_duplicate_detected_regardless_of_supervision_mode(self):
        train, val = self.root / "train.jsonl", self.root / "val.jsonl"
        self.write_jsonl(train, [{"prompt": "same", "target": " text"}])
        self.write_jsonl(val, [{"text": "same text"}])
        with self.assertRaisesRegex(ValueError, "BOTH"):
            prepare(train, self.root / "ready", val_source=val)

    def test_conflicting_supervision_in_one_split_is_rejected(self):
        source, val = self.root / "train.jsonl", self.root / "val.jsonl"
        self.write_jsonl(source, [
            {"text": "same text"},
            {"prompt": "same", "target": " text"},
        ])
        self.write_jsonl(val, [{"text": "different"}])
        with self.assertRaisesRegex(ValueError, "Conflicting supervision"):
            prepare(source, self.root / "ready", val_source=val)

    def test_targeted_document_must_fit_single_training_block(self):
        train, val = self.root / "train.jsonl", self.root / "val.jsonl"
        self.write_jsonl(train, [{"prompt": "p" * 20, "target": "answer"}])
        self.write_jsonl(val, [{"prompt": "q", "target": "z"}])
        prepare(train, self.root / "ready", val_source=val)
        with self.assertRaisesRegex(ValueError, "exceeds seq_len"):
            Corpus(self.root / "ready", "train", 8)
        # Increasing seq_len makes the same prepared data valid.
        corpus = Corpus(self.root / "ready", "train", 64)
        _, y = corpus.batch([0])
        self.assertEqual(y[0][y[0] != -100].tolist(), [*b"answer", EOS])

    def test_schema1_legacy_dataset_still_loads_as_full_loss(self):
        ready = self.root / "legacy"
        ready.mkdir()
        payloads = {"train": b"abc", "val": b"xyz"}
        files = {}
        for split, raw in payloads.items():
            tokens = np.array([BOS, *raw, EOS], dtype="<u2")
            (ready / f"{split}.bin").write_bytes(tokens.tobytes())
            (ready / f"{split}.index.json").write_text(json_text([[0, len(tokens)]]), encoding="utf-8")
        for path in sorted(p for p in ready.iterdir() if p.name != "manifest.json"):
            files[path.name] = digest_file(path)
        meta = {
            "schema": 1, "tokenizer": TOKENIZER, "seed": 1,
            "split_mode": "explicit", "val_ratio": 0.1,
            "tokens": {"train": 5, "val": 5},
            "documents": {"train": 1, "val": 1},
            "duplicates_skipped": 0, "empty_skipped": 0,
            "files": files,
        }
        meta["fingerprint"] = hashlib.sha256(json_text(meta).encode()).hexdigest()
        (ready / "manifest.json").write_text(json_text(meta), encoding="utf-8")
        corpus = Corpus(ready, "train", 8)
        self.assertEqual(corpus.schema, 1)
        _, y = corpus.batch([0])
        self.assertEqual(y[0][y[0] != -100].tolist(), [*b"abc", EOS])


if __name__ == "__main__":
    unittest.main()
