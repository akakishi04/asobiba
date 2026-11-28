"""Load/migrate and validate local settings without depending on Tk."""
from __future__ import annotations

import copy
import json
import shutil

from .configuration import load_config
from .h3_prompt import FORMAT as H3_OFFICIAL_FORMAT
from .prompt_profiles import DEFAULT_T2I_PROFILE, DEFAULT_I2I_PROFILE, DEFAULT_H3_PROFILE


def load_local_config(config_path, example_path) -> dict:
    """Create the local settings file only if missing, preserving custom settings."""
    if not config_path.exists():
        shutil.copyfile(example_path, config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    example = json.loads(example_path.read_text(encoding="utf-8"))
    if "llm" not in config:
        config["llm"] = copy.deepcopy(example["llm"])
    config["llm"]["provider"] = "lmstudio"
    # Backfill the new inference-only timeout without changing the user's
    # chosen model, endpoint, token limit, or older API-management timeout.
    config["llm"].setdefault(
        "inference_timeout_seconds", example["llm"]["inference_timeout_seconds"]
    )
    config["llm"].setdefault("image_reasoning", "off")
    config["llm"].setdefault("send_reference_to_llm", False)
    config["llm"].setdefault("t2i_prompt_profile", DEFAULT_T2I_PROFILE)
    config["llm"].setdefault("i2i_prompt_profile", DEFAULT_I2I_PROFILE)
    config["llm"].setdefault("h3_prompt_profile", DEFAULT_H3_PROFILE)
    config["llm"].setdefault("h3_prompt_format", H3_OFFICIAL_FORMAT)
    config["llm"].setdefault("h3_reference_vision", True)
    config.setdefault("workflows", {})
    for workflow_id, entry in example.get("workflows", {}).items():
        config["workflows"].setdefault(workflow_id, copy.deepcopy(entry))
    config.setdefault("ui", copy.deepcopy(example.get("ui", {})))
    # One-time migration from the original 4096/2048 token presets.
    # Keep unrelated settings (including the user's chosen model and port).
    # A marker prevents a deliberate future choice of smaller limits from
    # being silently overwritten on the next startup.
    ui = config["ui"]
    # One-time upgrade of the previous stock 10-minute timeout. Preserve
    # custom values and allow deliberate changes back to 600 after migration.
    if not ui.get("inference_timeout_v2_applied", False):
        if config["llm"].get("inference_timeout_seconds") == 600:
            config["llm"]["inference_timeout_seconds"] = example["llm"]["inference_timeout_seconds"]
        ui["inference_timeout_v2_applied"] = True
    if not ui.get("token_defaults_v2_applied", False):
        llm = config["llm"]
        defaults = example["llm"]
        if llm.get("context_length") == 4096:
            llm["context_length"] = defaults["context_length"]
        if llm.get("max_tokens", 2048) == 2048:
            llm["max_tokens"] = defaults["max_tokens"]
        ui["token_defaults_v2_applied"] = True
    return config


def write_local_config(path, config):
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    load_config(temporary)
    temporary.replace(path)
