"""LM Studio native model lifecycle and OpenAI-compatible structured inference.

The selected LM Studio model is unloaded before ComfyUI starts generation.
Other loaded models are never unloaded implicitly.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .core import OrchestratorError, _open_json, plan_schema, HOST_VIDEO_IDS, H3_I2V_ID, QWEN_IDS
from .character_refs import observation_schema, intersection_schema, validate_images
from .character_repair import repair_model_analysis
from .model_runtime import record_model_event
from .prompt_profiles import (
    DEFAULT_T2I_PROFILE, T2I_PROFILE_LEGACY,
    DEFAULT_I2I_PROFILE, I2I_PROFILE_LEGACY,
    apply_t2i_profile, apply_i2i_profile,
    is_t2i_context, is_i2i_context,
    edit_strength_hint,
    DEFAULT_H3_PROFILE, H3_PROFILE_LABELS, apply_h3_profile, is_h3_context,
)


def _request(settings: dict, route: str, payload: dict | None = None) -> dict:
    base = settings["base_url"].rstrip("/")
    # Loading/unloading a model and waiting for a thinking LLM answer have
    # different latency profiles. Only the inference request receives the
    # longer wait; keep the ordinary API timeout for short management calls.
    inference = route == "/v1/chat/completions"
    timeout = float(
        settings.get("inference_timeout_seconds", 600)
        if inference else settings.get("timeout_seconds", 240)
    )
    headers = {"Content-Type": "application/json"}
    token = os.environ.get(settings.get("token_env", "LMSTUDIO_API_TOKEN"), "")
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base + "/" + route.lstrip("/"),
        data=data,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    try:
        return _open_json(request, timeout=timeout)
    except OrchestratorError as exc:
        if "timed out" in str(exc).lower() or "timeout" in str(exc).lower():
            label = "自然文解釈" if inference else "API操作"
            raise OrchestratorError(
                f"LM Studioの{label}で通信タイムアウトしました（{timeout:g}秒）。"
                "LLMの推論負荷と起動状態を確認してください。"
                "設定 llm.inference_timeout_seconds で推論待ちを変更できます。"
            ) from exc
        raise


def list_models(settings: dict) -> list[dict]:
    """List local LM Studio LLMs; does not load them."""
    result = _request(settings, "/api/v1/models")
    models = result.get("models")
    if not isinstance(models, list):
        raise OrchestratorError("LM Studioのモデル一覧応答が不正です。サーバーが起動しているか確認してください")
    return [
        item for item in models
        if isinstance(item, dict) and item.get("type") == "llm"
        and isinstance(item.get("key"), str)
    ]


# A separate observation pass makes mistaken image interpretation visible
# before those mistakes are translated into an SDXL generation prompt.
COMPOSITION_FIELDS = {
    "framing": "画角・切り取り",
    "camera": "カメラ視点",
    "subject_placement": "人数・画面内の位置",
    "body_pose": "全身姿勢・重心",
    "torso_orientation": "胴体の向き",
    "head_and_gaze": "頭部と視線",
    "arms_and_hands": "腕と手",
    "legs_and_feet": "脚と足",
    "uncertain_or_hidden": "不明点・隠れた部分",
}


def composition_schema() -> dict:
    """Small, strictly formatted factual observation (no invented coordinates)."""
    return {
        "type": "object",
        "properties": {
            key: {"type": "string", "maxLength": 300}
            for key in COMPOSITION_FIELDS
        },
        "required": list(COMPOSITION_FIELDS),
        "additionalProperties": False,
    }


def read_json_reply(result: dict, label: str) -> dict:
    """Validate an LM Studio structured response without trusting its content."""
    choices = result.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise OrchestratorError(f"LM Studioの{label}応答形式が不正です")
    message = choices[0].get("message")
    raw = message.get("content") if isinstance(message, dict) else None
    if not isinstance(raw, str):
        raise OrchestratorError(f"LM Studioの{label}がJSON文字列を返しませんでした")
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise OrchestratorError(f"LM Studioの{label}のJSONを解析できません: {raw[:150]}") from exc
    if not isinstance(parsed, dict):
        raise OrchestratorError(f"LM Studioの{label}はJSONオブジェクトが必要です")
    return parsed


def format_composition_observation(observation: dict) -> str:
    lines = []
    for key, label in COMPOSITION_FIELDS.items():
        value = observation.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 300:
            raise OrchestratorError(f"構図認識結果の {key} が不正です")
        lines.append(f"{label}: {value.strip()}")
    return "\n".join(lines)


class LMStudio:
    def __init__(self, settings: dict):
        self.settings = settings
        self.model = settings["model"]
        self.unload_after = settings.get("unload_after_inference", True)

    def _ensure_loaded(self) -> str:
        catalog = list_models(self.settings)
        matching = next((item for item in catalog if item["key"] == self.model), None)
        if matching is None:
            raise OrchestratorError(
                f"LM Studioにモデル {self.model!r} がありません。GUIの「モデルを更新」から選択してください"
            )
        capabilities = matching.get("capabilities")
        if self.settings.get("send_reference_to_llm", False) and getattr(self, "_has_visual_input", False):
            # Older LM Studio versions may not report capabilities; only reject
            # models explicitly identified as text-only.
            if isinstance(capabilities, dict) and capabilities.get("vision") is False:
                raise OrchestratorError(
                    f"選択したモデル {self.model!r} は画像入力に非対応です。"
                    "画像対応VLMを選ぶか、GUIの「画像をLLMで構図解析」をOFFにしてください"
                )
        running = matching.get("loaded_instances") or []
        if running:
            instance_id = running[0].get("id") if isinstance(running[0], dict) else None
            if not instance_id:
                raise OrchestratorError("LM StudioのモデルインスタンスIDを取得できません")
            record_model_event("llm_reuses")
            return instance_id

        settings = {"model": self.model}
        if self.settings.get("context_length") is not None:
            settings["context_length"] = self.settings["context_length"]
        result = _request(self.settings, "/api/v1/models/load", settings)
        loaded_id = result.get("instance_id", result.get("model_instance_id"))
        if result.get("status") != "loaded" or not isinstance(loaded_id, str) or not loaded_id:
            raise OrchestratorError(f"LM Studioのロード完了を確認できません: {result}")
        record_model_event("llm_loads")
        return loaded_id

    def unload_selected(self, instance_id, progress=None, *, label="LM Studio: 選択モデルをアンロード"):
        """Unload only the instance acquired for this operation, if configured."""
        if not instance_id or not self.unload_after:
            return
        if progress:
            progress(label)
        response = _request(self.settings, "/api/v1/models/unload", {"instance_id": instance_id})
        if response.get("instance_id") != instance_id:
            raise OrchestratorError(
                "LM Studioのアンロード完了を確認できません。VRAM空き容量を確認してください"
            )
        record_model_event("llm_unloads")

    def interpret(
        self, text: str, workflows: dict, image: Path | None,
        progress: Callable[[str], None] | None = None,
        reference_role: str | None = None,
        character_traits: str | None = None,
    ) -> dict:
        if not isinstance(self.model, str) or not self.model.strip() or self.model == "SELECT_IN_GUI":
            raise OrchestratorError("LM Studioのモデルを選択してください")
        instance_id: str | None = None
        self._has_visual_input = (
            image is not None and self.settings.get("send_reference_to_llm", False)
        )
        video_only = bool(workflows) and all(
            entry.get("kind") == "i2v" for entry in workflows.values()
        )
        reference_only = video_only and H3_I2V_ID in workflows and self.settings.get("_h3_reference_only", False)
        pose_only = bool(workflows) and all(
            entry.get("kind") == "pose" for entry in workflows.values()
        )
        composition_only = (
            reference_role == "composition"
            or (
                image is not None and not pose_only
                and all("image" not in entry["bindings"] for entry in workflows.values())
            )
        )
        catalog = [
            {"id": key, "kind": entry["kind"], "description": entry.get("description", ""),
             "parameters": [
                 name for name in entry["bindings"]
                 if name not in ("image", "mask", "pose", "seed")
                 and (key not in HOST_VIDEO_IDS or name in ("positive_prompt", "negative_prompt"))
             ],
             "required_inputs": [
                 name for name in ("image", "mask", "pose")
                 if name in entry["bindings"]
             ],
             "requires_image": "image" in entry["bindings"]}
            for key, entry in workflows.items()
        ]
        system = (
            "You are a fixed ComfyUI workflow selector. Output JSON matching the provided schema. "
            "Select workflow_id only from the catalog. Never invent nodes, paths, or model names. "
            "Write a detailed positive_prompt suitable for the image-generation model; "
            "use short comma-separated English visual tags for anime-style SDXL workflows. "
            "Keep instructions faithful to the user's request. "
            "Only supply parameters supported by the selected workflow. "
            "Never provide a seed: it is generated by the application or set by the user. "
            "If the source image is not provided to the LLM, do not invent visual facts about it. "
            + (
                "A dedicated visual observation pass describes the reference image below. "
                "Use these observations as evidence, not imagination. "
                "Translate visible spatial relationships into explicit, concrete English positive_prompt tags: "
                "camera elevation and angle, view direction, framing (full-body/half-body/close-up), "
                "subject location in the frame, pose and limb placement, perspective, gaze direction, "
                "foreground/background arrangement and cropping. Avoid generic phrases such as "
                "'same composition as reference' or 'match the picture'. "
                "Do not claim pixel-accurate geometry or infer occluded joints. "
                "Respect requested changes and preserve what the user wants preserved. "
                + (
                    "This is a COMPOSITION-ONLY reference, not the image being edited or "
                    "the ControlNet source. Use its framing, camera, subject placement "
                    "and pose as textual guidance; do NOT copy character identity, "
                    "textures, clothing, colors, or background unless the user requests them."
                    if composition_only else
                    "This is a POSE reference. Describe the pose, framing and viewpoint ONLY; "
                    "do not borrow the mannequin's material, color, design, clothes, or background."
                    if pose_only else
                    "This is the image to be edited. Describe its composition accurately and "
                    "only change content, clothing or lighting when requested."
                )
                if self._has_visual_input else ""
            )
        )
        if reference_only:
            system += (
                "\n\nMiniMax H3 Ref2VA: <Picture 1> is a visual guide, not the first "
                "frame. Write natural English sentences including the literal reference tag "
                "<Picture 1>. Use it for requested appearance, character identity or style. "
                "The target scene, pose, camera, composition and aspect ratio are independent; "
                "do not require a copy of the reference or invent details you have not seen. "
                "Follow the user's request, allowing coherent natural motion and framing. "
                "Describe requested audio only, without adding unsolicited dialogue or music. "
                "Only return positive_prompt; do not choose technical generation settings."
            )
        elif video_only:
            system += (
                "\n\nIMAGE-TO-VIDEO POLICY (overrides still-image/tag/edit instructions): "
                "The source image is the initial frame, not an image to redraw. "
                "Write coherent natural English sentences describing only requested motion, "
                "timing, subject action, secondary motion, camera movement and scene continuity. "
                "Preserve character identity, art style and scene unless explicitly changed. "
                "Do not add new objects, cuts, camera moves or unseen details without request. "
                "A stationary camera is valid. Do not repeat static SDXL tags or redesign the source. "
                "If no image is visible to you, describe the user's requested movement without "
                "pretending to have observed the image. Only return positive_prompt and optional "
                "negative_prompt; video resolution, frame count, FPS and seed are host settings."
            )
        if H3_I2V_ID in workflows and not reference_only:
            system += (
                "\nMiniMax H3 FL2VA: the input image is the first frame. "
                "Describe continuous action in natural English; for a complex sequence use "
                "ordered time beats, keeping their timing consistent with the user's requested duration. "
                "The model generates synchronized audio. Include requested ambience, effects, "
                "speech or music in the same prompt; do not add dialogue or music unasked. "
                "Preserve the source illustration's style, subject and scene. "
                "Only return positive_prompt; negative prompts and CFG are not supported by this workflow."
            )
        profile = self.settings.get("t2i_prompt_profile", DEFAULT_T2I_PROFILE)
        edit_profile = self.settings.get("i2i_prompt_profile", DEFAULT_I2I_PROFILE)
        system = apply_t2i_profile(system, workflows, profile)
        system = apply_i2i_profile(system, workflows, edit_profile)
        if workflows and workflows.keys() <= QWEN_IDS:
            system += (
                "\\nQwen-Image 2512: Write coherent, descriptive natural English sentences "
                "for the requested still image, composition, materials, pose, lighting and art style. "
                "Do not use Danbooru tag lists or describe motion over time. Preserve requested "
                "illustration style and do not invent unwanted details."
            )
        if character_traits is not None:
            from .character_refs import normalize_approved
            character_traits = normalize_approved(character_traits)
            system += (
                "\n\nCHARACTER REFERENCE POLICY: You are given an explicitly "
                "USER-APPROVED character feature sheet, distilled from multiple "
                "visual references and corrected by the user. Treat ONLY the "
                "approved traits as evidence of character appearance. "
                "The reference pictures themselves are NOT available here "
                "unless separately supplied as the source/composition image. "
                "Do not borrow variable or uncertain traits from the analysis. "
                "Include the approved traits faithfully in the positive_prompt "
                "as concrete concise visual tags. For I2I, preserve the original "
                "image unless the user explicitly requests modifications; "
                "the confirmed character features guide identity, not a "
                "redesign. An explicit newer user instruction may override a "
                "sheet trait for this generation. Do not add other unseen traits."
            )
        if video_only and character_traits is not None:
            system += (
                "\nFor I2V the first frame defines appearance: the confirmed character "
                "sheet may help identify the moving subject, but do not convert the "
                "sheet into a static tag list or use it to redraw the subject."
            )
        h3_profile = self.settings.get("h3_prompt_profile", DEFAULT_H3_PROFILE)
        system = apply_h3_profile(system, workflows, h3_profile, reference_only=reference_only) if reference_only else apply_h3_profile(system, workflows, h3_profile)
        edit_enabled = (
            is_i2i_context(workflows) and edit_profile != I2I_PROFILE_LEGACY
        )
        edit_context = ""
        if edit_enabled:
            mask_present = any(
                entry.get("kind") == "inpaint" for entry in workflows.values()
            )
            edit_context = f"Mask present: {'yes' if mask_present else 'no'}\n"
            if "_edit_denoise" in self.settings:
                denoise = self.settings["_edit_denoise"]
                edit_context += (
                    f"Edit strength hint: {edit_strength_hint(denoise)} "
                    f"(host denoise={denoise:g}; this is NOT a change request)\n"
                )
            edit_context += (
                "Priority: preserve original except for explicitly requested edits. "
                "A text-only LLM must not pretend it has seen the source image.\n"
            )
        # Legacy keeps the original exact user metadata for fair comparison.
        # Do not describe a text-only T2I request as an image-to-edit operation.
        no_image_role = (
            "none (text-to-image)" if (
                is_t2i_context(workflows) and profile != T2I_PROFILE_LEGACY
            ) else "composition of image to edit"
        )
        user_text = (
            f"Available workflows: {json.dumps(catalog, ensure_ascii=False)}\n"
            f"Reference image routed to ComfyUI: {'yes' if image and not composition_only else 'no'}\n"
            f"Reference image visible to the LLM: "
            f"{'yes' if self._has_visual_input else 'no'}\n"
            f"Reference role: "
            f"{'composition only (LLM reference)' if composition_only else 'pose and camera only' if pose_only else 'visual reference <Picture 1>, not first frame' if reference_only else 'first frame of video' if video_only else no_image_role if not self._has_visual_input else 'composition of image to edit'}\n"
            f"{edit_context}"
            + (
                "User-confirmed character traits (not inferred by the LLM):\n"
                + character_traits + "\n"
                if character_traits else ""
            )
            + (f"Host video duration: {self.settings['_h3_duration_seconds']:.2f} seconds at 24 FPS.\n" if H3_I2V_ID in workflows and "_h3_duration_seconds" in self.settings else "")
            + f"User request: {text}"
        )
        message: dict[str, Any] = {"role": "user", "content": user_text}
        if self._has_visual_input:
            if not image.is_file():
                raise OrchestratorError(f"参照画像が見つかりません: {image}")
            if image.stat().st_size > 20 * 1024 * 1024:
                raise OrchestratorError("LM Studioに渡す参照画像は20MB以下にしてください")
            mime = mimetypes.guess_type(image.name)[0]
            if mime not in ("image/png", "image/jpeg", "image/webp"):
                raise OrchestratorError("LM Studioの参照画像はPNG、JPEG、WebPに対応します")
            data = base64.b64encode(image.read_bytes()).decode("ascii")
            message["content"] = [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
            ]

        try:
            if progress:
                progress("LM Studio: モデルを確認・ロード")
            instance_id = self._ensure_loaded()
            if self._has_visual_input:
                if progress:
                    progress("LM Studio: 画像の構図・人物配置・姿勢を項目別に観察中")
                # The image is sent only in this observation pass.
                # The subsequent generation planning pass works from its text.
                source_image = message["content"][1]
                observation_system = (
                    "You are a careful visual observer. Describe ONLY what is visible "
                    "in the supplied image; do NOT write a generation prompt. "
                    "Record composition, camera direction, framing, figure placement, "
                    "torso/head direction and the pose of each visible arm and leg. "
                    "Use the IMAGE'S left and right, not assumed anatomical left/right. "
                    "Describe where limbs are actually visible, not where they should be. "
                    "If a joint is occluded, the model is stylized, or the camera angle "
                    "cannot be determined, explicitly say 'unknown' instead of guessing. "
                    "Do NOT infer hidden body parts, character identity, clothing designs "
                    "or unobserved scenery. Keep every field short and factual."
                )
                observation_request = {
                    "model": instance_id,
                    "messages": [
                        {"role": "system", "content": observation_system},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "Analyze the provided visual reference as a composition "
                                        "and pose source. Fill the requested fields with concrete "
                                        "visible observations or 'unknown'."
                                    ),
                                },
                                source_image,
                            ],
                        },
                    ],
                    "stream": False,
                    "temperature": 0.0,
                    "max_tokens": self.settings.get("max_tokens", 4096),
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "comfy_visual_observation",
                            "schema": composition_schema(),
                        },
                    },
                }
                observed = read_json_reply(
                    _request(self.settings, "/v1/chat/completions", observation_request),
                    "画像観察",
                )
                report = format_composition_observation(observed)
                if progress:
                    progress("【構図認識結果】\n" + report)
                # Explicit visual facts are now input to the ordinary planner.
                # Avoid a second image encode, limiting local GPU overhead.
                message["content"] = (
                    user_text
                    + "\nVisual observations (model-estimated; unknown means not visible):\n"
                    + json.dumps(observed, ensure_ascii=False)
                    + ("\nUse these facts only to support the requested motion in natural English sentences. Do not invent hidden details." if video_only else "\nTranslate only well-supported observations into tags. Never fabricate the location of hidden joints.")
                )
            if progress and is_t2i_context(workflows):
                progress(
                    "T2Iプロンプト: "
                    + ("Illustrious v2（構図・陰影の一貫性重視）"
                       if profile != T2I_PROFILE_LEGACY else "従来版（比較用）")
                )
            if progress and is_i2i_context(workflows):
                progress(
                    "I2I/部分修正プロンプト: "
                    + ("保持重視 v1" if edit_enabled else "従来版（比較用）")
                )
            if progress and is_h3_context(workflows):
                progress("H3プロンプト: " + H3_PROFILE_LABELS[h3_profile])
            if progress:
                task_label = (
                    "自然文と構図観察結果から生成プロンプトを作成"
                    if self._has_visual_input else "自然文を解釈"
                )
                progress(
                    f"LM Studio: {task_label}"
                    f"（応答待ち上限 {self.settings.get('inference_timeout_seconds', 600)} 秒）"
                )
            request = {
                "model": instance_id,
                "messages": [{"role": "system", "content": system}, message],
                "stream": False,
                "temperature": 0.2,
                "max_tokens": self.settings.get("max_tokens", 4096),
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "comfy_plan", "schema": plan_schema(workflows)},
                },
            }
            result = _request(self.settings, "/v1/chat/completions", request)
            return read_json_reply(result, "生成プロンプト")
        finally:
            self.unload_selected(instance_id, progress)

    def analyze_character_references(
        self, images: list[Path] | tuple[Path, ...],
        progress: Callable[[str], None] | None = None,
    ) -> dict:
        """Observe 2-4 images and infer evidence-backed character invariants.

        Compare high-level character design even when the drawings, camera
        angles or outfits differ. Never produce an approved identity directly;
        the user reviews and confirms the proposed traits in the GUI.
        """
        paths = validate_images(images)
        if not isinstance(self.model, str) or not self.model.strip() or self.model == "SELECT_IN_GUI":
            raise OrchestratorError("画像対応LM Studioモデルを選択してください")
        # This dedicated action is explicitly visual even if the ordinary
        # image-to-image composition checkbox is disabled.
        self.settings = {**self.settings, "send_reference_to_llm": True}
        self._has_visual_input = True
        instance_id = None

        def info(value: str) -> None:
            if progress:
                progress(value)

        def structured(messages: list[dict], schema_name: str, schema: dict) -> dict:
            payload = {
                "model": instance_id,
                "messages": messages,
                "stream": False,
                "temperature": 0,
                "max_tokens": self.settings.get("max_tokens", 4096),
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": schema_name, "schema": schema},
                },
            }
            return read_json_reply(
                _request(self.settings, "/v1/chat/completions", payload),
                "キャラクター特徴抽出",
            )

        try:
            info("LM Studio: キャラ参照用の画像対応モデルをロード")
            instance_id = self._ensure_loaded()
            observations = []
            for i, path in enumerate(paths, 1):
                info(f"キャラ特徴観察 {i}/{len(paths)}: {path.name}")
                mime = mimetypes.guess_type(path.name)[0]
                if mime not in ("image/png", "image/jpeg", "image/webp"):
                    raise OrchestratorError(f"キャラ参照画像形式が不正です: {path}")
                encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                observations.append(structured(
                    [
                        {"role": "system", "content": (
                            "You are a careful visual observer of illustrated characters. "
                            "Return ALL HUMAN-READABLE FIELD VALUES IN NATURAL JAPANESE, "
                            "not English prompt tags. The JSON property names must remain "
                            "exactly as defined by the schema (in English). "
                            "Write clear, specific descriptions that the user can edit "
                            "as ordinary Japanese text. Do not use comma-separated "
                            "Danbooru tags, English keywords, or keyword stuffing. "
                            "For example, write '耳にかかる短い黒髪' instead of "
                            "'black hair, short hair'. Use brief Japanese descriptions "
                            "of appearance, not prompt syntax. "
                            "Keep each field concise and observational, describing "
                            "what a person can actually see. "
                            "Focus on stable identity characteristics (hair, eye details, "
                            "distinctive face traits, body proportions, accessories). "
                            "ALSO describe the character's visible FACIAL GEOMETRY "
                            "(face outline, relative eye spacing, chin/jaw shape), "
                            "SILHOUETTE (proportion and outline independent of pose), "
                            "SHAPE LANGUAGE (round vs angular or directional character "
                            "design cues), and DISTINCTIVE MOTIFS (recognizable markers). "
                            "Do not confuse image rendering style, camera angle, "
                            "lighting, temporary costume, or pose with character identity. "
                            "Describe outfits as observed, not as necessarily permanent. "
                            "Never invent hidden parts, age, backstory, identity, gender "
                            "or clothes not actually visible. If a feature is unseen or "
                            "ambiguous, write '不明'. Do not infer from other images "
                            "or from generic anime conventions."
                        )},
                        {"role": "user", "content": [
                            {"type": "text", "text": (
                                f"参照画像{i}/{len(paths)}。この画像だけを観察してください。"
                                "JSONのキー名は変更せず、値はすべて自然な日本語で記述。"
                                "見えない特徴は「不明」と書き、英語タグは出力しないでください。"
                            )},
                            {"type": "image_url", "image_url": {
                                "url": f"data:{mime};base64,{encoded}"
                            }},
                        ]},
                    ], "comfy_character_observation", observation_schema(),
                ))
            info("キャラ特徴: 造形上の共通性・相違点・同一性の仮説を統合")
            combined = structured(
                [
                    {"role": "system", "content": (
                        "You compare descriptions of illustrations that the user "
                        "says depict the same character, even when artwork STYLE, "
                        "CLOTHES, LIGHTING, POSE and CAMERA VIEWPOINT vary dramatically. "
                        "Your PRIMARY goal is to infer a VISUAL IDENTITY SIGNATURE: "
                        "stable higher-level face geometry, eye shape/spacing, hair "
                        "silhouette, proportions, repeated design motifs, overall "
                        "shape language, and their relationships. Do not merely "
                        "calculate a strict intersection of exact colors or clothing. "
                        "Return every human-readable text VALUE in natural, readable "
                        "JAPANESE for a Japanese-speaking user who will directly edit "
                        "the extracted character description. JSON property names, enum "
                        "values, and feature/aspect identifiers must stay in their "
                        "schema-defined English. Do not output Danbooru tags, English "
                        "keyword lists or prompt syntax as description strings. "
                        "For each identity_hypothesis provide aspect, a specific "
                        "Japanese sentence about the character's visual identity in "
                        "description, 1-based supporting_images, "
                        "conflicting_images, confidence (high/medium/low), and rationale "
                        "in Japanese explaining why the feature is robust across different "
                        "drawings. Keep all common/candidate values and variable/uncertain "
                        "details in natural Japanese, not comma-separated tags. "
                        "Use short Japanese noun phrases for common/candidate values "
                        "(e.g. '丸みのある頬'), but complete natural Japanese sentences "
                        "for identity_hypotheses.description and rationale "
                        "(e.g. '丸い頬と細い顎が顔立ちの特徴になっている。'). "
                        "An image that does NOT reveal the feature is unknown, NOT a "
                        "contradiction; explicit opposing evidence IS a contradiction. "
                        "Only claim supporting_images when their individual observations "
                        "actually justify the abstract characteristic; do not turn all "
                        "unspecified views into support. A hypothesis can be based on "
                        "multiple images without their wording being identical. "
                        "Use 'overall' for a concise, distinctive COMBINATION of supported "
                        "features, not generic adjectives like 'beautiful' or 'anime girl'. "
                        "Keep the older common/candidates/variable/uncertain fields too: "
                        "Use ONLY the exact machine field names from the JSON schema "
                        "for feature (hair_color, hair_style, eye_color, eye_shape, "
                        "face, body, outfit, accessories, other, facial_geometry, "
                        "silhouette, shape_language, distinctive_motifs). Do NOT "
                        "invent feature labels such as hair, eyes, identity, or "
                        "colors; those are invalid here. For abstract higher-level "
                        "hypotheses, use identity_hypotheses with aspect from the "
                        "schema instead of inventing feature categories. "
                        "Every common/candidate value must be a nonempty string "
                        "no longer than 220 characters. "
                        "common requires all images, candidates have partial direct support, "
                        "variable lists changes in outfits/style/other content, uncertain "
                        "records genuinely unknowable or conflicting traits. "
                        "For hairstyles or outfits, different camera perspectives "
                        "are not sufficient evidence of a permanent change. "
                        "Never average conflicting traits into a fictitious character. "
                        "Never confuse a changed art style with changed character anatomy. "
                        "No identity hypothesis is guaranteed; the user must verify it."
                    )},
                    {"role": "user", "content": (
                        f"参照画像の枚数: {len(paths)}。画像ごとの観察結果から、"
                        "日本語の文章でキャラの核、共通点、差分を整理してください。"
                        "キー名やenum値だけはスキーマどおりにしてください。\n"
                        + json.dumps(
                            [
                                {"image": i, "traits": obs}
                                for i, obs in enumerate(observations, 1)
                            ], ensure_ascii=False,
                        )
                    )},
                ], "comfy_character_intersection", intersection_schema(),
            )
            analysis = repair_model_analysis(observations, combined)
            if analysis.get("warnings"):
                info(
                    f"キャラ特徴: LLMの形式違い {len(analysis['warnings'])}件を "
                    "除外または補正しました（結果画面で確認できます）"
                )
            return analysis
        finally:
            self.unload_selected(instance_id, info, label="LM Studio: キャラ特徴抽出後に選択モデルをアンロード")

    def revise_character_description(
        self, current: str, instruction: str,
        progress: Callable[[str], None] | None = None,
    ) -> str:
        """Apply a user's Japanese editing request to the draft, without images.

        The result is an unapproved suggestion. GUI keeps human confirmation
        mandatory; this call never modifies the saved character sheet.
        """
        from .character_refs import normalize_approved

        original = normalize_approved(current)
        if (
            not isinstance(instruction, str)
            or not instruction.strip()
            or len(instruction.strip()) > 1200
        ):
            raise OrchestratorError("修正指示は1～1200文字で入力してください")
        if (
            not isinstance(self.model, str) or not self.model.strip()
            or self.model == "SELECT_IN_GUI"
        ):
            raise OrchestratorError("LM Studioモデルを選択してください")
        # No visual reference is used in this text-only revision.
        self._has_visual_input = False
        instance_id = None
        try:
            if progress:
                progress("LM Studio: 自然文の修正指示を適用中")
            instance_id = self._ensure_loaded()
            payload = {
                "model": instance_id,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a careful Japanese-language editor for a "
                            "character design description that will be reviewed "
                            "by a human before image generation. The input is "
                            "an existing user-editable character description plus "
                            "a new editing instruction, not new image evidence. "
                            "Follow the user's editing instruction precisely. "
                            "Preserve all unspecified traits and their meanings; "
                            "remove only what was asked to remove. Never fabricate "
                            "new visual evidence, anatomy or character details. "
                            "Do not change the character or invent another outfit. "
                            "Write concise, natural Japanese sentences, NOT "
                            "Danbooru tags, keyword lists, English prompts, "
                            "markdown, bullet labels or commentary. If the user "
                            "asks to replace an old detail, remove the old detail "
                            "rather than listing contradictory details. "
                            "Return only JSON according to the schema."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps({
                            "current_description": original,
                            "edit_instruction": instruction.strip(),
                        }, ensure_ascii=False),
                    },
                ],
                "stream": False,
                "temperature": 0,
                "max_tokens": self.settings.get("max_tokens", 4096),
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "comfy_character_revision_ja",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "description_ja": {
                                    "type": "string", "minLength": 1,
                                    "maxLength": 3000,
                                },
                            },
                            "required": ["description_ja"],
                            "additionalProperties": False,
                        },
                    },
                },
            }
            answer = read_json_reply(
                _request(self.settings, "/v1/chat/completions", payload),
                "キャラ説明の自然文修正",
            )
            return normalize_approved(answer.get("description_ja"))
        finally:
            self.unload_selected(instance_id, progress, label="LM Studio: キャラ説明の修正後にモデルをアンロード")
