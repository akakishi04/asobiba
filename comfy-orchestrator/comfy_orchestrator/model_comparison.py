"""One interpretation, independent sequential T2I jobs, and durable comparison groups."""
from __future__ import annotations

import copy
import json
import re
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from . import image_prompts, camera_spec
from .generation_runtime import build_template, preflight, check_cancel
from .input_snapshot import copy_frozen_asset
from .model_profiles import ANIMA_ID, WAI_ID, QWEN_ID, QWEN_FAST_ID, defaults_for
from .parameters import OrchestratorError, check_param
from .workflow_registry import sdxl_checkpoint_kind, split_checkpoint_option
from .comfy_client import ComfyUI

COMPARISON_IDS = frozenset({WAI_ID, ANIMA_ID, QWEN_ID, QWEN_FAST_ID})
MAX_MODELS = 4
POLICIES = {"recommended": "モデル推奨値", "common": "Steps・CFG共通"}
MAX_GROUPS = 50


def valid_group_id(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value) is not None


def prepare_targets(workflows, choices, registrations, *, width, height, seed,
                    policy="recommended", steps=None, cfg=None, camera=None):
    """Keep geometry/seed shared, reject incompatible fixed sampler settings."""
    choices = tuple(choices)
    if not 2 <= len(choices) <= MAX_MODELS:
        raise OrchestratorError("比較モデルは2～4件選択してください")
    if len({(c.workflow_id, c.filename) for c in choices}) != len(choices):
        raise OrchestratorError("同一モデルが重複しています")
    if policy not in POLICIES:
        raise OrchestratorError("比較方式が不正です")
    if seed is None:
        seed = secrets.randbits(32)
    for key, value in (("width", width), ("height", height), ("seed", seed)):
        check_param(key, value)
    camera = camera_spec.normalize(camera)
    targets = []
    for choice in choices:
        workflow = choice.workflow_id
        entry = workflows.get(workflow, {})
        if workflow not in COMPARISON_IDS or entry.get("kind") != "t2i":
            raise OrchestratorError("比較生成は対応するT2Iモデル専用です")
        fixed = workflow == QWEN_FAST_ID or sdxl_checkpoint_kind(choice.filename) == "turbo"
        if workflow in (QWEN_ID, QWEN_FAST_ID, ANIMA_ID) and (width % 16 or height % 16):
            raise OrchestratorError("Anima・Qwenを含む比較の幅と高さは16の倍数にしてください")
        defaults = defaults_for(workflows, choice, turbo=fixed, registrations=registrations)
        values = {"width": width, "height": height, "seed": seed,
                  "steps": defaults.get("steps"), "cfg": defaults.get("cfg")}
        if policy == "common":
            if fixed and (steps != 4 or cfg != 1):
                raise OrchestratorError(f"{choice.label} は4 Steps / CFG 1固定です。モデル推奨値を使用してください")
            values.update(steps=steps, cfg=cfg)
        for key, value in values.items():
            check_param(key, value)
        if choice.filename:
            values["checkpoint_model"] = choice.filename
            split_checkpoint_option(values, {workflow})
        if camera:
            values[camera_spec.KEY] = dict(camera)
        targets.append({"label": choice.label, "workflow_id": workflow,
                        "overrides": values, "status": "pending"})
    return targets


def representative(targets):
    """A single shared interpretation, not a model-specific rewrite per result."""
    return next((t for workflow in (ANIMA_ID, WAI_ID, QWEN_ID, QWEN_FAST_ID)
                 for t in targets if t["workflow_id"] == workflow), targets[0])


