"""Small local-attention LM with a fixed-port, append-only FOLD-R branch.

This is an independent trainable vertical slice, not a learned symbolic
MemoryOp interpreter, dynamic graph compiler, or complete v0.2 implementation.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import torch
from torch import Tensor, nn
from torch.nn import functional as F
from .capsule import compile_capsule

VOCAB_SIZE, PAD, BOS, EOS = 259, 256, 257, 258


@dataclass
class ModelConfig:
    width: int = 128
    layers: int = 2
    heads: int = 4
    window: int = 64
    chunk: int = 32
    ff_mult: int = 2
    capsules: int = 2
    latent: int = 16
    rank: int = 8
    reads: int = 8
    memory: bool = True
    local_control: bool = False

    def __post_init__(self):
        for key, value in vars(self).items():
            if key in {"memory", "local_control"}:
                if type(value) is not bool:
                    raise ValueError(f"model.{key} must be boolean")
            elif type(value) is not int or value < 1:
                raise ValueError(f"model.{key} must be a positive integer")
        if self.memory and self.local_control:
            raise ValueError("memory and local_control are mutually exclusive")
        if self.width % self.heads or self.width % 2:
            raise ValueError("width must be even and divisible by heads")
        if self.window < 2 or self.chunk > self.window:
            raise ValueError("require 2 <= window and chunk <= window")
        if max(self.rank, self.reads) >= self.latent:
            raise ValueError("rank and reads must be smaller than latent")


def memory_parameter_budget(c: ModelConfig) -> int:
    """Trainable parameters used by the FOLD-R branch for this configuration."""
    writer_out = c.capsules * (c.rank + 2)
    return (
        c.capsules * c.latent * c.latent  # base_A
        + c.capsules * c.latent           # base_eta
        + c.width * writer_out + writer_out  # writer weight + bias
        + c.capsules * c.reads * c.width     # reader, bias=False
        + c.width * c.width + c.width         # read_gate weight + bias
    )


class LocalCapacityAdapter(nn.Module):
    """Active token-local control with exactly the FOLD-R branch parameter budget.

    The adapter only transforms each token's already-local representation, so it
    cannot extend the attention receptive field.  Its trainable parameter count
    is constructed to equal ``memory_parameter_budget(config)`` exactly.  This is
    a capacity/parameter-count control, not a compute-matched control.
    """
    def __init__(self, c: ModelConfig):
        super().__init__()
        budget = memory_parameter_budget(c)
        # Two biasless projections plus one hidden gain consume (2*width+1)
        # parameters per bottleneck unit.  At most 2*width parameters remain and
        # are used as active feature-wise input/output gains.
        hidden = budget // (2 * c.width + 1)
        if hidden < 1:
            raise ValueError("memory parameter budget is too small for local_control")
        remainder = budget - hidden * (2 * c.width + 1)
        output_gain = min(remainder, c.width)
        input_gain = remainder - output_gain
        if input_gain > c.width:
            raise AssertionError("local-control parameter packing failed")

        self.input_gain_len = input_gain
        self.output_gain_len = output_gain
        self.in_proj = nn.Linear(c.width, hidden, bias=False)
        self.out_proj = nn.Linear(hidden, c.width, bias=False)
        self.hidden_gain = nn.Parameter(torch.ones(hidden))
        if input_gain:
            self.input_gain = nn.Parameter(torch.ones(input_gain))
        else:
            self.register_parameter("input_gain", None)
        if output_gain:
            self.output_gain = nn.Parameter(torch.ones(output_gain))
        else:
            self.register_parameter("output_gain", None)

        # Start as the plain local-only baseline while retaining trainable extra
        # capacity.  Gradients reach out_proj immediately and the upstream adapter
        # parameters become active once out_proj moves away from zero.
        nn.init.zeros_(self.out_proj.weight)

    def forward(self, x: Tensor) -> Tensor:
        source = x
        if self.input_gain is not None:
            n = self.input_gain_len
            source = torch.cat((source[..., :n] * self.input_gain, source[..., n:]), dim=-1)
        hidden = F.silu(self.in_proj(source)) * self.hidden_gain
        delta = self.out_proj(hidden)
        if self.output_gain is not None:
            n = self.output_gain_len
            delta = torch.cat((delta[..., :n] * self.output_gain, delta[..., n:]), dim=-1)
        return x + delta


class LocalBlock(nn.Module):
    def __init__(self, c: ModelConfig):
        super().__init__()
        self.c = c
        self.norm1, self.norm2 = nn.LayerNorm(c.width), nn.LayerNorm(c.width)
        self.qkv = nn.Linear(c.width, 3 * c.width, bias=False)
        self.attn_out = nn.Linear(c.width, c.width, bias=False)
        self.up = nn.Linear(c.width, 2 * c.ff_mult * c.width, bias=False)
        self.down = nn.Linear(c.ff_mult * c.width, c.width, bias=False)

    def forward(self, x: Tensor, cache=None):
        B, T, D = x.shape
        q, k, v = self.qkv(self.norm1(x)).view(
            B, T, 3, self.c.heads, D // self.c.heads
        ).permute(2, 0, 3, 1, 4).unbind(0)
        past = 0 if cache is None else cache[0].shape[-2]
        if cache is not None:
            k, v = torch.cat((cache[0], k), -2), torch.cat((cache[1], v), -2)
        delta = (torch.arange(T, device=x.device)[:, None] + past
                 - torch.arange(past + T, device=x.device)[None, :])
        allowed = (delta >= 0) & (delta < self.c.window)
        # True in SDPA's boolean mask means allowed. No global T x T mask.
        a = F.scaled_dot_product_attention(q, k, v, attn_mask=allowed, dropout_p=0.0)
        x = x + self.attn_out(a.transpose(1, 2).reshape(B, T, D))
        u, gate = self.up(self.norm2(x)).chunk(2, -1)
        x = x + self.down(u * F.silu(gate))
        keep = self.c.window - 1
        return x, (k[..., -keep:, :].clone(), v[..., -keep:, :].clone())


class FoldLanguageModel(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = c = config
        self.embedding = nn.Embedding(VOCAB_SIZE, c.width)
        nn.init.normal_(self.embedding.weight, std=0.02)
        self.blocks = nn.ModuleList([LocalBlock(c) for _ in range(c.layers)])
        self.norm = nn.LayerNorm(c.width)
        if c.memory:
            # Each learned base J is I+A A.T; Q/U are fixed, nonidentical ports.
            self.base_A = nn.Parameter(torch.randn(c.capsules, c.latent, c.latent) * 0.1)
            self.base_eta = nn.Parameter(torch.zeros(c.capsules, c.latent))
            self.register_buffer("U", torch.eye(c.latent)[:, :c.rank].expand(c.capsules, -1, -1).clone())
            self.register_buffer("Q", torch.eye(c.latent)[-c.reads:].expand(c.capsules, -1, -1).clone())
            self.writer = nn.Linear(c.width, c.capsules * (c.rank + 2))
            self.reader = nn.Linear(c.capsules * c.reads, c.width, bias=False)
            self.read_gate = nn.Linear(c.width, c.width)
        elif c.local_control:
            self.local_control = LocalCapacityAdapter(c)

    def forward(self, tokens: Tensor, state: dict | None = None):
        if tokens.ndim != 2 or tokens.shape[1] == 0:
            raise ValueError("tokens must have nonempty shape [batch, time]")
        c, B = self.config, tokens.shape[0]
        if state is None:
            state = {"position": 0, "kv": [None] * c.layers}
            if c.memory:
                state["W"] = self.embedding.weight.new_zeros(B, c.capsules, c.rank, c.rank)
                state["b"] = self.embedding.weight.new_zeros(B, c.capsules, c.rank)
        kv, position = list(state["kv"]), state["position"]
        if c.memory:
            J = torch.eye(c.latent, device=tokens.device, dtype=self.base_A.dtype) + self.base_A @ self.base_A.mT
            capsule = compile_capsule(J, self.base_eta, self.Q, self.U, check=False)
            W, b = state["W"], state["b"]
        outputs = []
        for part in tokens.split(c.chunk, dim=1):
            T = part.shape[1]
            pos = torch.arange(position, position + T, device=tokens.device, dtype=self.embedding.weight.dtype)
            freq = torch.exp(torch.arange(0, c.width, 2, device=tokens.device,
                                          dtype=pos.dtype) * (-math.log(10000.0) / c.width))
            phase = pos[:, None] * freq[None, :]
            pe = torch.stack((phase.sin(), phase.cos()), -1).flatten(-2)
            h = self.embedding(part) * math.sqrt(c.width) + 0.1 * pe
            for i, block in enumerate(self.blocks):
                h, kv[i] = block(h, kv[i])
            if c.memory:
                op = self.writer(h).view(B, T, c.capsules, c.rank + 2)
                a = torch.tanh(op[..., :c.rank]) / math.sqrt(c.rank)
                weight = torch.sigmoid(op[..., c.rank])
                target = torch.tanh(op[..., c.rank + 1])
                # Inclusive causal prefix: x_t can affect prediction of x_(t+1).
                dW = weight[..., None, None] * a.unsqueeze(-1) * a.unsqueeze(-2)
                db = (weight * target)[..., None] * a
                Ws, bs = W[:, None] + dW.cumsum(1), b[:, None] + db.cumsum(1)
                read = capsule.response(Ws, bs, check=False)
                h = h + torch.sigmoid(self.read_gate(h)) * self.reader(read.flatten(-2))
                W, b = Ws[:, -1].clone(), bs[:, -1].clone()
            elif c.local_control:
                h = self.local_control(h)
            outputs.append(F.linear(self.norm(h), self.embedding.weight))
            position += T
        result = {"position": position, "kv": kv}
        if c.memory:
            result.update(W=W, b=b)
        return torch.cat(outputs, 1), result
