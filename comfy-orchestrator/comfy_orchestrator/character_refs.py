"""Character identity extraction from 2-4 local reference images.

Every observation is model-estimated. Only user-approved features are allowed
to influence an image-generation request. Reference images never become
ComfyUI image inputs through this module.
"""

from __future__ import annotations

import json
from pathlib import Path

MAX_CHARACTER_IMAGES = 4
MIN_CHARACTER_IMAGES = 2
MAX_APPROVED_CHARS = 3000
FEATURES = {
    "hair_color": "髪色",
    "hair_style": "髪型・前髪",
    "eye_color": "目の色",
    "eye_shape": "目の形",
    "face": "顔の特徴",
    "body": "体格",
    "outfit": "服装",
    "accessories": "装飾品",
    "other": "その他の見た目",
}
# These are observations of character DESIGN, not arbitrary image style.
# Older saved sheets have only FEATURES; the reader accepts both versions.
ABSTRACT_FEATURES = {
    "facial_geometry": "顔の造形・比率",
    "silhouette": "シルエット・形状",
    "shape_language": "デザインの形状的傾向",
    "distinctive_motifs": "識別的な造形・モチーフ",
}
OBSERVATION_FIELDS = {**FEATURES, **ABSTRACT_FEATURES}
IDENTITY_ASPECTS = {
    "face": "顔立ち",
    "hair": "髪の特徴",
    "eyes": "目元",
    "silhouette": "輪郭・体型",
    "design": "デザインの特徴",
    "overall": "総合的なキャラらしさ",
}
CONFIDENCE_LABELS = {"high": "高", "medium": "中", "low": "低"}


def observation_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            key: {"type": "string", "maxLength": 220}
            for key in OBSERVATION_FIELDS
        },
        "required": list(OBSERVATION_FIELDS),
        "additionalProperties": False,
    }


def intersection_schema() -> dict:
    shared = {
        "type": "object",
        "properties": {
            "feature": {"type": "string"},
            "value": {"type": "string"},
            "images": {"type": "array", "items": {"type": "integer"}},
        },
        "required": ["feature", "value", "images"],
        "additionalProperties": False,
    }
    difference = {
        "type": "object",
        "properties": {
            "feature": {"type": "string"},
            "details": {"type": "string"},
        },
        "required": ["feature", "details"],
        "additionalProperties": False,
    }
    identity_hypothesis = {
        "type": "object",
        "properties": {
            "aspect": {"type": "string", "enum": list(IDENTITY_ASPECTS)},
            "description": {"type": "string", "maxLength": 350},
            "supporting_images": {"type": "array", "items": {"type": "integer"}},
            "conflicting_images": {"type": "array", "items": {"type": "integer"}},
            "confidence": {"type": "string", "enum": list(CONFIDENCE_LABELS)},
            "rationale": {"type": "string", "maxLength": 400},
        },
        "required": [
            "aspect", "description", "supporting_images",
            "conflicting_images", "confidence", "rationale",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "common": {"type": "array", "items": shared},
            "candidates": {"type": "array", "items": shared},
            "variable": {"type": "array", "items": difference},
            "uncertain": {"type": "array", "items": difference},
            "identity_hypotheses": {
                "type": "array", "items": identity_hypothesis,
            },
        },
        "required": [
            "common", "candidates", "variable", "uncertain",
            "identity_hypotheses",
        ],
        "additionalProperties": False,
    }


def validate_images(paths) -> tuple[Path, ...]:
    from .core import OrchestratorError

    if not isinstance(paths, (list, tuple)) or not MIN_CHARACTER_IMAGES <= len(paths) <= MAX_CHARACTER_IMAGES:
        raise OrchestratorError("キャラ参照は2～4枚の画像を指定してください")
    valid = []
    for item in paths:
        path = Path(item).expanduser().resolve()
        if path in valid:
            raise OrchestratorError("同じ画像を複数指定できません")
        if not path.is_file() or path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            raise OrchestratorError(f"キャラ参照画像がありません（PNG/JPEG/WebPのみ）: {path}")
        if path.stat().st_size > 20 * 1024 * 1024:
            raise OrchestratorError(f"キャラ参照画像は各20MB以下にしてください: {path.name}")
        valid.append(path)
    return tuple(valid)



