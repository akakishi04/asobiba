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
    ) -> tuple[RetrievalEvidence | None, dict]:
        hits, stats = self._index.search(
            structure,
            semantics,
            schema=schema,
            k=1,
            min_structure=0.999999,
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
