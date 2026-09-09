"""Demonstrate published components, not the full search scheduler."""
import json
import torch
from .index import Record, StructuralIndex
from fold_lm.capsule import compile_capsule


def main():
    records = [Record("factory", "manufacturing", "chain", (1, 0), (1, 0), ("shift",)),
               Record("rhythm", "music", "chain", (1, 0), (0, 1), ("shift",))]
    hits, stats = StructuralIndex(records).search((1, 0), (1, 0), schema="chain")
    J = torch.tensor([[2., -1.], [-1., 1.]], dtype=torch.float64)
    eta = torch.tensor([0., 1.], dtype=torch.float64)
    Q = torch.tensor([[0., 1.]], dtype=torch.float64)
    U = torch.tensor([[1.], [0.]], dtype=torch.float64)
    cap = compile_capsule(J, eta, Q, U)
    W = torch.zeros(2, 1, 1, dtype=torch.float64)
    b = torch.tensor([[0.], [1.]], dtype=torch.float64)
    print(json.dumps({"kind": "supplied-signature-component-demo", "learned_reasoning": False,
                      "retrieved": [h.record.key for h in hits], "index": stats,
                      "batched_read_values": cap.response(W, b).tolist()}, indent=2))


if __name__ == "__main__":
    main()