def add_character_image_files(
    existing: list[Path] | tuple[Path, ...],
    incoming: list[str] | tuple[str, ...],
) -> tuple[Path, ...]:
    """Validate a drag/drop or file-picker batch, atomically.

    One image is allowed while building a list, but the extraction step still
    requires 2-4 unique images. Any bad file rejects the entire new batch.
    """
    from .core import OrchestratorError

    if not isinstance(existing, (tuple, list)) or not isinstance(incoming, (tuple, list)):
        raise OrchestratorError("画像ファイルの指定が不正です")
    images = [Path(item).expanduser().resolve() for item in existing]
    if len(images) > MAX_CHARACTER_IMAGES:
        raise OrchestratorError("キャラ参照は最大4枚までです")
    if not incoming:
        return tuple(images)
    for item in incoming:
        if not isinstance(item, (str, Path)) or not str(item).strip():
            raise OrchestratorError("ドロップしたファイル名が不正です")
        path = Path(item).expanduser().resolve()
        if path in images:
            continue
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            raise OrchestratorError(f"画像はPNG/JPEG/WebPのみです: {path.name}")
        if not path.is_file():
            raise OrchestratorError(f"画像ファイルがありません: {path}")
        if path.stat().st_size > 20 * 1024 * 1024:
            raise OrchestratorError(f"画像は各20MB以下にしてください: {path.name}")
        if len(images) >= MAX_CHARACTER_IMAGES:
            raise OrchestratorError("キャラ参照は最大4枚までです")
        images.append(path)
    return tuple(images)


