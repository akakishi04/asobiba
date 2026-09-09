"""Offline UTF-8 data preparation; document splits precede sequence slicing."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import tempfile
import numpy as np

PAD, BOS, EOS = 256, 257, 258
TOKENIZER = {"kind": "utf8-byte-v1", "vocab_size": 259, "pad": PAD, "bos": BOS, "eos": EOS}


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def json_text(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def documents(root: Path):
    """JSONL: one {text: str} per line. TXT: blank-line-separated documents."""
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
                    if not isinstance(obj, dict) or not isinstance(obj.get("text"), str):
                        raise ValueError(f"Expected {{\"text\": \"...\"}} at {path}:{line_no}")
                    yield obj["text"].strip()
            else:
                paragraph = []
                for line in f:
                    if line.strip():
                        paragraph.append(line)
                    elif paragraph:
                        yield "".join(paragraph).strip()
                        paragraph = []
                if paragraph:
                    yield "".join(paragraph).strip()


def prepare(source: Path, output: Path, *, val_source: Path | None = None,
            val_ratio: float = 0.1, seed: int = 20260909) -> dict:
    if not 0 < val_ratio < 1:
        raise ValueError("val_ratio must be between zero and one")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}; choose a NEW --output directory")
    # Never discover our own output during recursive source traversal.
    for root in [source] + ([val_source] if val_source else []):
        if not root.exists():
            raise FileNotFoundError(root)
        if root.is_dir() and output.resolve().is_relative_to(root.resolve()):
            raise ValueError("output must be outside the raw input directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".prepare-", dir=output.parent))
    seen, rows = {}, {"train": [], "val": []}
    counts, duplicates, empty = {"train": 0, "val": 0}, 0, 0
    handles = {}
    try:
        handles = {s: (stage / f"{s}.bin").open("wb") for s in rows}
        sources = [(source, "train" if val_source else None)]
        if val_source:
            sources.append((val_source, "val"))
        for root, forced in sources:
            for text in documents(root):
                if not text:
                    empty += 1
                    continue
                raw = text.encode("utf-8")
                if len(raw) > 16 * 1024 * 1024:
                    raise ValueError("Document exceeds 16 MiB; split it into meaningful documents")
                key = hashlib.sha256(raw).hexdigest()
                split_hash = hashlib.sha256(f"{seed}:{key}".encode()).digest()
                fraction = int.from_bytes(split_hash[:8], "big") / 2**64
                split = forced or ("val" if fraction < val_ratio else "train")
                if key in seen:
                    if seen[key] != split:
                        raise ValueError("Identical document appears in BOTH train and validation inputs")
                    duplicates += 1
                    continue
                seen[key] = split
                tokens = np.empty(len(raw) + 2, dtype="<u2")
                tokens[0], tokens[-1] = BOS, EOS
                tokens[1:-1] = np.frombuffer(raw, dtype=np.uint8)
                handles[split].write(tokens.tobytes())
                rows[split].append([counts[split], len(tokens)])
                counts[split] += len(tokens)
        for f in handles.values():
            f.close()
        if not all(rows.values()):
            raise ValueError("Need nonempty train AND validation documents. Add more documents, "
                             "separate TXT paragraphs with blank lines, or use --val-input")
        for split in rows:
            (stage / f"{split}.index.json").write_text(json_text(rows[split]), encoding="utf-8")
        meta = {
            "schema": 1, "tokenizer": TOKENIZER, "seed": seed,
            "split_mode": "explicit" if val_source else "document-hash",
            "val_ratio": val_ratio, "tokens": counts,
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
            # Remove only our five known files; never recursively delete a tree.
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
        if meta["schema"] != 1 or meta["tokenizer"] != TOKENIZER:
            raise ValueError("Unsupported dataset/tokenizer schema")
        expected_files = {f"{s}{suffix}" for s in ("train", "val") for suffix in (".bin", ".index.json")}
        if set(meta["files"]) != expected_files:
            raise ValueError("Invalid dataset file list")
        if verify:
            for name, expected in meta["files"].items():
                if digest_file(root / name) != expected:
                    raise ValueError(f"Dataset changed/corrupted: {name}; prepare into a new directory")
        self.data = np.memmap(root / f"{split}.bin", dtype="<u2", mode="r")
        self.rows = np.array(json.loads((root / f"{split}.index.json").read_text(encoding="utf-8")), dtype=np.int64)
        if (self.rows.ndim != 2 or self.rows.shape[1] != 2
                or np.any(self.rows[:, 1] < 3)
                or self.rows[0, 0] != 0
                or np.any(self.rows[1:, 0] != np.cumsum(self.rows[:, 1])[:-1])
                or int(self.rows[-1].sum()) != len(self.data)):
            raise ValueError("Invalid document index")
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
            offset, length = self.rows[doc]
            start = int(offset + block * self.seq_len)
            stop = min(start + self.seq_len + 1, int(offset + length))
            values = np.asarray(self.data[start:stop], dtype=np.int64)
            n = len(values) - 1
            x[i, :n], y[i, :n] = values[:-1], values[1:]
        return x, y
