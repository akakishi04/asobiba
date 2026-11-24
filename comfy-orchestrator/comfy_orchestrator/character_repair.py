"""Repair partial VLM output without inventing character identity evidence.

The strict normalizer remains authoritative for persisted/user-approved sheets.
This adapter is only for untrusted, sometimes off-schema LM Studio responses.
Unrecognized fields or corrupted citations are retained as warnings and NEVER
promoted into automatic character traits.
"""

from __future__ import annotations

from .character_refs import (
    CONFIDENCE_LABELS,
    IDENTITY_ASPECTS,
    OBSERVATION_FIELDS,
    normalize_analysis,
)

# Safe, near-equivalent field names commonly emitted by smaller LLMs.
# Ambiguous generic keys (e.g. "hair", "eyes", "style") are intentionally
# omitted: guessing their meaning would turn an unknown field into evidence.
_FIELD_ALIASES = {
    "hair_colour": "hair_color",
    "haircolor": "hair_color",
    "hairstyle": "hair_style",
    "haircut": "hair_style",
    "eyecolor": "eye_color",
    "eye_colour": "eye_color",
    "eye_style": "eye_shape",
    "eye_shape_and_size": "eye_shape",
    "facial_features": "face",
    "facial_structure": "facial_geometry",
    "face_shape": "facial_geometry",
    "body_build": "body",
    "body_shape": "body",
    "clothing": "outfit",
    "clothes": "outfit",
    "costume": "outfit",
    "accessory": "accessories",
    "jewelry": "accessories",
    "jewellery": "accessories",
    "motifs": "distinctive_motifs",
    "distinctive_features": "distinctive_motifs",
    "shape_design": "shape_language",
}
_ASPECT_ALIASES = {
    "facial_geometry": "face",
    "face_shape": "face",
    "hair_style": "hair",
    "hair_color": "hair",
    "eye_shape": "eyes",
    "eye_color": "eyes",
    "body": "silhouette",
    "body_build": "silhouette",
    "shape_language": "design",
    "distinctive_motifs": "design",
    "identity": "overall",
    "character_identity": "overall",
}
MAX_WARNINGS = 60


def _short(value, limit=110) -> str:
    return str(value).replace("\n", " ").replace("\r", " ")[:limit]


def _field(value) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    key = _FIELD_ALIASES.get(normalized, normalized)
    return key if key in OBSERVATION_FIELDS else None


def _indices(value, count) -> list[int] | None:
    """Only unambiguous citations are accepted, never inferred by position."""
    if not isinstance(value, list):
        return None
    ids = []
    for raw in value:
        if type(raw) is int:
            index = raw
        elif (
            isinstance(raw, str)
            and raw.strip().isascii()
            and raw.strip().isdigit()
        ):
            index = int(raw.strip())
        else:
            return None
        if not 1 <= index <= count:
            return None
        if index not in ids:
            ids.append(index)
    return sorted(ids)


