"""Small offline learned necessity probe, not the FOLD core or a live action policy.

Only canonical C170 numeric task fields are consumed. Binding IDs, semantic-group
IDs, expected actions, completion values and proof-checker outputs are not inputs.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib

import torch
from torch import nn

from . import structured_task_input as task

ARMS = ("TASK_VISIBLE", "SYNTAX_ABLATED")
LABELS = ("SUFFICIENT", "NEEDS_OBSERVATION")
HIDDEN = 128
TRAIN_STEPS, BATCH_SIZE, LEARNING_RATE = 2000, 256, 0.001
SEEDS = (174001, 174002, 174003)
# Fixed schema-based scaling; no statistics estimated from evaluation inputs.
SCALES = (7, 4, 1, 1) + (1, 3, 4, 7, 7, 1)*7 + (1, 8, 1, 1)*4 + (12, 4, 1, 1, 1, 1, 1, 1, 6, 7)


def packet_values(packet: task.PolicyInput) -> tuple[int, ...]:
    task.decode(packet)  # Strict canonical/schema validation; no logic evaluation.
    return packet.features


def prepare(features: torch.Tensor, arm: str) -> torch.Tensor:
    if arm not in ARMS:
        raise ValueError("Explicit registered arm required")
    if (features.ndim != 2 or features.shape[1] != 72 or features.dtype != torch.int32
            or features.device.type != "cpu" or (features < 0).any().item()):
        raise ValueError("CPU int32 matrix of canonical C170 fields required")
    x = features.to(torch.float32) / torch.tensor(SCALES, dtype=torch.float32)
    if arm == "SYNTAX_ABLATED":
        x[:, 4:46] = 0  # Only the ordered AST is withheld; facts/resources stay equal.
    return x


class NecessityProbe(nn.Module):
    input_schema = task.SCHEMA

    def __init__(self):
        super().__init__()
        self.layers = nn.Sequential(nn.Linear(72, HIDDEN, dtype=torch.float32), nn.ReLU(),
            nn.Linear(HIDDEN, HIDDEN, dtype=torch.float32), nn.ReLU(), nn.Linear(HIDDEN, 2, dtype=torch.float32))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim != 2 or x.shape[1] != 72 or x.dtype != torch.float32:
            raise ValueError("Expected batch of 72 float32 scaled features")
        return self.layers(x)


def fingerprint(model: nn.Module) -> str:
    h = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        h.update(name.encode()); h.update(str(tuple(tensor.shape)).encode())
        h.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def fit(initial: NecessityProbe, x_train: torch.Tensor, y_train: torch.Tensor, seed: int,
        *, steps: int = TRAIN_STEPS, batch_size: int = BATCH_SIZE, progress=None):
    """No evaluation tensors, labels, metrics or checkpoint selection in this API.

    The formal benchmark uses only registered defaults. Tiny unit-test calls are
    explicitly development checks and are not a deciding experiment.
    """
    if (type(initial) is not NecessityProbe or x_train.ndim != 2 or x_train.shape[1] != 72
            or x_train.dtype != torch.float32 or x_train.device.type != "cpu"
            or y_train.shape != (len(x_train),) or y_train.dtype != torch.int64
            or y_train.device.type != "cpu" or len(x_train) < 2
            or not torch.isfinite(x_train).all().item()
            or set(y_train.tolist()) != {0, 1}
            or type(steps) is not int or steps < 1
            or type(batch_size) is not int or batch_size < 1):
        raise ValueError("Finite train-only inputs and positive fixed workload required")
    model = deepcopy(initial).cpu().train()
    optim = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE,
        betas=(0.9, 0.999), eps=1e-8, weight_decay=0, amsgrad=False, foreach=False)
    loss_fn = nn.CrossEntropyLoss()
    batches = torch.Generator(device="cpu").manual_seed(seed + 1000000)
    schedule = hashlib.sha256(); log = []
    for index in range(steps):
        ids = torch.randint(len(x_train), (batch_size,), generator=batches)
        schedule.update(ids.numpy().tobytes())
        optim.zero_grad(set_to_none=True)
        logits = model(x_train[ids]); loss = loss_fn(logits, y_train[ids])
        if not torch.isfinite(loss).item():
            raise FloatingPointError("Nonfinite training loss; no automatic retuning")
        loss.backward()
        if any(not torch.isfinite(p.grad).all().item() for p in model.parameters()):
            raise FloatingPointError("Nonfinite gradient")
        optim.step()
        if (index+1) % 500 == 0 or index+1 == steps:
            row = dict(step=index+1, training_loss=float(loss.detach()))
            log.append(row)
            if progress is not None:
                progress(row)
    if any(not torch.isfinite(p).all().item() for p in model.parameters()):
        raise FloatingPointError("Nonfinite trained weights")
    return model.eval(), dict(steps=steps, examples_drawn=steps*batch_size,
        batch_schedule_sha256=schedule.hexdigest(), training_log=log)


def predict(model: NecessityProbe, x: torch.Tensor, *, batch_size: int = 1024):
    """Raw two-class argmax; no semantic checker, labels, fallback or action mask."""
    if type(batch_size) is not int or batch_size < 1 or not len(x):
        raise ValueError("Nonempty evaluation and positive batching required")
    before = fingerprint(model); model.eval()
    outputs = []
    with torch.inference_mode():
        for start in range(0, len(x), batch_size):
            outputs.append(model(x[start:start+batch_size]).cpu())
    logits = torch.cat(outputs)
    if not torch.isfinite(logits).all().item() or fingerprint(model) != before:
        raise FloatingPointError("Invalid or mutating inference")
    return logits.argmax(1), logits