def normalize_analysis(observations: list[dict], synthesis: dict) -> dict:
    """Validate evidence IDs and partition all-image vs partial-image support.

    The VLM estimates semantic agreement; human review is still mandatory.
    """
    from .core import OrchestratorError

    count = len(observations)
    if not MIN_CHARACTER_IMAGES <= count <= MAX_CHARACTER_IMAGES:
        raise OrchestratorError("特徴抽出には2～4枚の画像が必要です")
    clean = []
    for index, obs in enumerate(observations, 1):
        if (
            not isinstance(obs, dict)
            or not set(FEATURES).issubset(obs)
            or not set(obs).issubset(OBSERVATION_FIELDS)
        ):
            raise OrchestratorError(f"画像{index}の特徴認識結果が不正です")
        item = {}
        for key in OBSERVATION_FIELDS:
            # Old local sheets lack the four new morphology fields.
            value = obs.get(key, "unknown")
            if not isinstance(value, str) or len(value) > 220 or not value.strip():
                raise OrchestratorError(f"画像{index}の{key}の認識結果が不正です")
            item[key] = value.strip()
        clean.append(item)
    if not isinstance(synthesis, dict):
        raise OrchestratorError("統合結果の形式が不正です")
    result = {
        "observations": clean,
        "common": [], "candidates": [], "variable": [], "uncertain": [],
        "identity_hypotheses": [],
    }
    # A purported common feature must reference ALL inputs; all partial
    # evidence is downgraded to a candidate even if the model mislabels it.
    seen = set()
    for category in ("common", "candidates"):
        entries = synthesis.get(category)
        if not isinstance(entries, list) or len(entries) > 40:
            raise OrchestratorError(f"統合結果の{category}が不正です")
        for entry in entries:
            if not isinstance(entry, dict):
                raise OrchestratorError("共通特徴の根拠が不正です")
            feature, value, support = entry.get("feature"), entry.get("value"), entry.get("images")
            if not isinstance(feature, str) or feature not in OBSERVATION_FIELDS or not isinstance(value, str) or not 0 < len(value.strip()) <= 220:
                raise OrchestratorError("共通特徴の項目または内容が不正です")
            if not isinstance(support, list) or not support or any(
                type(i) is not int or i < 1 or i > count for i in support
            ) or len(set(support)) != len(support):
                raise OrchestratorError("特徴の画像番号が不正です")
            identifier = (feature, value.strip().casefold())
            if identifier in seen:
                continue
            seen.add(identifier)
            actual = "common" if len(support) == count else "candidates"
            result[actual].append({
                "feature": feature, "value": value.strip(),
                "images": sorted(support),
            })
    for category in ("variable", "uncertain"):
        entries = synthesis.get(category)
        if not isinstance(entries, list) or len(entries) > 40:
            raise OrchestratorError(f"統合結果の{category}が不正です")
        for entry in entries:
            if not isinstance(entry, dict):
                raise OrchestratorError("相違点の形式が不正です")
            feature, details = entry.get("feature"), entry.get("details")
            if not isinstance(feature, str) or feature not in OBSERVATION_FIELDS or not isinstance(details, str) or not 0 < len(details.strip()) <= 1000:
                raise OrchestratorError("相違点の内容が不正です")
            result[category].append({"feature": feature, "details": details.strip()})

    # A hypothesis can survive absent views, unlike the exact intersection,
    # but must not hide observations that actively contradict it.
    hypotheses = synthesis.get("identity_hypotheses", [])
    if not isinstance(hypotheses, list) or len(hypotheses) > 20:
        raise OrchestratorError("抽象的キャラ特徴の形式が不正です")
    used_hypotheses = set()

    def image_indices(value):
        if (
            not isinstance(value, list)
            or any(type(i) is not int or not 1 <= i <= count for i in value)
            or len(value) != len(set(value))
        ):
            raise OrchestratorError("キャラ特徴の根拠画像番号が不正です")
        return sorted(value)

    for item in hypotheses:
        if not isinstance(item, dict):
            raise OrchestratorError("抽象的キャラ特徴が不正です")
        aspect = item.get("aspect")
        description = item.get("description")
        rationale = item.get("rationale")
        confidence = item.get("confidence")
        if (
            not isinstance(aspect, str) or aspect not in IDENTITY_ASPECTS
            or not isinstance(description, str)
            or not 0 < len(description.strip()) <= 350
            or not isinstance(rationale, str)
            or not 0 < len(rationale.strip()) <= 400
            or confidence not in CONFIDENCE_LABELS
        ):
            raise OrchestratorError("抽象的キャラ特徴の内容が不正です")
        support = image_indices(item.get("supporting_images"))
        conflict = image_indices(item.get("conflicting_images"))
        if set(support) & set(conflict):
            raise OrchestratorError("同じ画像を根拠と反証の両方には指定できません")
        key = (aspect, description.strip().casefold())
        if key in used_hypotheses:
            continue
        used_hypotheses.add(key)
        # Confidence is claimed by the model, not objectively calibrated.
        # Downgrade statements backed by fewer than two explicit observations.
        if conflict or len(support) < 2:
            confidence = "low"
        result["identity_hypotheses"].append({
            "aspect": aspect,
            "description": description.strip(),
            "supporting_images": support,
            "conflicting_images": conflict,
            "confidence": confidence,
            "rationale": rationale.strip(),
        })
    return result


def suggested_traits(analysis: dict) -> str:
    """Draft an editable identity sheet, not a strict set intersection.

    Prefer non-contradicted medium/high-level design hypotheses backed by
    two or more images. Low-confidence guesses and partial color specifics
    remain in evidence rather than being silently adopted.
    """
    hypotheses = [
        item for item in analysis.get("identity_hypotheses", [])
        if (
            item.get("confidence") in ("medium", "high")
            and len(item.get("supporting_images", [])) >= 2
            and not item.get("conflicting_images")
        )
    ]
    rows = []
    if hypotheses:
        rows.append("【キャラの核（抽象・要確認）】")
        rows.extend(
            f"{IDENTITY_ASPECTS[item['aspect']]}: {item['description']}"
            for item in hypotheses
        )
    common = analysis.get("common", [])
    if common:
        if rows:
            rows.append("")
        rows.append("【具体的な共通特徴】")
        rows.extend(
            f"{OBSERVATION_FIELDS[trait['feature']]}: {trait['value']}"
            for trait in common
        )
    return "\n".join(rows)