def project_prompt_pair(result, targets, workflows):
    """Compile every target from exactly the same standalone representations."""
    source = result["workflow_id"]
    clean, bundle = image_prompts.split_saved(result["parameters"], source)
    _, camera = camera_spec.split(clean, {source})
    source_format = image_prompts.prompt_format(source)
    if source_format is None:
        raise OrchestratorError("比較用プロンプト形式が不正です")
    prompts = bundle["prompts"] if bundle else {source_format: image_prompts.active_pair(clean)}
    instructions = bundle["instructions"] if bundle else ()
    prepared = []
    for target in targets:
        workflow = target["workflow_id"]
        fmt = image_prompts.prompt_format(workflow)
        if fmt not in prompts or (workflow == ANIMA_ID and set(prompts) != set(image_prompts.FORMATS)):
            raise OrchestratorError("比較に必要なプロンプト形式が揃いません。解釈キャッシュをOFFにして再試行してください")
        overrides, expected_camera = camera_spec.split(target["overrides"], {workflow})
        if expected_camera != camera:
            raise OrchestratorError("共通カメラ設定が一致しません")
        params = {**workflows[workflow].get("defaults", {}), **overrides, **prompts[fmt]}
        if camera:
            params[camera_spec.KEY] = dict(camera)
        params = image_prompts.bind_bundle(workflow, params, prompts.get(image_prompts.other_format(fmt)), instructions)
        prepared.append(params)
    return prepared


class ComparisonStore:
    """Small manifests; output pixels and full history remain in existing stores."""
    def __init__(self, history_store):
        self.history = history_store
        self.root = Path(history_store.data) / "image_comparisons"

    def _path(self, group_id):
        if not valid_group_id(group_id):
            raise OrchestratorError("比較グループIDが不正です")
        return self.root / (group_id + ".json")

    def create(self, request, targets, policy):
        manifest = {"version": 1, "id": uuid.uuid4().hex,
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "request": request, "policy": policy, "status": "preparing",
                    "message": "", "targets": copy.deepcopy(targets)}
        self.save(manifest)
        return manifest

    def save(self, manifest):
        path = self._path(manifest["id"])
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.root,
                                    prefix=".comparison-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(manifest, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def read(self, group_id):
        try:
            path = self._path(group_id)
            if path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("size")
            value = json.loads(path.read_text(encoding="utf-8"))
            if (not isinstance(value, dict) or value.get("version") != 1
                    or value.get("id") != group_id or not isinstance(value.get("targets"), list)
                    or not isinstance(value.get("created_at"), str)
                    or not isinstance(value.get("request"), str)
                    or value.get("policy") not in POLICIES
                    or not 2 <= len(value["targets"]) <= MAX_MODELS
                    or any(not isinstance(t, dict) or not isinstance(t.get("label"), str)
                           or t.get("workflow_id") not in COMPARISON_IDS
                           or not isinstance(t.get("overrides"), dict)
                           or ("images" in t and not isinstance(t["images"], list))
                           or ("parameters" in t and not isinstance(t["parameters"], dict))
                           for t in value["targets"])):
                raise ValueError("schema")
            return value
        except (OSError, ValueError, TypeError) as exc:
            raise OrchestratorError("比較記録を読み込めません: " + str(exc)) from exc

    def recent(self):
        if not self.root.exists():
            return ()
        paths = []
        for path in self.root.glob("*.json"):
            try:
                paths.append((path.stat().st_mtime_ns, path))
            except OSError:
                continue
        paths = [path for _, path in sorted(paths, reverse=True)]
        result = []
        for path in paths[:MAX_GROUPS]:
            try:
                result.append(self.read(path.stem))
            except OrchestratorError:
                continue
        return tuple(result)

    def images_for(self, target):
        paths = []
        for name in target.get("images", ()):
            if not isinstance(name, str):
                continue
            path = (self.history.outputs / name).resolve()
            if path.is_relative_to(self.history.outputs.resolve()) and path.is_file():
                paths.append(path)
        return tuple(paths)

    def completed(self, manifest, index, result, images, history_id):
        target = manifest["targets"][index]
        paths = []
        for image in images:
            path = Path(image).resolve()
            if path.is_file() and path.is_relative_to(self.history.outputs.resolve()):
                paths.append(path.relative_to(self.history.outputs.resolve()).as_posix())
        if not paths:
            raise OrchestratorError("比較結果の画像を回収できません")
        target.update(status="completed", images=paths, history_id=history_id,
                      parameters=copy.deepcopy(result["parameters"]),
                      elapsed_seconds=result.get("elapsed_seconds"))
        self.save(manifest)

    def resolved(self, manifest):
        """A recovered job is linked by its immutable group and slot metadata."""
        value = copy.deepcopy(manifest)
        for entry in self.history.comparison_entries(value["id"]):
            index = entry.comparison_index
            if type(index) is int and 0 <= index < len(value["targets"]):
                target = value["targets"][index]
                if target["workflow_id"] == entry.workflow_id:
                    target.update(status="completed", history_id=entry.id,
                                  parameters=entry.parameters,
                                  images=[p.relative_to(self.history.outputs.resolve()).as_posix()
                                          for p in entry.images if p.is_relative_to(self.history.outputs.resolve())])
        return value


