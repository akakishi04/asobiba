"""Persistent image adjustment session backed by the existing reviewed-plan service."""
from __future__ import annotations

import copy
import secrets
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from .input_snapshot import copy_frozen_asset
from . import image_prompts, camera_spec
from .model_profiles import ANIMA_ID, ANIMA_BASE, QWEN_ID
from .output_collection import IMAGE_EXTENSIONS
from .parameters import PARAMS, OrchestratorError, check_param
from .prompt_inference import check_cancel
from .single_prompt import SinglePromptDraft
from .workflow_registry import (
    IMAGE_INPUTS, QWEN_IDS, QWEN_LIGHTNING_ID, SDXL_WORKFLOW_IDS,
    sdxl_checkpoint_kind, split_checkpoint_option, supplied_inputs, validate_plan,
)

SUPPORTED = SDXL_WORKFLOW_IDS | QWEN_IDS | {ANIMA_ID}
I2I = "wai_i2i_basic"
NUMERICAL = ("width", "height", "steps", "cfg", "denoise", "control_strength", "seed")


def supported_workflow(workflow_id, workflows):
    return (workflow_id in SUPPORTED and workflow_id in workflows
            and workflows[workflow_id].get("kind") in ("t2i", "i2i", "inpaint", "pose"))


def image_file(path):
    return bool(path and Path(path).suffix.lower() in IMAGE_EXTENSIONS and Path(path).is_file())


def can_adjust(entry, workflows):
    return bool(entry is not None and not entry.legacy
                and supported_workflow(entry.workflow_id, workflows)
                and any(image_file(path) for path in entry.images)
                and isinstance(entry.parameters.get("positive_prompt"), str)
                and entry.parameters["positive_prompt"].strip()
                and type(entry.parameters.get("seed")) is int)


def _validated(workflows, workflow_id, parameters, assets):
    if not supported_workflow(workflow_id, workflows):
        raise OrchestratorError("画像調整に対応していないワークフローです")
    workflow = workflows[workflow_id]
    binds = workflow["bindings"]
    if IMAGE_INPUTS.intersection(binds) != supplied_inputs(
            assets.get("image"), assets.get("mask_image"), assets.get("pose_image")):
        raise OrchestratorError("元の参照画像・マスク・ポーズ画像が揃っていません")
    parameters, camera = camera_spec.split(parameters, {workflow_id})
    parameters, bundle = image_prompts.split_saved(parameters, workflow_id)
    params, model = split_checkpoint_option(parameters, {workflow_id})
    if "seed" in binds and "seed" not in params:
        raise OrchestratorError("保存されたSeedがありません")
    _, params = validate_plan({"workflow_id": workflow_id, "parameters": params},
                              {workflow_id: workflow}, assets.get("image") is not None)
    if workflow_id in QWEN_IDS and any(params[k] % 16 for k in ("width", "height")):
        raise OrchestratorError("Qwen-Imageの幅・高さは16の倍数にしてください")
    if (workflow_id == QWEN_LIGHTNING_ID or
            sdxl_checkpoint_kind(model.get("checkpoint_model")) == "turbo"):
        if params.get("steps") != 4 or params.get("cfg") != 1:
            raise OrchestratorError("高速蒸留モデルは4 Steps / CFG 1固定です")
    for key in binds:
        if key not in IMAGE_INPUTS and key not in params:
            raise OrchestratorError(f"保存された生成設定がありません: {key}")
    return {**params, **model, **({image_prompts.KEY: bundle} if bundle is not None else {}),
            **({camera_spec.KEY: camera} if camera else {})}


