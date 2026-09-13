"""C57 launcher extending the codebook runtime scale sweep through width 1024.

This keeps the C57 implementation and experiment ID unchanged while extending
its width set from 32..256 to 32..1024.  The fixed tile geometry is intentional:
C57 measures scaling behavior of the same execution family, not per-width
retuning.
"""
from __future__ import annotations

from fold_lm.v05_benchmarks import gate_c_codebook_scale_sweep as benchmark


benchmark.WIDTHS = (32, 64, 128, 256, 512, 1024)


if __name__ == "__main__":
    raise SystemExit(benchmark.main())