def run_comparison(controller, store, manifest, *, composition_image=None,
                   character_references=(), character_traits=None, character_analysis=None,
                   on_update=None):
    """Never enqueue another job after an ambiguous failure or cancellation."""
    targets = manifest["targets"]
    active = None

    def publish():
        store.save(manifest)
        if on_update:
            on_update(copy.deepcopy(manifest))

    try:
        with TemporaryDirectory(prefix="asobiba-compare-") as temporary:
            folder = Path(temporary)
            composition = copy_frozen_asset(composition_image, folder, "composition")
            refs = tuple(copy_frozen_asset(p, folder, f"character_{i}")
                         for i, p in enumerate(character_references))
            context = {"composition_image": composition, "character_references": refs,
                       "character_traits": character_traits, "character_analysis": character_analysis}
            comfy = ComfyUI(controller.config["comfyui"])
            workflows = controller.config["workflows"]
            for target in targets:
                check_cancel(controller.cancel_event)
                workflow = target["workflow_id"]
                entry = workflows[workflow]
                clean, _ = camera_spec.split(target["overrides"], {workflow})
                inputs, options = split_checkpoint_option(clean, {workflow})
                params = {**entry.get("defaults", {}), **inputs}
                template = build_template(controller.config_path, entry, workflow, params, {}, options, final=True)
                preflight(comfy, controller.config, workflow, entry, template, options)
            source = representative(targets)
            controller.note("比較生成: 共通プロンプトを作成")
            profile = controller.config["llm"].get("t2i_prompt_profile") if source["workflow_id"] == WAI_ID else None
            result, _, _ = controller.generate(manifest["request"], source["workflow_id"],
                                               source["overrides"], prompt_profile=profile,
                                               dry_run=True, **context)
            prepared = project_prompt_pair(result, targets, workflows)
            for target, parameters in zip(targets, prepared):
                target["parameters"] = parameters
            manifest["status"] = "generating"
            publish()
            for index, (target, parameters) in enumerate(zip(targets, prepared)):
                check_cancel(controller.cancel_event)
                active = index
                target["status"] = "running"
                publish()
                controller.note(f"比較生成 {index+1}/{len(targets)}: {target['label']}")
                result, images, history_id = controller.generate_prepared(
                    manifest["request"], target["workflow_id"], parameters,
                    prompt_profile=profile, comparison_group_id=manifest["id"],
                    comparison_index=index, **context)
                store.completed(manifest, index, result, images, history_id)
                active = None
                publish()
            manifest["status"] = "completed"
            manifest["message"] = "比較生成が完了しました"
    except Exception as exc:
        cancelled = controller.cancel_event is not None and controller.cancel_event.is_set()
        manifest["status"] = "interrupted" if cancelled else "error"
        manifest["message"] = str(exc)
        if active is not None and targets[active]["status"] != "completed":
            targets[active]["status"] = manifest["status"]
        # Preserve earlier images and never resubmit an uncertain ComfyUI job.
        controller.note("比較生成中断: " + str(exc))
    publish()
    return copy.deepcopy(manifest)