def format_evidence(analysis: dict) -> str:
    size = len(analysis["observations"])
    lines = ["【キャラの核：抽象的な特徴の仮説】"]
    hypotheses = analysis.get("identity_hypotheses", [])
    for item in hypotheses:
        supported = ",".join(str(n) for n in item["supporting_images"]) or "なし"
        conflicted = ",".join(str(n) for n in item["conflicting_images"]) or "なし"
        lines.append(
            f"・{IDENTITY_ASPECTS[item['aspect']]}: {item['description']}"
            f" [確信度（推定）: {CONFIDENCE_LABELS[item['confidence']]}, "
            f"支持{len(item['supporting_images'])}/{size} (画像{supported}), "
            f"反証 (画像{conflicted})]"
        )
        lines.append(f"  根拠・変化の説明: {item['rationale']}")
    if not hypotheses:
        lines.append("・推定できた特徴なし（手動確認が必要）")
    lines.append("\n【具体的な共通特徴（全画像で確認できた候補）】")
    for item in analysis["common"]:
        lines.append(f"・{OBSERVATION_FIELDS[item['feature']]}: {item['value']} ({size}/{size})")
    if not analysis["common"]:
        lines.append("・なし（手動で確定してください）")
    lines.append("\n【部分的に一致・候補】")
    for item in analysis["candidates"]:
        images = ",".join(str(i) for i in item["images"])
        lines.append(
            f"・{OBSERVATION_FIELDS[item['feature']]}: {item['value']} "
            f"({len(item['images'])}/{size}, 画像{images})"
        )
    if not analysis["candidates"]:
        lines.append("・なし")
    for section, title in (("variable", "画像ごとの差分"), ("uncertain", "不明・矛盾")):
        lines.append(f"\n【{title}】")
        for item in analysis[section]:
            lines.append(f"・{OBSERVATION_FIELDS[item['feature']]}: {item['details']}")
        if not analysis[section]:
            lines.append("・なし")
    lines.append("\n【画像ごとの観察結果】")
    for index, observed in enumerate(analysis["observations"], 1):
        lines.append(f"画像{index}")
        for key, label in OBSERVATION_FIELDS.items():
            value = observed.get(key, "unknown")
            if value and value.strip().lower() != "unknown":
                lines.append(f"  {label}: {value}")
    return "\n".join(lines)


def normalize_approved(text: str) -> str:
    from .core import OrchestratorError

    if not isinstance(text, str):
        raise OrchestratorError("確定キャラ特徴は文章で指定してください")
    clean = text.strip()
    if not clean or len(clean) > MAX_APPROVED_CHARS:
        raise OrchestratorError("確定キャラ特徴は1～3000文字で入力してください")
    return clean



def save_character_sheet(
    root: Path, images: tuple[Path, ...], analysis: dict, approved: str,
) -> None:
    """Persist the last explicitly approved sheet locally (not in git)."""
    from .core import OrchestratorError

    paths = validate_images(images)
    clean = normalize_approved(approved)
    if not isinstance(analysis, dict):
        raise OrchestratorError("キャラ特徴の根拠がありません")
    analysis = normalize_analysis(analysis.get("observations", []), analysis)
    file = Path(root) / "data" / "character_sheet.json"
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps({
            "version": 1,
            "images": [str(path) for path in paths],
            "analysis": analysis,
            "approved_traits": clean,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(file)
    finally:
        tmp.unlink(missing_ok=True)


def load_character_sheet(root: Path) -> tuple[tuple[Path, ...], dict | None, str]:
    """Return empty state if old local images have moved or data is malformed."""
    file = Path(root) / "data" / "character_sheet.json"
    if not file.is_file() or file.stat().st_size > 1_000_000:
        return (), None, ""
    try:
        value = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("version") != 1:
            raise ValueError("unexpected version")
        paths = validate_images(value["images"])
        analysis = value["analysis"]
        approved = normalize_approved(value["approved_traits"])
        if not isinstance(analysis, dict):
            raise ValueError("invalid analysis")
        analysis = normalize_analysis(analysis.get("observations", []), analysis)
        return paths, analysis, approved
    except (ValueError, TypeError, KeyError, OSError, RuntimeError):
        return (), None, ""


def clear_character_sheet(root: Path) -> None:
    (Path(root) / "data" / "character_sheet.json").unlink(missing_ok=True)