def repair_model_analysis(observations: list[dict], synthesis: dict) -> dict:
    """Normalize a best-effort model reply and expose every dropped item.

    Unlike normalize_analysis(), this function tolerates individual LLM
    mistakes, retaining valid records and the original observation report.
    Never silently grants support to a feature with a missing/bad image list.
    """
    from .core import OrchestratorError

    if not isinstance(observations, list) or not isinstance(synthesis, dict):
        raise OrchestratorError("キャラ認識結果がJSONオブジェクトになっていません")
    count = len(observations)
    warnings: list[str] = []

    def warn(msg: str) -> None:
        if len(warnings) < MAX_WARNINGS:
            warnings.append(msg[:450])

    clean_observations = []
    for image_idx, original in enumerate(observations, 1):
        if not isinstance(original, dict):
            raise OrchestratorError(
                f"画像{image_idx}の特徴認識が不正です（オブジェクトではありません）"
            )
        cleaned = {}
        for key in OBSERVATION_FIELDS:
            raw = original.get(key)
            if isinstance(raw, str) and raw.strip():
                if len(raw.strip()) > 220:
                    warn(f"画像{image_idx}: {key} が長すぎるため220文字に縮小")
                cleaned[key] = raw.strip()[:220]
            else:
                cleaned[key] = "unknown"
                if key in original:
                    warn(f"画像{image_idx}: {key} の値が不正なため不明扱い")
        for unknown in set(original) - set(OBSERVATION_FIELDS):
            warn(f"画像{image_idx}: 未認識の観察項目 {_short(unknown)} は除外")
        clean_observations.append(cleaned)

    repaired = {
        "common": [], "candidates": [], "variable": [], "uncertain": [],
        "identity_hypotheses": [],
    }
    for category in ("common", "candidates", "variable", "uncertain"):
        entries = synthesis.get(category, [])
        if not isinstance(entries, list):
            warn(f"{category}: 項目配列が不正なため除外")
            continue
        for position, entry in enumerate(entries[:40], 1):
            loc = f"{category}[{position}]"
            if not isinstance(entry, dict):
                warn(f"{loc}: オブジェクトでないため除外")
                continue
            original_field = entry.get("feature")
            feature = _field(original_field)
            raw_text = entry.get("value") if category in ("common", "candidates") else entry.get("details")
            allowed_length = 220 if category in ("common", "candidates") else 1000
            if feature is None:
                warn(
                    f"{loc}: 未登録の項目名 {_short(original_field)} "
                    f"（内容: {_short(raw_text)}）。自動採用せず要確認"
                )
                continue
            if not isinstance(raw_text, str) or not raw_text.strip():
                warn(f"{loc}: {feature} の内容が空・不正なため除外")
                continue
            if len(raw_text.strip()) > allowed_length:
                warn(f"{loc}: {feature} の内容が長すぎるため短縮")
            clean_text = raw_text.strip()[:allowed_length]
            if (
                category in ("common", "candidates")
                and clean_text.lower().rstrip("。").strip()
                in ("unknown", "不明", "不明瞭", "判断できない", "確認できない")
            ):
                warn(f"{loc}: {feature} は不明情報のため共通特徴へ採用しません")
                continue
            if category in ("common", "candidates"):
                images = _indices(entry.get("images"), count)
                if not images:
                    warn(
                        f"{loc}: {feature} の根拠画像番号が不正"
                        f"（内容: {_short(raw_text)}）。自動採用しません"
                    )
                    continue
                repaired[category].append({
                    "feature": feature, "value": clean_text, "images": images,
                })
            else:
                repaired[category].append({
                    "feature": feature, "details": clean_text,
                })
        if len(entries) > 40:
            warn(f"{category}: 多すぎる候補の残り{len(entries)-40}件は除外")

    hypotheses = synthesis.get("identity_hypotheses", [])
    if not isinstance(hypotheses, list):
        warn("identity_hypotheses: 項目配列が不正なため除外")
        hypotheses = []
    for i, entry in enumerate(hypotheses[:20], 1):
        loc = f"identity_hypotheses[{i}]"
        if not isinstance(entry, dict):
            warn(f"{loc}: 形式不正のため除外")
            continue
        aspect = entry.get("aspect")
        if isinstance(aspect, str):
            aspect = aspect.strip().lower().replace(" ", "_").replace("-", "_")
            aspect = _ASPECT_ALIASES.get(aspect, aspect)
        description = entry.get("description")
        rationale = entry.get("rationale")
        confidence = entry.get("confidence")
        if isinstance(confidence, str):
            confidence = confidence.strip().lower()
        supporting = _indices(entry.get("supporting_images"), count)
        conflicting = _indices(entry.get("conflicting_images"), count)
        if (
            not isinstance(aspect, str) or aspect not in IDENTITY_ASPECTS
            or not isinstance(description, str) or not description.strip()
            or not isinstance(rationale, str) or not rationale.strip()
            or confidence not in CONFIDENCE_LABELS
            or supporting is None or conflicting is None
            or set(supporting) & set(conflicting)
        ):
            warn(
                f"{loc}: {_short(aspect)} / {_short(description)} "
                "の形式または根拠が不正。自動採用せず要確認"
            )
            continue
        repaired["identity_hypotheses"].append({
            "aspect": aspect,
            "description": description.strip()[:350],
            "rationale": rationale.strip()[:400],
            "confidence": confidence,
            "supporting_images": supporting,
            "conflicting_images": conflicting,
        })
    if len(hypotheses) > 20:
        warn(f"identity_hypotheses: 残り{len(hypotheses)-20}件は除外")
    # Existing validator checks support counts, prevents false consensus and
    # preserves the old format for already approved/persisted history.
    analysis = normalize_analysis(clean_observations, repaired)
    analysis["warnings"] = warnings
    return analysis
