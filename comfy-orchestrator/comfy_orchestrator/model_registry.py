"""Local, explicit registrations for existing model adapters.

The typed selection keys are self-contained: old history and queued jobs keep
the exact loader filename and adapter even after a registry entry is removed.
Neither LLM output nor a filename heuristic can create a manual registration.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from .parameters import OrchestratorError, check_param


@dataclass(frozen=True)
class Profile:
    label: str
    loader: str
    image_family: str | None = None
    h3_modes: tuple[str, ...] = ()
    fixed_steps: int | None = None
    fixed_cfg: float | None = None
    default_steps: int = 20


PROFILES = {
    "sdxl": Profile("Illustrious互換 SDXL", "CheckpointLoaderSimple", "sdxl", default_steps=28),
    "sdxl_turbo": Profile("SDXL Turbo (4 steps)", "CheckpointLoaderSimple", "sdxl", fixed_steps=4, fixed_cfg=1),
    "anima": Profile("Anima", "UNETLoader", "anima", default_steps=28),
    "qwen": Profile("Qwen-Image 2512互換", "UNETLoader", "qwen", default_steps=50),
    "h3_fl2va": Profile("H3 FL2VA / T2VA", "UNETLoader", h3_modes=("opening",)),
    "h3_ref2va": Profile("H3 Ref2VA", "UNETLoader", h3_modes=("reference",)),
    "h3_euler_fl2va": Profile("H3 Turbo内蔵 Euler 8step / FL2VA", "UNETLoader",
                              h3_modes=("opening",), fixed_steps=8),
    "h3_euler_ref2va": Profile("H3 Turbo内蔵 Euler 8step / Ref2VA", "UNETLoader",
                               h3_modes=("reference",), fixed_steps=8),
    "h3_euler_hybrid": Profile("H3 Turbo内蔵 Euler 8step / Hybrid", "UNETLoader",
                               h3_modes=("opening", "reference"), fixed_steps=8),
}
MAX_REGISTRATIONS = 512
IMAGE_PREFIX = "registered_image:"
H3_PREFIX = "registered_h3:"


def safe_filename(value):
    if not isinstance(value, str) or not value or len(value) > 1024:
        return False
    parts = value.replace("\\", "/").split("/")
    return (value.lower().endswith(".safetensors")
            and all(p and p not in (".", "..") and p == p.rstrip(" .")
                    and not any(c in ':<>|?*"' or ord(c) < 32 or ord(c) == 127 for c in p)
                    for p in parts))


def image_key(profile, filename):
    spec = PROFILES.get(profile) if isinstance(profile, str) else None
    if spec is None or spec.image_family is None or not safe_filename(filename):
        return None
    return IMAGE_PREFIX + profile + ":" + filename


def parse_image_key(value):
    if not isinstance(value, str) or not value.startswith(IMAGE_PREFIX):
        return None
    parts = value.split(":", 2)
    if len(parts) != 3:
        return None
    _, profile, filename = parts
    return (profile, filename) if image_key(profile, filename) == value else None


def h3_key(profile, mode, filename):
    spec = PROFILES.get(profile) if isinstance(profile, str) else None
    if spec is None or mode not in spec.h3_modes or not safe_filename(filename):
        return None
    return H3_PREFIX + profile + ":" + mode + ":" + filename


def parse_h3_key(value):
    if not isinstance(value, str) or not value.startswith(H3_PREFIX):
        return None
    parts = value.split(":", 3)
    if len(parts) != 4:
        return None
    _, profile, mode, filename = parts
    return (profile, mode, filename) if h3_key(profile, mode, filename) == value else None


def registered_h3_turbo(value):
    parsed = parse_h3_key(value)
    return bool(parsed and PROFILES[parsed[0]].fixed_steps == 8)


def registered_h3_label(value):
    parsed = parse_h3_key(value)
    if parsed is None:
        return None
    profile, mode, filename = parsed
    label = PROFILES[profile].label
    return "登録 · " + label + (" · 開始" if mode == "opening" else " · 参考") + " · " + filename


def h3_key_from_label(label):
    if not isinstance(label, str):
        return None
    for profile, spec in PROFILES.items():
        for mode in spec.h3_modes:
            prefix = "登録 · " + spec.label + (" · 開始" if mode == "opening" else " · 参考") + " · "
            if label.startswith(prefix):
                return h3_key(profile, mode, label[len(prefix):])
    return None


def model_filename(value):
    image = parse_image_key(value)
    if image:
        return image[1]
    h3 = parse_h3_key(value)
    return h3[2] if h3 else value


def model_display(value):
    return str(model_filename(value)) + (" [登録]" if parse_image_key(value) else "")


@dataclass(frozen=True)
class Registration:
    profile: str
    filename: str
    steps: int | None = None
    cfg: float | None = None

    @property
    def spec(self):
        return PROFILES[self.profile]

    @property
    def identity(self):
        return self.spec.loader, self.filename

    @property
    def keys(self):
        if self.spec.image_family:
            return (image_key(self.profile, self.filename),)
        return tuple(h3_key(self.profile, mode, self.filename) for mode in self.spec.h3_modes)


def registration(profile, filename, steps=None, cfg=None):
    spec = PROFILES.get(profile) if isinstance(profile, str) else None
    if spec is None or not safe_filename(filename):
        raise OrchestratorError("登録するモデル系列またはファイル名が不正です")
    if steps is not None:
        check_param("steps", steps)
        if spec.fixed_steps is not None and steps != spec.fixed_steps:
            raise OrchestratorError(f"この系列は {spec.fixed_steps} Steps 固定です")
    if cfg is not None:
        if not spec.image_family:
            raise OrchestratorError("H3にCFGは指定できません")
        check_param("cfg", cfg)
        if spec.fixed_cfg is not None and cfg != spec.fixed_cfg:
            raise OrchestratorError(f"この系列は CFG {spec.fixed_cfg} 固定です")
    return Registration(profile, filename, steps, cfg)


def validate_registrations(values):
    if not isinstance(values, (list, tuple)) or len(values) > MAX_REGISTRATIONS:
        raise OrchestratorError("モデル登録一覧が不正です")
    result, seen = [], set()
    for value in values:
        if isinstance(value, Registration):
            value = asdict(value)
        if (not isinstance(value, dict) or not {"profile", "filename"} <= value.keys()
                or not value.keys() <= {"profile", "filename", "steps", "cfg"}):
            raise OrchestratorError("モデル登録項目が不正です")
        item = registration(**value)
        if item.identity in seen:
            raise OrchestratorError("同じローダー・ファイルが重複登録されています")
        seen.add(item.identity)
        result.append(item)
    return tuple(result)


def load_registrations(path):
    path = Path(path)
    if not path.exists():
        return ()
    if path.stat().st_size > 2 * 1024 * 1024:
        raise OrchestratorError("モデル登録ファイルが大きすぎます")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OrchestratorError("モデル登録ファイルを読み込めません") from exc
    if (not isinstance(payload, dict) or set(payload) != {"version", "models"}
            or type(payload["version"]) is not int or payload["version"] != 1):
        raise OrchestratorError("モデル登録ファイルの形式が不正です")
    return validate_registrations(payload["models"])


def save_registrations(path, values):
    checked = validate_registrations(values)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                prefix=".models-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({"version": 1, "models": [asdict(item) for item in checked]},
                      stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return checked


def installed_registrations(inventory, values):
    if inventory is None:
        return tuple(values)
    return tuple(item for item in values if item.filename in inventory.get(item.spec.loader, ()))


def registration_for_key(values, key):
    return next((item for item in values if key in item.keys), None)


def recommended(values, key, defaults):
    result = dict(defaults)
    item = registration_for_key(values, key)
    if item:
        if item.steps is not None:
            result["steps"] = item.steps
        elif item.spec.fixed_steps is not None:
            result["steps"] = item.spec.fixed_steps
        if item.cfg is not None:
            result["cfg"] = item.cfg
        elif item.spec.fixed_cfg is not None:
            result["cfg"] = item.spec.fixed_cfg
    return result
