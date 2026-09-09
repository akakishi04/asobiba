"""Offline UTF-8 data preparation with optional target-only supervision.

Schema 2 stores a contiguous loss-start position per document. Legacy schema 1
(full next-token loss) remains readable so existing prepared data/checkpoints do
not become unusable after adding SFT-style prompt/target records.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import tempfile
import numpy as np

PAD, BOS, EOS = 256, 257, 258
TOKENIZER = {"kind": "utf8-byte-v1", "vocab_size": 259, "pad": PAD, "bos": BOS, "eos": EOS}
CURRENT_SCHEMA = 2


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def json_text(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


@dataclass(frozen=True)
class Document:
    text: str
    target_start_bytes: int | None = None

    @property
    def targeted(self) -> bool:
        return self.target_start_bytes is not None


def documents(root: Path):
    """Yield full-loss text or target-only prompt/target documents.

    JSONL accepts either {"text": str} or {"prompt": str, "target": str}.
    Additional metadata keys are ignored. Supplying both forms, a partial
    prompt/target pair, or an empty target is rejected because supervision would
    otherwise be ambiguous. TXT remains blank-line-separated full-loss text.
    """
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".txt", ".jsonl"}) if root.is_dir() else [root]
    if not files:
        raise ValueError(f"No .txt/.jsonl data in {root}; put your UTF-8 data there first")
    for path in files:
        if path.suffix.lower() not in {".txt", ".jsonl"}:
            raise ValueError(f"Unsupported input: {path}")
        with path.open("r", encoding="utf-8-sig") as f:
            if path.suffix.lower() == ".jsonl":
                for line_no, line in enumerate(f, 1):
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"Invalid JSON at {path}:{line_no}") from exc
                    if not isinstance(obj, dict):
                        raise ValueError(f"Expected a JSON object at {path}:{line_no}")
                    has_text = "text" in obj
                    has_prompt = "prompt" in obj
                    has_target = "target" in obj
                    if has_text and (has_prompt or has_target):
                        raise ValueError(f"Ambiguous supervision at {path}:{line_no}; use text OR prompt+target")
                    if has_prompt != has_target:
                        raise ValueError(f"prompt and target must be supplied together at {path}:{line_no}")
                    if has_text:
                        if not isinstance(obj["text"], str):
                            raise ValueError(f"text must be a string at {path}:{line_no}")
                        yield Document(obj["text"].strip())
                    elif has_prompt:
                        prompt, target = obj["prompt"], obj["target"]
                        if not isinstance(prompt, str) or not isinstance(target, str):
                            raise ValueError(f"prompt and target must be strings at {path}:{line_no}")
                        if not target:
                            raise ValueError(f"target must be nonempty at {path}:{line_no}")
                        yield Document(prompt + target, len(prompt.encode("utf-8")))
                    else:
                        raise ValueError(
                            f"Expected {{\"text\": ...}} or {{\"prompt\": ..., \"target\": ...}} at {path}:{line_no}"
                        )
            else:
                paragraph = []
                for line in f:
                    if line.strip():
                        paragraph.append(line)
                    elif paragraph:
                        yield Document("".join(paragraph).strip())
                        paragraph = []
                if paragraph:
                    yield Document("".join(paragraph).strip())


def prepare(source: Path, output: Path, *, val_source: Path | None = None,
            val_ratio: float = 0.1, seed: int = 20260909) -> dict:
    if not 0 < val_ratio < 1:
        raise ValueError("val_ratio must be between zero and one")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}; choose a NEW --output directory")
    for root in [source] + ([val_source] if val_source else []):
        if not root.exists():
            raise FileNotFoundError(root)
        if root.is_dir() and output.resolve().is_relative_to(root.resolve()):
            raise ValueError("output must be outside the raw input directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".prepare-", dir=output.parent))
    seen, rows = {}, {"train": [], "val": []}
    counts = {"train": 0, "val": 0}
    supervised = {"train": 0, "val": 0}
    kinds = {"train": {"text": 0, "targeted": 0}, "val": {"text": 0, "targeted": 0}}
    duplicates, empty = 0, 0
    handles = {}
    try:
        handles = {s: (stage / f"{s}.bin").open("wb") for s in rows}
        sources = [(source, "train" if val_source else None)]
        if val_source:
            sources.append((val_source, "val"))
        for root, forced in sources:
            for document in documents(root):
                text = document.text
                if not text:
                    empty += 1
                    continue
                raw = text.encode("utf-8")
                if len(raw) > 16 * 1024 * 1024:
                    raise ValueError("Document exceeds 16 MiB; split it into meaningful documents")
                # loss_start is a token index inside [BOS, bytes..., EOS].
                loss_start = 1 if not document.targeted else 1 + document.target_start_bytes
                if not 1 <= loss_start <= len(raw):
                    raise ValueError("Target supervision must start on a nonempty target byte")
                key = hashlib.sha256(raw).hexdigest()
                split_hash = hashlib.sha256(f"{seed}:{key}".encode()).digest()
                fraction = int.from_bytes(split_hash[:8], "big") / 2**64
                split = forced or ("val" if fraction < val_ratio else "train")
                if key in seen:
                    old_split, old_loss_start = seen[key]
                    if old_split != split:
                        raise ValueError("Identical document appears in BOTH train and validation inputs")
                    if old_loss_start != loss_start:
                        raise ValueError("Conflicting supervision for identical document")
                    duplicates += 1
                    continue
                seen[key] = (split, loss_start)
                tokens = np.empty(len(raw) + 2, dtype="<u2")
                tokens[0], tokens[-1] = BOS, EOS
                tokens[1:-1] = np.frombuffer(raw, dtype=np.uint8)
                handles[split].write(tokens.tobytes())
                rows[split].append([counts[split], len(tokens), loss_start])
                counts[split] += len(tokens)
                # target bytes plus EOS are supervised; prompt/BOS are not.
                supervised[split] += len(tokens) - loss_start
                kinds[split]["targeted" if document.targeted else "text"] += 1
        for f in handles.values():
            f.close()
        if not all(rows.values()):
            raise ValueError("Need nonempty train AND validation documents. Add more documents, "
                             "separate TXT paragraphs with blank lines, or use --val-input")
        for split in rows:
            (stage / f"{split}.index.json").write_text(json_text(rows[split]), encoding="utf-8")
        meta = {
            "schema": CURRENT_SCHEMA, "tokenizer": TOKENIZER, "seed": seed,
            "split_mode": "explicit" if val_source else "document-hash",
            "val_ratio": val_ratio, "tokens": counts,
            "supervised_tokens": supervised, "document_kinds": kinds,
            "documents": {s: len(rows[s]) for s in rows},
            "duplicates_skipped": duplicates, "empty_skipped": empty,
            "files": {p.name: digest_file(p) for p in sorted(stage.iterdir())},
        }
        meta["fingerprint"] = hashlib.sha256(json_text(meta).encode()).hexdigest()
        (stage / "manifest.json").write_text(json_text(meta), encoding="utf-8")
        stage.rename(output)
        return meta
    finally:
        for f in handles.values():
            f.close()
        if stage.exists():
            for name in ("train.bin", "val.bin", "train.index.json", "val.index.json", "manifest.json"):
                (stage / name).unlink(missing_ok=True)
            stage.rmdir()


class Corpus:
    def __init__(self, root: Path, split: str, seq_len: int, *, verify: bool = True):
        if split not in {"train", "val"} or seq_len < 2:
            raise ValueError("Invalid split or seq_len")
        self.root, self.seq_len = root, seq_len
        self.manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        meta = dict(self.manifest)
        fingerprint = meta.pop("fingerprint")
        if hashlib.sha256(json_text(meta).encode()).hexdigest() != fingerprint:
            raise ValueError("Corrupted manifest fingerprint")
        schema = meta.get("schema")
        if schema not in {1, CURRENT_SCHEMA} or meta["tokenizer"] != TOKENIZER:
            raise ValueError("Unsupported dataset/tokenizer schema")
        self.schema = schema
        expected_files = {f"{s}{suffix}" for s in ("train", "val") for suffix in (".bin", ".index.json")}
        if set(meta["files"]) != expected_files:
            raise ValueError("Invalid dataset file list")
        if verify:
            for name, expected in meta["files"].items():
                if digest_file(root / name) != expected:
                    raise ValueError(f"Dataset changed/corrupted: {name}; prepare into a new directory")
        self.data = np.memmap(root / f"{split}.bin", dtype="<u2", mode="r")
        self.rows = np.array(json.loads((root / f"{split}.index.json").read_text(encoding="utf-8")), dtype=np.int64)
        expected_columns = 2 if schema == 1 else 3
        if (self.rows.ndim != 2 or self.rows.shape[1] != expected_columns
                or np.any(self.rows[:, 1] < 3)
                or self.rows[0, 0] != 0
                or np.any(self.rows[1:, 0] != np.cumsum(self.rows[:, 1])[:-1])
                or int(self.rows[-1, 0] + self.rows[-1, 1]) != len(self.data)):
            raise ValueError("Invalid document index")
        if schema == CURRENT_SCHEMA:
            loss_start = self.rows[:, 2]
            if np.any(loss_start < 1) or np.any(loss_start > self.rows[:, 1] - 2):
                raise ValueError("Invalid loss_start in document index")
            targeted = loss_start > 1
            # Current trainer resets model state at every sequence block. A targeted
            # document longer than one block would silently discard prompt context.
            if np.any(targeted & (self.rows[:, 1] > seq_len + 1)):
                raise ValueError(
                    "Target-only document exceeds seq_len; increase train.seq_len so prompt+target fit one block"
                )
        chunks = (self.rows[:, 1] - 2) // seq_len + 1
        self.ends = np.cumsum(chunks)

    def __len__(self):
        return int(self.ends[-1])

    def batch(self, indices):
        x = np.full((len(indices), self.seq_len), PAD, dtype=np.int64)
        y = np.full_like(x, -100)
        for i, index in enumerate(indices):
            index = int(index)
            if not 0 <= index < len(self):
                raise IndexError(index)
            doc = int(np.searchsorted(self.ends, index, side="right"))
            block = index - (0 if doc == 0 else int(self.ends[doc - 1]))
            offset, length = self.rows[doc, :2]
            loss_start = 1 if self.schema == 1 else int(self.rows[doc, 2])
            start = int(offset + block * self.seq_len)
            stop = min(start + self.seq_len + 1, int(offset + length))
            values = np.asarray(self.data[start:stop], dtype=np.int64)
            n = len(values) - 1
            x[i, :n] = values[:-1]
            targets = values[1:]
            # targets[j] is the token at absolute document position
            # (start-offset)+j+1. Only positions >= loss_start contribute.
            first = max(0, loss_start - (start - int(offset)) - 1)
            if first < n:
                y[i, first:n] = targets[first:n]
        return x, y
