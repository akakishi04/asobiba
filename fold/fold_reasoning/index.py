"""Two-view retrieval with bounded LSH probing and an explicit exact baseline.

Signatures are supplied, NOT learned here. Approximate retrieval may miss valid
records; there is no hidden full-scan fallback. Index construction is O(NTd).
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import math
import numpy as np


def unit(values) -> np.ndarray:
    a = np.array(values, dtype=np.float64, copy=True)
    if a.ndim != 1 or not a.size or not np.isfinite(a).all():
        raise ValueError("signature must be a finite, nonempty vector")
    norm = np.linalg.norm(a)
    if not np.isfinite(norm) or norm == 0:
        raise ValueError("signature norm must be finite and positive")
    a /= norm
    a.flags.writeable = False
    return a


@dataclass(frozen=True)
class Record:
    key: str
    domain: str
    schema: str
    structure: tuple[float, ...]
    semantics: tuple[float, ...]
    operations: tuple[str, ...]

    def __post_init__(self):
        for text in (self.key, self.domain, self.schema):
            if not isinstance(text, str) or not text:
                raise ValueError("record identifiers must be nonempty strings")
        object.__setattr__(self, "structure", tuple(float(x) for x in unit(self.structure)))
        object.__setattr__(self, "semantics", tuple(float(x) for x in unit(self.semantics)))
        ops = tuple(self.operations)
        if not ops or any(not isinstance(x, str) or not x for x in ops):
            raise ValueError("record must reference named operations")
        object.__setattr__(self, "operations", ops)


@dataclass(frozen=True)
class Hit:
    record: Record
    score: float
    structural_similarity: float
    semantic_distance: float


class StructuralIndex:
    def __init__(self, records, *, seed=20260909, tables=4, bits=6):
        self.records = tuple(records)
        if not self.records or len({r.key for r in self.records}) != len(self.records):
            raise ValueError("nonempty records with unique keys required")
        if type(tables) is not int or not 1 <= tables <= 32 or type(bits) is not int or not 1 <= bits <= 16:
            raise ValueError("require 1..32 tables and 1..16 bits")
        d, s = len(self.records[0].structure), len(self.records[0].semantics)
        if any(len(r.structure) != d or len(r.semantics) != s for r in self.records):
            raise ValueError("mixed signature dimensions")
        self.structures = np.array([r.structure for r in self.records])
        self.semantics = np.array([r.semantics for r in self.records])
        self.planes = np.random.default_rng(seed).normal(size=(tables, bits, d))
        self.tables = [{} for _ in range(tables)]
        self.bits = bits
        for i, vector in enumerate(self.structures):
            for table, code in zip(self.tables, self._codes(vector)):
                table.setdefault(int(code), []).append(i)
        self.structures.flags.writeable = self.semantics.flags.writeable = False
        payload = [vars(r) for r in self.records]
        self.fingerprint = hashlib.sha256(json.dumps(
            {"records": payload, "seed": seed, "tables": tables, "bits": bits},
            sort_keys=True).encode()).hexdigest()

    def _codes(self, vector):
        return ((self.planes @ vector >= 0) * (1 << np.arange(self.bits))).sum(-1)

    def search(self, structure, semantics, *, schema, k=8, scan_limit=128,
               probes=2, min_structure=0.5, novelty_weight=0.1, exact=False):
        for name, value in (("k", k), ("scan_limit", scan_limit), ("probes", probes)):
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be positive")
        if not math.isfinite(min_structure) or not -1 <= min_structure <= 1:
            raise ValueError("invalid structural threshold")
        if not math.isfinite(novelty_weight) or not 0 <= novelty_weight <= 0.25:
            raise ValueError("novelty_weight must be in [0, .25]")
        x, sem = unit(structure), unit(semantics)
        if x.size != self.structures.shape[1] or sem.size != self.semantics.shape[1]:
            raise ValueError("signature dimensions differ from index")
        visited = 0
        pool, seen = [], set()
        if exact:
            # This explicit oracle ignores scan_limit; cost is reported as N.
            pool = list(range(len(self.records)))
            visited = len(pool)
        else:
            codes = self._codes(x)
            # Probe exact buckets first, then at most bits single-bit neighbors.
            for probe in range(min(probes, self.bits + 1)):
                for table, code in zip(self.tables, codes):
                    bucket = int(code) if probe == 0 else int(code) ^ (1 << (probe - 1))
                    for i in table.get(bucket, ()):
                        if visited >= scan_limit:
                            break
                        visited += 1  # Duplicates cost work too.
                        if i not in seen:
                            seen.add(i)
                            pool.append(i)
                    if visited >= scan_limit:
                        break
                if visited >= scan_limit:
                    break
        hits = []
        if pool:
            sim = self.structures[pool] @ x
            distance = np.clip((1 - self.semantics[pool] @ sem) / 2, 0, 1)
            for i, similarity, gap in zip(pool, sim, distance):
                r = self.records[i]
                # Distance cannot rescue an incompatible or structurally weak hit.
                if r.schema == schema and similarity >= min_structure:
                    hits.append(Hit(r, float(similarity + novelty_weight * gap),
                                    float(similarity), float(gap)))
        hits.sort(key=lambda h: (-h.score, h.record.key))
        return hits[:k], {"mode": "exact" if exact else "bounded_lsh",
                         "bucket_entries_visited": visited,
                         "vectors_scored": len(pool), "records": len(self.records)}

    def numeric_bytes(self):
        """Excludes strings, Python bucket lists/dicts, and object overhead."""
        return self.structures.nbytes + self.semantics.nbytes + self.planes.nbytes
