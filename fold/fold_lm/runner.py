"""Single-device FP32 training, deterministic sampling, resumable checkpoints."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import platform
import time
import numpy as np
import torch
from torch.nn import functional as F
from .data import Corpus, json_text
from .model import BOS, EOS, PAD, FoldLanguageModel, ModelConfig


@dataclass
class TrainConfig:
    seq_len: int = 256
    batch_size: int = 4
    grad_accum: int = 1
    max_steps: int = 2000
    learning_rate: float = 0.0003
    weight_decay: float = 0.01
    grad_clip: float = 1.0
    eval_every: int = 100
    eval_batches: int = 20
    save_every: int = 100
    log_every: int = 10
    seed: int = 20260909
    cpu_threads: int = 2

    def __post_init__(self):
        for name in ("seq_len", "batch_size", "grad_accum", "max_steps", "eval_every",
                     "save_every", "log_every", "cpu_threads"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"train.{name} must be a positive integer")
        if self.seq_len < 2 or type(self.eval_batches) is not int or self.eval_batches < 0:
            raise ValueError("seq_len >= 2 and eval_batches >= 0 are required")
        if type(self.seed) is not int or not 0 <= self.seed < 2**63:
            raise ValueError("seed must be an integer in [0, 2**63)")
        for name in ("learning_rate", "grad_clip", "weight_decay"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid train.{name}")
        if self.learning_rate == 0 or self.grad_clip == 0:
            raise ValueError("learning_rate and grad_clip must be positive")


def device_for(name: str) -> torch.device:
    if name == "auto":
        name = "cuda" if torch.cuda.is_available() else "cpu"
    if name not in {"cpu", "cuda"}:
        raise ValueError("device must be auto, cpu, or cuda")
    if name == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA requested but unavailable. Check torch installation with doctor, or use --device cpu")
    return torch.device(name)


def load_checkpoint(path: Path) -> dict:
    # No arbitrary Python objects/custom classes are serialized by this project.
    ckpt = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(ckpt, dict) or ckpt.get("format") != "fold-lm-local-v1":
        raise ValueError("Unsupported checkpoint format")
    return ckpt


def atomic_save(payload: dict, path: Path):
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("wb") as f:
            torch.save(payload, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


@torch.inference_mode()
def evaluate_model(model, corpus: Corpus, batch_size: int, max_batches: int, device):
    training = model.training
    model.eval()
    n = min(len(corpus), max_batches * batch_size) if max_batches else len(corpus)
    indices = np.linspace(0, len(corpus) - 1, n, dtype=np.int64)
    total, tokens = 0.0, 0
    try:
        for offset in range(0, n, batch_size):
            x, y = corpus.batch(indices[offset:offset + batch_size])
            logits, _ = model(torch.from_numpy(x).to(device))
            labels = torch.from_numpy(y).to(device)
            loss = F.cross_entropy(logits.flatten(0, 1), labels.flatten(), ignore_index=-100, reduction="sum")
            total += loss.item()
            tokens += int((y != -100).sum())
    finally:
        model.train(training)
    nll = total / tokens
    if not math.isfinite(nll):
        raise ValueError("Nonfinite validation loss")
    return {"nll": nll, "byte_perplexity": math.exp(min(nll, 80)),
            "perplexity_capped": nll > 80, "tokens": tokens, "blocks": n}


def train(*, config_path: Path | None = None, data: Path | None = None,
          out: Path | None = None, resume: Path | None = None,
          max_steps: int | None = None, device_name: str = "auto") -> dict:
    ckpt = load_checkpoint(resume) if resume else None
    if ckpt:
        if config_path:
            raise ValueError("Resume uses checkpoint configuration; do not also pass --config")
        config = ckpt["config"]
    else:
        path = config_path or Path("configs/local-small.json")
        config = json.loads(path.read_text(encoding="utf-8"))
    if set(config) != {"model", "train"}:
        raise ValueError("Config must contain exactly model and train")
    mc, tc = ModelConfig(**config["model"]), TrainConfig(**config["train"])
    if max_steps is not None:
        tc = TrainConfig(**(asdict(tc) | {"max_steps": max_steps}))
    start = ckpt["step"] if ckpt else 0
    if tc.max_steps <= start:
        raise ValueError(f"--max-steps is the TOTAL target and must exceed completed step {start}")
    data = (data or Path(ckpt["data_path"] if ckpt else "data/processed")).resolve()
    out = (out or (resume.parent if resume else Path("runs/first"))).resolve()
    if data == out or out.is_relative_to(data) or data.is_relative_to(out):
        raise ValueError("Data and run directories must be disjoint")
    if out.exists() and any(out.iterdir()):
        if not ckpt or out != resume.parent.resolve():
            raise FileExistsError(f"Run directory is not empty: {out}; choose --out or --resume")
        latest = out / "last.pt"
        if latest.exists() and load_checkpoint(latest)["step"] > start:
            raise ValueError("Refusing to overwrite a newer run with an older checkpoint; choose a new --out")
    train_data = Corpus(data, "train", tc.seq_len)
    val_data = Corpus(data, "val", tc.seq_len, verify=False)
    fingerprint = train_data.manifest["fingerprint"]
    if ckpt and ckpt["data_fingerprint"] != fingerprint:
        raise ValueError("Dataset differs from checkpoint; continuation requires the original prepared dataset")
    device = device_for(device_name)
    torch.set_num_threads(tc.cpu_threads)
    torch.manual_seed(tc.seed)
    sampler = torch.Generator().manual_seed(tc.seed + 1)
    model = FoldLanguageModel(mc).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=tc.learning_rate, weight_decay=tc.weight_decay)
    best = float("inf")
    if ckpt:
        model.load_state_dict(ckpt["model"])
        optimizer.load_state_dict(ckpt["optimizer"])
        torch.set_rng_state(ckpt["torch_rng"])
        sampler.set_state(ckpt["sampler_rng"])
        if device.type == "cuda" and ckpt["cuda_rng"]:
            if len(ckpt["cuda_rng"]) != torch.cuda.device_count():
                raise ValueError("CUDA device count changed; exact RNG restore is unsupported")
            torch.cuda.set_rng_state_all(ckpt["cuda_rng"])
        best = ckpt["best_val"]
    out.mkdir(parents=True, exist_ok=True)
    # Exclusive lock: never let two trainers write the same run concurrently.
    lock = out / ".training.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    actual_config = {"model": asdict(mc), "train": asdict(tc)}
    environment = {"python": platform.python_version(), "torch": str(torch.__version__),
                   "numpy": np.__version__, "platform": platform.platform(), "device": str(device),
                   "cuda_runtime": torch.version.cuda,
                   "gpu": torch.cuda.get_device_name(0) if device.type == "cuda" else None}
    step = start
    last_eval = None
    started = time.perf_counter()

    def emit(event, **fields):
        row = {"event": event, "step": step, **fields}
        line = json.dumps(row, ensure_ascii=False, allow_nan=False)
        with (out / "metrics.jsonl").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(line, flush=True)

    def save(name):
        atomic_save({"format": "fold-lm-local-v1", "step": step,
                     "config": actual_config, "data_path": str(data),
                     "data_fingerprint": fingerprint, "model": model.state_dict(),
                     "optimizer": optimizer.state_dict(), "best_val": best,
                     "torch_rng": torch.get_rng_state(), "sampler_rng": sampler.get_state(),
                     "cuda_rng": torch.cuda.get_rng_state_all() if device.type == "cuda" else [],
                     "environment": environment}, out / name)

    try:
        (out / "config.json").write_text(json_text(actual_config), encoding="utf-8")
        (out / "environment.json").write_text(json_text(environment), encoding="utf-8")
        emit("resume" if ckpt else "start", parameters=sum(p.numel() for p in model.parameters()),
             device=str(device), data_fingerprint=fingerprint, total_steps=tc.max_steps)
        if not ckpt:
            last_eval = evaluate_model(model, val_data, tc.batch_size, tc.eval_batches, device)
            best = last_eval["nll"]
            emit("validation", **last_eval)
            save("best.pt")
            save("last.pt")
        model.train()
        for step in range(start + 1, tc.max_steps + 1):
            micro = [train_data.batch(torch.randint(len(train_data), (tc.batch_size,), generator=sampler).tolist())
                     for _ in range(tc.grad_accum)]
            token_count = sum(int((y != -100).sum()) for _, y in micro)
            optimizer.zero_grad(set_to_none=True)
            loss_sum = 0.0
            for x, y in micro:
                logits, _ = model(torch.from_numpy(x).to(device))
                loss = F.cross_entropy(logits.flatten(0, 1), torch.from_numpy(y).to(device).flatten(),
                                       ignore_index=-100, reduction="sum")
                if not torch.isfinite(loss):
                    raise ValueError("NUMERIC_UNSAFE: nonfinite training loss; last completed checkpoint retained")
                (loss / token_count).backward()
                loss_sum += loss.item()
            grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), tc.grad_clip, error_if_nonfinite=True)
            optimizer.step()
            if step % tc.log_every == 0 or step == tc.max_steps:
                emit("train", nll=loss_sum / token_count, tokens=token_count,
                     grad_norm=float(grad_norm), elapsed_seconds=time.perf_counter() - started)
            if step % tc.eval_every == 0 or step == tc.max_steps:
                last_eval = evaluate_model(model, val_data, tc.batch_size, tc.eval_batches, device)
                emit("validation", **last_eval)
                if last_eval["nll"] < best:
                    best = last_eval["nll"]
                    save("best.pt")
            if step % tc.save_every == 0 or step == tc.max_steps:
                save("last.pt")
        summary = {"step": step, "best_val_nll": best, "validation": last_eval,
                   "device": str(device), "elapsed_seconds": time.perf_counter() - started,
                   "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated() if device.type == "cuda" else None}
        (out / "summary.json").write_text(json_text(summary), encoding="utf-8")
        return summary
    finally:
        lock.unlink(missing_ok=True)
        # A KeyboardInterrupt never saves a potentially half-applied optimizer step.


def evaluate_checkpoint(path: Path, data: Path | None, device_name: str,
                        max_batches: int = 0):
    ckpt = load_checkpoint(path)
    mc, tc = ModelConfig(**ckpt["config"]["model"]), TrainConfig(**ckpt["config"]["train"])
    torch.set_num_threads(tc.cpu_threads)
    corpus = Corpus(data or Path(ckpt["data_path"]), "val", tc.seq_len)
    if corpus.manifest["fingerprint"] != ckpt["data_fingerprint"]:
        raise ValueError("Evaluation dataset differs from training manifest")
    if max_batches < 0:
        raise ValueError("max_batches must be nonnegative")
    device = device_for(device_name)
    model = FoldLanguageModel(mc).to(device)
    model.load_state_dict(ckpt["model"])
    return evaluate_model(model, corpus, tc.batch_size, max_batches, device)


@torch.inference_mode()
def generate(path: Path, prompt: str, *, max_new_tokens: int = 200,
             temperature: float = 0.8, top_k: int = 40, seed: int = 42,
             device_name: str = "auto") -> str:
    if max_new_tokens < 1 or not math.isfinite(temperature) or temperature < 0 or not 0 <= top_k <= 259:
        raise ValueError("Require max_new_tokens > 0, temperature >= 0, and 0 <= top_k <= 259")
    ckpt = load_checkpoint(path)
    torch.set_num_threads(ckpt["config"]["train"]["cpu_threads"])
    device = device_for(device_name)
    model = FoldLanguageModel(ModelConfig(**ckpt["config"]["model"])).to(device).eval()
    model.load_state_dict(ckpt["model"])
    rng = torch.Generator().manual_seed(seed)
    state, logits = None, None
    encoded = [BOS, *prompt.encode("utf-8")]
    # Stream prefill: do not retain logits for the complete prompt.
    for offset in range(0, len(encoded), model.config.chunk):
        tokens = torch.tensor([encoded[offset:offset + model.config.chunk]], device=device)
        logits, state = model(tokens, state)
    output = []
    for _ in range(max_new_tokens):
        scores = logits[0, -1].float().clone()
        scores[PAD] = scores[BOS] = -float("inf")
        if temperature == 0:
            token = int(scores.argmax())
        else:
            scores /= temperature
            if top_k:
                threshold = torch.topk(scores, top_k).values[-1]
                scores[scores < threshold] = -float("inf")
            token = int(torch.multinomial(scores.softmax(-1).cpu(), 1, generator=rng))
        if token == EOS:
            break
        output.append(token)
        logits, state = model(torch.tensor([[token]], device=device), state)
    return bytes(output).decode("utf-8", errors="replace")
