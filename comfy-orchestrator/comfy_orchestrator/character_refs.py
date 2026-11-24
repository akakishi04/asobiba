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


def observation_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            key: {"type": "string", "maxLength": 220}
            for key in FEATURES
        },
        "required": list(FEATURES),
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
    return {
        "type": "object",
        "properties": {
            "common": {"type": "array", "items": shared},
            "candidates": {"type": "array", "items": shared},
            "variable": {"type": "array", "items": difference},
            "uncertain": {"type": "array", "items": difference},
        },
        "required": ["common", "candidates", "variable", "uncertain"],
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
        if not isinstance(obs, dict) or set(obs) != set(FEATURES):
            raise OrchestratorError(f"画像{index}の特徴認識結果が不正です")
        item = {}
        for key, value in obs.items():
            if not isinstance(value, str) or len(value) > 220 or not value.strip():
                raise OrchestratorError(f"画像{index}の{key}の認識結果が不正です")
            item[key] = value.strip()
        clean.append(item)
    if not isinstance(synthesis, dict):
        raise OrchestratorError("統合結果の形式が不正です")
    result = {"observations": clean, "common": [], "candidates": [], "variable": [], "uncertain": []}
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
            if not isinstance(feature, str) or feature not in FEATURES or not isinstance(value, str) or not 0 < len(value.strip()) <= 220:
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
            if not isinstance(feature, str) or feature not in FEATURES or not isinstance(details, str) or not 0 < len(details.strip()) <= 1000:
                raise OrchestratorError("相違点の内容が不正です")
            result[category].append({"feature": feature, "details": details.strip()})
    return result


def suggested_traits(analysis: dict) -> str:
    """Only all-image consensus enters the initial editable character sheet."""
    rows = [
        f"{FEATURES[trait['feature']]}: {trait['value']}"
        for trait in analysis.get("common", [])
    ]
    return "\n".join(rows)


def format_evidence(analysis: dict) -> str:
    size = len(analysis["observations"])
    lines = ["【共通特徴（全画像で確認できた候補）】"]
    for item in analysis["common"]:
        lines.append(f"・{FEATURES[item['feature']]}: {item['value']} ({size}/{size})")
    if not analysis["common"]:
        lines.append("・なし（手動で確定してください）")
    lines.append("\n【部分的に一致・候補】")
    for item in analysis["candidates"]:
        images = ",".join(str(i) for i in item["images"])
        lines.append(
            f"・{FEATURES[item['feature']]}: {item['value']} "
            f"({len(item['images'])}/{size}, 画像{images})"
        )
    if not analysis["candidates"]:
        lines.append("・なし")
    for section, title in (("variable", "画像ごとの差分"), ("uncertain", "不明・矛盾")):
        lines.append(f"\n【{title}】")
        for item in analysis[section]:
            lines.append(f"・{FEATURES[item['feature']]}: {item['details']}")
        if not analysis[section]:
            lines.append("・なし")
    lines.append("\n【画像ごとの観察結果】")
    for index, observed in enumerate(analysis["observations"], 1):
        lines.append(f"画像{index}")
        for key, label in FEATURES.items():
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
        return paths, analysis, approved
    except (ValueError, TypeError, KeyError, OSError, RuntimeError):
        return (), None, ""


def clear_character_sheet(root: Path) -> None:
    (Path(root) / "data" / "character_sheet.json").unlink(missing_ok=True)
