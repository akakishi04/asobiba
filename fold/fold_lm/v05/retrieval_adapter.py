from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from fold_reasoning.index import Record, StructuralIndex


@dataclass(frozen=True)
class RetrievalEvidence:
    key: str
    domain: str
    schema: str
    evidence_value: int
    operations: tuple[str, ...]
    index_fingerprint: str
    source_sha256: str
    source_path: str


class PersistedStructuralRetrievalAdapter:
    """Thin V5-E runtime adapter over the existing StructuralIndex.

    The corpus is loaded from a persisted JSON file. Signatures are supplied by
    the request/corpus contract; this adapter does not learn embeddings or query
    formation. Returned evidence carries corpus and index provenance.
    """

    def __init__(self, path: Path):
        if not isinstance(path, Path):
            raise TypeError("path must be pathlib.Path")
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        if type(payload) is not dict or payload.get("schema_version") != 1:
            raise ValueError("unsupported retrieval corpus schema")
        rows = payload.get("records")
        if type(rows) is not list or not rows:
            raise ValueError("retrieval corpus requires records")

        records = []
        evidence_by_key: dict[str, int] = {}
        for row in rows:
            if type(row) is not dict:
                raise TypeError("retrieval corpus records must be objects")
            expected = {
                "key", "domain", "schema", "structure", "semantics",
                "operations", "evidence_value",
            }
            if set(row) != expected:
                raise ValueError("retrieval corpus record keys are invalid")
            value = row["evidence_value"]
            if type(value) is not int or value not in (0, 1):
                raise ValueError("evidence_value must be boolean-like integer 0/1")
            record = Record(
                key=row["key"],
                domain=row["domain"],
                schema=row["schema"],
                structure=tuple(row["structure"]),
                semantics=tuple(row["semantics"]),
                operations=tuple(row["operations"]),
            )
            if record.key in evidence_by_key:
                raise ValueError("duplicate retrieval corpus key")
            records.append(record)
            evidence_by_key[record.key] = value

        self._path = path.resolve()
        self._source_sha256 = hashlib.sha256(raw).hexdigest()
        self._index = StructuralIndex(records)
        self._evidence_by_key = evidence_by_key

    @property
    def source_sha256(self) -> str:
        return self._source_sha256

    @property
    def index_fingerprint(self) -> str:
        return self._index.fingerprint

    @property
    def record_count(self) -> int:
        return len(self._index.records)

    def retrieve(
        self,
        structure,
        semantics,
        *,
        schema: str,
        exact: bool = True,
        scan_limit: int = 128,
        probes: int = 2,
        min_structure: float = 0.999999,
    ) -> tuple[RetrievalEvidence | None, dict]:
        hits, stats = self._index.search(
            structure,
            semantics,
            schema=schema,
            k=1,
            scan_limit=scan_limit,
            probes=probes,
            min_structure=min_structure,
            exact=exact,
        )
        stats = dict(stats)
        stats["source_sha256"] = self._source_sha256
        stats["index_fingerprint"] = self._index.fingerprint
        if not hits:
            return None, stats
        record = hits[0].record
        evidence = RetrievalEvidence(
            key=record.key,
            domain=record.domain,
            schema=record.schema,
            evidence_value=self._evidence_by_key[record.key],
            operations=record.operations,
            index_fingerprint=self._index.fingerprint,
            source_sha256=self._source_sha256,
            source_path=str(self._path),
        )
        return evidence, stats

    def retrieve_with_exact_recovery(
        self,
        structure,
        semantics,
        *,
        schema: str,
        scan_limit: int = 128,
        probes: int = 2,
        min_structure: float = 0.999999,
    ) -> tuple[RetrievalEvidence | None, dict]:
        """Run bounded retrieval first; exact-search only after a bounded miss.

        A bounded-LSH zero hit is not authoritative evidence of absence. The
        returned trace makes the escalation explicit. A true exact miss remains
        a zero-hit result and must not become evidence.
        """
        bounded_evidence, bounded_stats = self.retrieve(
            structure,
            semantics,
            schema=schema,
            exact=False,
            scan_limit=scan_limit,
            probes=probes,
            min_structure=min_structure,
        )
        if bounded_evidence is not None:
            return bounded_evidence, {
                "bounded": bounded_stats,
                "exact": None,
                "exact_attempted": False,
                "recovered_from_bounded_miss": False,
                "final_mode": "bounded_lsh",
            }

        exact_evidence, exact_stats = self.retrieve(
            structure,
            semantics,
            schema=schema,
            exact=True,
            scan_limit=scan_limit,
            probes=probes,
            min_structure=min_structure,
        )
        return exact_evidence, {
            "bounded": bounded_stats,
            "exact": exact_stats,
            "exact_attempted": True,
            "recovered_from_bounded_miss": exact_evidence is not None,
            "final_mode": "exact" if exact_evidence is not None else "none",
        }
