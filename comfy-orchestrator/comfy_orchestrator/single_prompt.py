"""One reviewed image/video generation with frozen inputs and editable prompts.

The English prompt remains authoritative. Planning uses the existing dry-run,
execution uses exact saved parameters; neither translation nor rewrite submits
a generation job. The temporary input snapshot belongs to the open draft.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from . import h3_prompt as hp
from .h3 import h3_ref2va_filename, ensure_h3_reference_prompt
from .input_snapshot import copy_frozen_asset
from . import image_prompts, camera_spec
from .model_profiles import ANIMA_ID
from .jobs import JobCancellationRequested
from .lmstudio import LMStudio
from .model_runtime import release_comfy_before_llm
from .parameters import OrchestratorError, check_param
from .prompt_inference import check_cancel, request_validated
from .prompt_review import protect, restore, translate_pending
from .workflow_registry import H3_I2V_ID, SDXL_WORKFLOW_IDS


FIELDS = ("positive_prompt", "negative_prompt")
LABELS = {"positive_prompt": "ポジティブ", "negative_prompt": "ネガティブ"}
INPUTS = ("image", "mask_image", "pose_image", "composition_image")


class SinglePromptDraft:
    def __init__(self, controller, result, request, assets, context, temporary):
        self.controller = controller
        self.workflow_id = result["workflow_id"]
        self.parameters = copy.deepcopy(result["parameters"])
        self.request = request
        self.assets = dict(assets)
        self.context = copy.deepcopy(context)
        self._temporary = temporary
        self.text_only = self.parameters.get("text_only_h3") is True
        self.official = (self.workflow_id == H3_I2V_ID
                         and (self.text_only or hp.enabled(controller.config.get("llm", {}))))
        self.reference_only = (self.workflow_id == H3_I2V_ID
                               and h3_ref2va_filename(self.parameters.get("h3_model")) is not None)
        self.fields = tuple(key for key in FIELDS
                            if key in controller.config["workflows"][self.workflow_id]["bindings"])
        if self.text_only and (self.workflow_id != H3_I2V_ID or self.reference_only
                               or self.assets.get("image") is not None):
            raise OrchestratorError("H3参照なしモードの確認内容が不正です")
        self._closed = False
        self._unreleased = False
        self.review_references = ()
        # Verify the plan immediately, not only at generation time.
        self.canonical_parameters(self.english())

    @classmethod
    def prepare(cls, controller, request, workflow_id, overrides, *, image=None,
                mask_image=None, pose_image=None, composition_image=None,
                prompt_profile=None, character_references=(), character_traits=None,
                character_analysis=None, cache=None):
        temporary = TemporaryDirectory(prefix="asobiba-prompt-")
        try:
            folder = Path(temporary.name)
            assets = {key: copy_frozen_asset(value, folder, key)
                      for key, value in zip(INPUTS, (image, mask_image, pose_image, composition_image))}
            context = {
                "prompt_profile": prompt_profile,
                "character_references": tuple(copy_frozen_asset(path, folder, f"character_{i}")
                                              for i, path in enumerate(character_references)),
                "character_traits": character_traits,
                "character_analysis": copy.deepcopy(character_analysis),
            }
            check_cancel(controller.cancel_event)
            result, _, _ = controller.generate(request, workflow_id, overrides,
                                               **assets, **context, dry_run=True)
            draft = cls(controller, result, request, assets, context, temporary)
            if cache is not None:
                draft.translate(cache, best_effort=True)
            check_cancel(controller.cancel_event)
            return draft
        except BaseException:
            temporary.cleanup()
            raise

    def close(self):
        if not self._closed:
            self._closed = True
            self._temporary.cleanup()

    def english(self):
        values = (image_prompts.editor_pair(self.parameters, self.workflow_id)
                  if image_prompts.is_mixed(self.parameters) else
                  {key: self.parameters.get(key, "") for key in self.fields})
        if self.official and values["positive_prompt"].startswith(hp.I2VA_HEADER + "\n\n"):
            values["positive_prompt"] = values["positive_prompt"][len(hp.I2VA_HEADER) + 2:]
        return values

    def canonical_parameters(self, values):
        if set(values) != set(self.fields):
            raise OrchestratorError("編集するプロンプトの項目が一致しません")
        params = dict(self.parameters)
        for key, raw in values.items():
            check_param(key, raw)
            text = raw.strip()
            if key == "positive_prompt" and not text:
                raise OrchestratorError("ポジティブプロンプトを入力してください")
            if key == "positive_prompt" and self.official:
                sections, ref = hp.parse_sections(text)
                if ref != self.reference_only:
                    raise OrchestratorError("H3の参照方式とプロンプト形式が一致しません")
                text = hp.compile_prompt(sections, ref, kept_frames=params["frames"], text_only=self.text_only)
            elif key == "positive_prompt" and self.reference_only:
                text = ensure_h3_reference_prompt(text)
            params[key] = text
        return image_prompts.synchronize(params, self.workflow_id, self.parameters)

    def set_english(self, values):
        self.parameters = self.canonical_parameters(values)

    def _cache_kind(self, key):
        if self.official and key == "positive_prompt":
            return "cut", True
        return f"single:{self.workflow_id}:{key}", False

    def japanese(self, cache):
        values = {}
        for key, source in self.english().items():
            kind, official = self._cache_kind(key)
            values[key] = cache.get(kind, source, official)
        return values

    def _missing(self, cache):
        pending = []
        for key, source in self.english().items():
            kind, official = self._cache_kind(key)
            if source.strip() and cache.get(kind, source, official) is None:
                pending.append((key, kind, source, official))
        return pending

    def _session(self, action):
        config = self.controller.config
        settings = dict(config["llm"], send_reference_to_llm=False)
        if settings.get("model", "") in ("", "SELECT_IN_GUI"):
            raise OrchestratorError("LM Studioのモデルを選択してください")
        check_cancel(self.controller.cancel_event)
        release_comfy_before_llm(config["comfyui"], progress=self.controller.note)
        check_cancel(self.controller.cancel_event)
        client = LMStudio(settings)
        instance = None
        try:
            instance = client._ensure_loaded()
            return action(client, instance)
        finally:
            try:
                client.unload_selected(instance, self.controller.note)
            except OrchestratorError:
                self._unreleased = True
                raise
            else:
                if instance is not None:
                    self._unreleased = False

    def _translate_loaded(self, cache, client, instance):
        for key, kind, source, official in self._missing(cache):
            translate_pending(client, instance, [(LABELS[key], kind, source)], cache, official,
                              self.controller.note, self.controller.cancel_event)

    def translate(self, cache, *, best_effort=False):
        if not self._missing(cache) and not self._unreleased:
            return
        try:
            self._session(lambda client, instance: self._translate_loaded(cache, client, instance))
        except JobCancellationRequested:
            raise
        except OrchestratorError as exc:
            if not best_effort:
                raise
            self.controller.note("日本語訳を中断しました。英語プロンプトを保持します: " + str(exc))

    def revise(self, operation, cache, *, japanese=None, instruction=""):
        """Stage all edits, validate them, and review the actual English again."""
        if operation not in ("apply", "regenerate"):
            raise OrchestratorError("プロンプト操作が不正です")
        if not isinstance(instruction, str) or len(instruction) > 2000:
            raise OrchestratorError("修正指示は2000文字以内です")
        if (self.workflow_id == ANIMA_ID or camera_spec.KEY in self.parameters) and operation == "regenerate":
            self.parameters = image_prompts.revise_bundle(
                self, instruction.strip() or "生成内容を維持し、タグと自然文の表現を最適化する。")
            return
        before = self.english()
        if operation == "apply":
            if not isinstance(japanese, dict) or set(japanese) != set(self.fields):
                raise OrchestratorError("日本語の編集項目が不正です")
            if any(not isinstance(v, str) or len(v) > 15000 for v in japanese.values()):
                raise OrchestratorError("日本語プロンプトが長すぎます")
        format_hint = (
            "Retain the exact H3 section names and order shown in current_english. "
            "Use the same reference mode, valid shot timing and dialogue notation. "
            "Never include the host-added opening-frame header."
            + (" No source images exist; establish the scene from text and do not use reference labels."
               if self.text_only else "")
            + ("\n" + hp.RETENTION_POLICY if self.reference_only else "")
            if self.official else
            "Use concise comma-separated English visual tags and preserve tag weights."
            if self.workflow_id in SDXL_WORKFLOW_IDS or self.workflow_id == ANIMA_ID else
            "Use natural English suitable for the selected generation model."
        )

        def task(client, instance):
            payload = {"request": self.request, "workflow": self.workflow_id,
                       "current_english": before, "instruction": instruction}
            if operation == "apply":
                baseline = self.japanese(cache)
                changed = {key: value for key, value in japanese.items()
                           if value != (baseline[key] or "")}
                if not changed:
                    return
                masked, tokens = {}, {}
                for key, value in changed.items():
                    masked[key], tokens[key] = protect(value)
                payload["edited_japanese"] = masked
                keys = tuple(changed)
                system = ("Translate only the edited Japanese fields into faithful English. "
                          "Add nothing. Preserve every protected token exactly once in order. "
                          "The user's Japanese edit is authoritative. ")
            else:
                tokens = {}
                keys = self.fields
                system = ("Rewrite the generation prompts for the original request, using the "
                          "existing English and the user's optional repair instruction. Preserve "
                          "unspecified content, negative conditions and identity. Do not add settings. ")
            system += format_hint
            if operation == "regenerate" and image_prompts.prompt_format(self.workflow_id) is not None:
                system += image_prompts.CLOTHING_FIDELITY_POLICY.replace(
                    "BOTH standalone positive prompts", "the positive prompt")
            def validate(reply):
                if set(reply) != set(keys):
                    raise OrchestratorError("プロンプトの項目が一致しません")
                staged = dict(before)
                for key, text in reply.items():
                    if not isinstance(text, str):
                        raise OrchestratorError("プロンプトが文字列ではありません")
                    staged[key] = restore(text, tokens[key]) if key in tokens else text
                return self.canonical_parameters(staged)
            result = request_validated(
                client, instance, system, json.dumps(payload, ensure_ascii=False),
                {"type": "object", "properties": {key: {"type": "string", "maxLength": 5000}
                                                    for key in keys},
                 "required": list(keys), "additionalProperties": False},
                "single_prompt_edit" if operation == "apply" else "single_prompt_rewrite",
                validate, self.controller.note, self.controller.cancel_event,
                translation_chars=sum(map(len, japanese.values())) if operation == "apply" else None,
                direct_answer=operation == "regenerate" and image_prompts.prompt_format(self.workflow_id) is not None,
            )
            check_cancel(self.controller.cancel_event)
            # A cancelled or failed back-translation cannot publish half an edit.
            previous = self.parameters
            self.parameters = result
            try:
                self._translate_loaded(cache, client, instance)
            except JobCancellationRequested:
                self.parameters = previous
                raise
            except OrchestratorError as exc:
                self.controller.note("英語の編集は保持しました。未翻訳分: " + str(exc))
        previous = self.parameters
        try:
            self._session(task)
        except BaseException:
            self.parameters = previous
            raise

    def generate(self):
        if self._closed:
            raise OrchestratorError("プロンプト確認を閉じています")
        if self._unreleased:
            raise OrchestratorError("LLMモデルの解放を確認できません。日本語訳を再実行してください")
        completed = self.controller.generate_prepared(
            self.request, self.workflow_id, copy.deepcopy(self.parameters),
            **self.assets, **self.context,
        )
        result = completed[0]
        if result.get("job_id") and self.controller.journal is not None:
            try:
                journal = self.controller.journal
                self.review_references = journal.context_for_history(journal.read(result["job_id"]))["character_references"]
            except (OSError, ValueError, OrchestratorError) as exc:
                self.controller.note("生成後の参照画像情報を取得できません: " + str(exc))
        return completed