class ImageAdjustDraft(SinglePromptDraft):
    """Independent comparison baseline, exact graph inputs, and repeated runs.

    English, Japanese review and optional rewriting share SinglePromptDraft.
    A comparison change alone never alters generation inputs or parameters.
    """
    @classmethod
    def from_history(cls, controller, entry, selected=None):
        if not can_adjust(entry, controller.config["workflows"]):
            raise OrchestratorError("生成設定のある対応画像履歴を選択してください")
        selected = Path(selected or next(p for p in entry.images if image_file(p))).resolve()
        if selected not in tuple(p.resolve() for p in entry.images) or not image_file(selected):
            raise OrchestratorError("選択した画像はこの履歴の出力ではありません")
        temporary = TemporaryDirectory(prefix="asobiba-adjust-")
        try:
            folder = Path(temporary.name)
            assets = {name: copy_frozen_asset(path, folder, name) for name, path in (
                ("image", entry.reference_image), ("mask_image", entry.mask_image),
                ("pose_image", entry.pose_image), ("composition_image", entry.composition_image),
            )}
            context = {
                "prompt_profile": entry.prompt_profile,
                "character_references": tuple(copy_frozen_asset(p, folder, f"character_{i}")
                                              for i, p in enumerate(entry.character_references)),
                "character_traits": entry.character_traits,
                "character_analysis": copy.deepcopy(entry.character_analysis),
            }
            params = _validated(controller.config["workflows"], entry.workflow_id,
                                entry.parameters, assets)
            baseline = copy_frozen_asset(selected, folder, "baseline")
            check_cancel(controller.cancel_event)
            draft = cls(controller, {"workflow_id": entry.workflow_id, "parameters": params},
                        entry.request_text, assets, context, temporary)
            draft.base_image = baseline
            draft.base_name = selected.name
            draft.results = []
            draft.result_parameters = []
            draft.group_id = uuid.uuid4().hex
            draft.source_history_id = entry.id
            return draft
        except BaseException:
            temporary.cleanup()
            raise

    @property
    def numeric_fields(self):
        bindings = self.controller.config["workflows"][self.workflow_id]["bindings"]
        return tuple(key for key in NUMERICAL if key in bindings)

    @property
    def checkpoint_selectable(self):
        return self.workflow_id in SDXL_WORKFLOW_IDS or self.workflow_id in (ANIMA_ID, QWEN_ID)

    def fixed_sampler(self, checkpoint=None):
        if checkpoint is None:
            checkpoint = self.parameters.get("checkpoint_model")
        return (self.workflow_id == QWEN_LIGHTNING_ID or
                sdxl_checkpoint_kind(checkpoint) == "turbo")

    def can_use_base_as_input(self):
        return (self.workflow_id in SDXL_WORKFLOW_IDS
                and sdxl_checkpoint_kind(self.parameters.get("checkpoint_model")) != "turbo"
                and supported_workflow(I2I, self.controller.config["workflows"]))

    def t2i_choices(self):
        workflows = self.controller.config["workflows"]
        if workflows[self.workflow_id]["kind"] != "t2i":
            return ()
        return tuple(key for key in workflows if supported_workflow(key, workflows)
                     and workflows[key]["kind"] == "t2i")

    def switch_t2i(self, target, checkpoint=None):
        """Explicitly reuse the saved prompt format; never reinterpret or reuse a sampler."""
        if self._closed or target not in self.t2i_choices():
            raise OrchestratorError("モデル方式の切り替えは対応するT2I同士に限ります")
        if target == self.workflow_id:
            return
        workflows = self.controller.config["workflows"]
        clean, bundle = image_prompts.split_saved(self.parameters, self.workflow_id)
        target_format = image_prompts.prompt_format(target)
        bundle = bundle or image_prompts.make_bundle(self.workflow_id, clean, None)
        if target_format not in bundle["prompts"]:
            raise OrchestratorError("切り替え先のプロンプトが未取得です。修正指示の反映で両形式を生成してください")
        params = {**workflows[target].get("defaults", {}), **bundle["prompts"][target_format]}
        if target == ANIMA_ID:
            params["checkpoint_model"] = checkpoint or ANIMA_BASE
        elif target == QWEN_ID and checkpoint:
            params["checkpoint_model"] = checkpoint
        for key in ("width", "height", "seed"):
            if key in clean and key in workflows[target]["bindings"]:
                params[key] = clean[key]
        if camera_spec.KEY in clean:
            params[camera_spec.KEY] = camera_spec.normalize(clean[camera_spec.KEY])
        params = image_prompts.bind_bundle(
            target, params, bundle["prompts"].get(image_prompts.other_format(target_format)),
            bundle["instructions"])
        validated = _validated(workflows, target, params, self.assets)
        self.workflow_id = target
        self.parameters = validated
        self.fields = tuple(key for key in ("positive_prompt", "negative_prompt")
                            if key in workflows[target]["bindings"])
        self.context = {**self.context, "prompt_profile": None}

    def apply_edits(self, prompts, numeric, checkpoint=None):
        """Validate the entire form before publishing anything."""
        if self._closed:
            raise OrchestratorError("画像調整を閉じています")
        if set(numeric) != set(self.numeric_fields):
            raise OrchestratorError("生成設定の項目が一致しません")
        params = self.canonical_parameters(prompts)
        for key, raw in numeric.items():
            if not isinstance(raw, str):
                raise OrchestratorError(f"{key} の入力は数値文字列で指定してください")
            try:
                value = int(raw) if PARAMS[key][0] == "integer" else float(raw)
            except (TypeError, ValueError, OverflowError) as exc:
                raise OrchestratorError(f"{key} の数値が不正です") from exc
            check_param(key, value)
            params[key] = value
        if self.checkpoint_selectable:
            if checkpoint:
                params["checkpoint_model"] = checkpoint
            else:
                params.pop("checkpoint_model", None)
        params = _validated(self.controller.config["workflows"], self.workflow_id, params, self.assets)
        self.parameters = params

    def revise(self, operation, cache, *, japanese=None, instruction=""):
        if operation != "regenerate":
            return super().revise(operation, cache, japanese=japanese, instruction=instruction)
        result = image_prompts.revise_bundle(self, instruction)
        self.parameters = _validated(self.controller.config["workflows"], self.workflow_id,
                                     result, self.assets)

    def revise_camera(self, value):
        if self._closed or self.workflow_id not in camera_spec.IDS:
            raise OrchestratorError("カメラ変更は対応するT2I専用です")
        spec = camera_spec.normalize(value)
        old = camera_spec.normalize(self.parameters.get(camera_spec.KEY))
        if spec == old:
            return
        if not spec:
            # Unset constraints without changing the already reviewed image text.
            self.parameters = {k: v for k, v in self.parameters.items() if k != camera_spec.KEY}
            return
        result = image_prompts.revise_bundle(self, "指定したカメラ設定だけを反映し、他の内容は維持する。",
                                            camera_update=spec)
        self.parameters = _validated(self.controller.config["workflows"], self.workflow_id,
                                     result, self.assets)

    def generate_variant(self, *, fixed_seed=True):
        """A random seed is chosen once, and becomes visible only on success."""
        old = self.parameters
        try:
            if not fixed_seed:
                self.parameters = {**old, "seed": secrets.randbits(32)}
            return self.generate()
        finally:
            self.parameters = old

    def accept_completed(self, completed):
        result, images, history_id = completed
        if result.get("status") != "completed" or result.get("workflow_id") != self.workflow_id:
            raise OrchestratorError("調整結果のワークフローが一致しません")
        paths = tuple(Path(p) for p in images if image_file(p))
        if not paths:
            raise OrchestratorError("調整結果の画像が取得できません")
        params = _validated(self.controller.config["workflows"], self.workflow_id,
                            result["parameters"], self.assets)
        self.parameters = copy.deepcopy(params)
        self.results.extend(paths)
        self.result_parameters.extend(copy.deepcopy(params) for _ in paths)
        return paths[-1], history_id

    def adopt_result(self, path):
        """Change only the comparison baseline. Keep the real source untouched."""
        path = Path(path)
        if path not in self.results or not image_file(path):
            raise OrchestratorError("調整結果から基準画像を選択してください")
        previous = self.base_image
        base = copy_frozen_asset(path, Path(self._temporary.name), "base_" + uuid.uuid4().hex)
        self.base_image, self.base_name = base, path.name
        if previous not in self.assets.values():
            previous.unlink(missing_ok=True)

    def use_base_as_input(self):
        """Explicitly switch to the registered I2I graph with the selected baseline.

        Old masks/pose/composition no longer describe the new source. Drop them
        rather than silently applying them to a different image.
        """
        if not self.can_use_base_as_input():
            raise OrchestratorError("現在のモデルはこのI2I編集に対応していません")
        workflows = self.controller.config["workflows"]
        binds = workflows[I2I]["bindings"]
        params = {key: value for key, value in self.parameters.items()
                  if (key in binds and key not in IMAGE_INPUTS) or key in ("checkpoint_model", image_prompts.KEY)}
        assets = {"image": self.base_image, "mask_image": None,
                  "pose_image": None, "composition_image": None}
        validated = _validated(workflows, I2I, params, assets)
        previous = self.assets.get("image")
        self.workflow_id = I2I
        self.parameters = validated
        self.assets = assets
        if previous and previous != self.base_image and previous.name.startswith("base_"):
            previous.unlink(missing_ok=True)
        self.fields = tuple(key for key in ("positive_prompt", "negative_prompt") if key in binds)
        self.context = {**self.context, "prompt_profile": None}
