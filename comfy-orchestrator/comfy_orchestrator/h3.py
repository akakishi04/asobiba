"""H3 model inventory, options and native graph adapters (no API or GUI)."""
from __future__ import annotations

import copy

from .parameters import OrchestratorError, check_param
from .model_registry import (parse_h3_key, h3_key, registered_h3_turbo,
                             registered_h3_label, h3_key_from_label)
from .h3_performance import (H3_PERFORMANCE_LABELS, H3_SOL_VAE,
                             apply_h3_hybrid_performance, validate_h3_hybrid_steps)


# Host-owned model/LoRA selection. These are intentionally NOT PARAMS or LLM
# bindings: no model-supplied filename or arbitrary LoRA can enter a graph.
H3_MODELS = {
    "int8": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    "w4a8": "minimax_h3_fl2va_pruned_w4a8_mixed.safetensors",
    "gguf_u16g": "minimax_h3_fl2va_pruned_fp8_U16G.gguf",
    "pinkcherry": "PinkCherry_h3_fl2va_pruned_int8_v0.5-alpha.safetensors",
    "s3_raw": "s3_raw_w4a8.safetensors",
}
H3_TURBOS = {
    "off": (None, None),
    "turbo8": ("minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors", 8),
    "turbo4": ("minimax_h3_fl2v_turbo_4step_v1.3_768p_comfyui_bf16.safetensors", 4),
}
# Task-specific distilled adapters: do not apply FL2VA weights to Ref2VA.
# The shifts are the published training shifts for these exact releases.
H3_REF2VA_TURBOS = {
    "off": (None, None, None),
    "turbo8": ("minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors", 8, 6.0),
    "turbo4": ("minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors", 4, 12.0),
}
H3_MODEL_LABELS = {"int8": "INT8 ConvRot", "w4a8": "W4A8 Mixed",
                   "gguf_u16g": "H3 GGUF U16G", "pinkcherry": "PinkCherry INT8 v0.5",
                   "s3_raw": "S3 Raw W4A8"}
H3_TURBO_LABELS = {"off": "OFF", "turbo8": "8 Steps", "turbo4": "4 Steps"}
H3_ENCODERS = {
    "nvfp4": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
    "int4": "qwen3vl_32b_minimax_h3_int4_convrot.safetensors",
    "clipproj4b": "qwen3vl_4b_int8_convrot.safetensors",
}
H3_ENCODER_LABELS = {"nvfp4": "NVFP4 AWQ", "int4": "INT4 ConvRot", "clipproj4b": "4B ClipProj (INT8)"}
H3_CLIPPROJ_MATRIX = "mmh3-4b-ClipProj-v3.1.safetensors"
H3_OPTION_KEYS = frozenset({"h3_model", "h3_turbo", "h3_encoder_device", "h3_encoder_model", "h3_performance"})
H3_REF2VA_PREFIX = "ref2va:"
H3_REF2VA_LABEL = "参考画像 · "
# v1.0 is a hybrid with its eight-step distillation already merged.
H3_HYBRID_FILES = frozenset(name.lower() for name in (
    "10Eros_Max_8stepTurbo_v1.0_hybrid.safetensors",
    "10Eros_Max_8stepTurbo_v1.0_hybrid-int8_HQ.safetensors",
    "10Eros_Max_8stepTurbo_v1.0_hybrid_activation_learned_HQ.safetensors",
    "10Eros_Max_8stepTurbo_v1.0_hybrid_activation_learned_compact_w4w6int8_14.50gb.safetensors",
    "10Eros_Max_8stepTurbo_v1.0_hybrid_activation_learned_Micro.safetensors",
))
H3_HYBRID_PREFIXES = {"hybrid_i2v:": "Hybrid 開始フレーム · ", "hybrid_ref2va:": "Hybrid 参考画像 · "}
H3_HYBRID_DEFAULT_STEPS = 8
H3_REF2VA_DEFAULT_PROMPT = (
    "Use <Picture 1> as a reference for the subject's appearance and visual style. "
    "Create a coherent video with natural motion and independent framing."
)


def h3_hybrid_model_key(filename: str, *, reference_only: bool) -> str | None:
    """Recognize published v1.0 hybrid checkpoints, retaining the exact loader filename."""
    if not isinstance(filename, str) or not filename or len(filename) > 1024:
        return None
    parts = filename.replace("\\", "/").split("/")
    if any(not part or part in (".", "..") or ":" in part or "\x00" in part for part in parts):
        return None
    if parts[-1].lower() not in H3_HYBRID_FILES:
        return None
    return ("hybrid_ref2va:" if reference_only else "hybrid_i2v:") + filename


def h3_hybrid_filename(model) -> str | None:
    manual = parse_h3_key(model)
    if manual is not None:
        return manual[2] if registered_h3_turbo(model) else None
    if not isinstance(model, str):
        return None
    for prefix in H3_HYBRID_PREFIXES:
        if model.startswith(prefix):
            filename = model[len(prefix):]
            if h3_hybrid_model_key(filename, reference_only=prefix == "hybrid_ref2va:") == model:
                return filename
    return None


def h3_hybrid_mode_key(model, *, reference_only):
    """Change conditioning without losing an explicitly registered profile."""
    manual = parse_h3_key(model)
    if manual is not None:
        return h3_key(manual[0], "reference" if reference_only else "opening", manual[2])
    filename = h3_hybrid_filename(model)
    return h3_hybrid_model_key(filename, reference_only=reference_only) if filename is not None else None


def h3_ref2va_model_key(filename: str) -> str | None:
    """Recognize explicit Ref2VA checkpoints listed by the native UNETLoader.

    Keep the real loader filename (including its subfolder) in the history;
    do not guess the filename of a community quantization.
    """
    if not isinstance(filename, str) or not filename or len(filename) > 1024:
        return None
    parts = filename.replace("\\", "/").split("/")
    if any(not part or part in (".", "..") or ":" in part or "\x00" in part for part in parts):
        return None
    basename = parts[-1].lower()
    if not basename.endswith(".safetensors") or "ref2va" not in basename or "fl2va" in basename:
        return None
    return H3_REF2VA_PREFIX + filename


def h3_ref2va_filename(model) -> str | None:
    manual = parse_h3_key(model)
    if manual is not None:
        return manual[2] if manual[1] == "reference" else None
    if isinstance(model, str) and model.startswith("hybrid_ref2va:"):
        return h3_hybrid_filename(model)
    if isinstance(model, str) and model.startswith(H3_REF2VA_PREFIX):
        filename = model[len(H3_REF2VA_PREFIX):]
        if h3_ref2va_model_key(filename) == model:
            return filename
    return None


def h3_model_label(model) -> str:
    manual = registered_h3_label(model)
    if manual is not None:
        return manual
    hybrid = h3_hybrid_filename(model)
    if hybrid is not None:
        return H3_HYBRID_PREFIXES[model.split(":", 1)[0] + ":"] + hybrid
    filename = h3_ref2va_filename(model)
    return H3_REF2VA_LABEL + filename if filename else H3_MODEL_LABELS.get(model, "INT8 ConvRot")


def h3_model_from_label(label: str) -> str | None:
    manual = h3_key_from_label(label)
    if manual is not None:
        return manual
    for prefix, display in H3_HYBRID_PREFIXES.items():
        if label.startswith(display):
            return h3_hybrid_model_key(label[len(display):], reference_only=prefix == "hybrid_ref2va:")
    if label.startswith(H3_REF2VA_LABEL):
        return h3_ref2va_model_key(label[len(H3_REF2VA_LABEL):])
    return next((key for key, value in H3_MODEL_LABELS.items() if value == label), None)


def ensure_h3_reference_prompt(prompt: str) -> str:
    if "<Picture 1>" not in prompt:
        prompt = "Use <Picture 1> as a visual reference, not as the first frame. " + prompt
    check_param("positive_prompt", prompt)
    return prompt


def split_h3_options(parameters: dict, *, enabled: bool) -> tuple[dict, dict]:
    """Separate trusted H3 selections from ordinary API-bound parameters.

    Missing selections preserve the pre-existing graph for old CLI jobs and
    history. FL2VA choices are fixed; Ref2VA choices store the exact filename
    discovered through the native loader and are checked before inference.
    """
    inputs = dict(parameters)
    options = {key: inputs.pop(key) for key in H3_OPTION_KEYS if key in inputs}
    if not options:
        return inputs, {}
    if not enabled:
        raise OrchestratorError("H3モデル・Turbo設定はMiniMax H3専用です")
    model = options.get("h3_model", "int8")
    turbo = options.get("h3_turbo", "off")
    ref_model = h3_ref2va_filename(model)
    hybrid = h3_hybrid_filename(model)
    if not isinstance(model, str) or (model not in H3_MODELS and ref_model is None and hybrid is None and parse_h3_key(model) is None):
        raise OrchestratorError("未対応のH3モデルです")
    if not isinstance(turbo, str) or turbo not in H3_TURBOS:
        raise OrchestratorError("未対応のH3 Turbo設定です")
    if hybrid is not None and turbo != "off":
        raise OrchestratorError("Turbo内蔵モデルには追加Turboを使用できません")
    selected = {"h3_model": model, "h3_turbo": turbo}
    if "h3_performance" in options:
        performance = options["h3_performance"]
        if hybrid is None or not isinstance(performance, str) or performance not in H3_PERFORMANCE_LABELS:
            raise OrchestratorError("未対応のH3高速化設定です")
        selected["h3_performance"] = performance
    if registered_h3_turbo(model):
        if selected.get("h3_performance", "euler_dense") != "euler_dense":
            raise OrchestratorError("登録されたEuler 8stepモデルの高速化方式は固定です")
        selected["h3_performance"] = "euler_dense"
    # Do not inject a new device into old saved jobs or legacy CLI calls.
    if "h3_encoder_device" in options:
        device = options["h3_encoder_device"]
        if not isinstance(device, str) or device not in ("cpu", "default"):
            raise OrchestratorError("H3テキストエンコーダーのデバイスが不正です")
        selected["h3_encoder_device"] = device
    if "h3_encoder_model" in options:
        encoder = options["h3_encoder_model"]
        if not isinstance(encoder, str) or encoder not in H3_ENCODERS:
            raise OrchestratorError("未対応のH3テキストエンコーダーです")
        selected["h3_encoder_model"] = encoder
    return inputs, selected


def prepare_h3_workflow(template: dict, options: dict, parameters: dict | None = None) -> dict:
    """Prepare FL2VA or Ref2VA while retaining the shared H3 parameter bindings."""
    if not options:
        return template
    _, options = split_h3_options(options, enabled=True)
    model = options["h3_model"]
    ref_model = h3_ref2va_filename(model)
    hybrid = h3_hybrid_filename(model)
    performance = options.get("h3_performance", "standard")
    hybrid_steps = H3_HYBRID_DEFAULT_STEPS
    if hybrid is not None and parameters is not None:
        hybrid_steps = parameters.get("steps", H3_HYBRID_DEFAULT_STEPS)
        validate_h3_hybrid_steps(hybrid_steps, performance)
    shift_video = None
    if ref_model is not None:
        lora, steps, shift_video = H3_REF2VA_TURBOS[options["h3_turbo"]]
    else:
        lora, steps = H3_TURBOS[options["h3_turbo"]]
    if steps is not None and parameters is not None and parameters.get("steps") != steps:
        raise OrchestratorError(f"H3 Turboは{steps} Steps固定です")
    graph = copy.deepcopy(template)
    expected = {"6": "UNETLoader", "9": "BasicScheduler", "16": "BasicGuider", "17": "KSamplerSelect"}
    if any(graph.get(node, {}).get("class_type") != kind for node, kind in expected.items()):
        raise OrchestratorError("H3モデル切替には標準のMiniMax H3ワークフローが必要です")
    if any(graph[node]["inputs"].get("model") != ["6", 0] for node in ("9", "16")):
        raise OrchestratorError("H3のモデル接続が標準ワークフローと一致しません")
    if ref_model is not None:
        conditioning = graph.get("104", {})
        inputs = conditioning.get("inputs", {})
        if (conditioning.get("class_type") != "MiniMaxH3ImageToVideo"
                or inputs.get("first_frame") != ["114", 0]
                or inputs.get("clip") != ["13", 0]
                or inputs.get("vae") != ["11", 0]
                or "last_frame" in inputs
                or graph.get("24", {}).get("class_type") != "VAELoader"):
            raise OrchestratorError("Ref2VAには標準H3ワークフローが必要です")
        graph["6"]["inputs"]["unet_name"] = ref_model
        conditioning["class_type"] = "MiniMaxH3ReferenceToVideo"
        inputs["ref_images.ref_image_0"] = inputs.pop("first_frame")
        inputs["audio_vae"] = ["24", 0]
        # Match preserves reference aspect ratio and limits extra reference tokens.
        inputs["ref_image_size"] = "match"
        graph["9"]["inputs"]["scheduler"] = "beta"
        graph["17"]["inputs"]["sampler_name"] = "res_multistep"
    elif hybrid is not None:
        graph["6"]["inputs"]["unet_name"] = hybrid
    elif parse_h3_key(model) is not None:
        graph["6"]["inputs"]["unet_name"] = parse_h3_key(model)[2]
    elif model == "gguf_u16g":
        # The current backend uses legacy VRAM management. U16G needs the
        # compatible molbal fork; do not pass GGUF to the native UNETLoader.
        graph["6"] = {"class_type": "UnetLoaderGGUF",
                      "inputs": {"unet_name": H3_MODELS[model]}}
    else:
        graph["6"]["inputs"]["unet_name"] = H3_MODELS[model]
    if "h3_encoder_device" in options or "h3_encoder_model" in options:
        encoder = graph.get("13", {})
        if encoder.get("class_type") != "CLIPLoader" or not {"device", "clip_name"} <= encoder.get("inputs", {}).keys():
            raise OrchestratorError("H3テキストエンコーダーの標準ノードが見つかりません")
        if "h3_encoder_device" in options:
            encoder["inputs"]["device"] = options["h3_encoder_device"]
        if "h3_encoder_model" in options:
            encoder["inputs"]["clip_name"] = H3_ENCODERS[options["h3_encoder_model"]]
        if options.get("h3_encoder_model") == "clipproj4b":
            conditioning = graph.get("104", {})
            if (conditioning.get("class_type") not in ("MiniMaxH3ImageToVideo", "MiniMaxH3ReferenceToVideo")
                    or conditioning.get("inputs", {}).get("clip") != ["13", 0]):
                raise OrchestratorError("H3 ClipProjには標準の画像→動画ノードが必要です")
            # Stock CLIPLoader manages CPU offload. Do not use the resident
            # all-in-one ClipProj loader, which pins memory on a single GPU.
            encoder["inputs"]["type"] = "krea2"
            node = 901
            while str(node) in graph:
                node += 1
            node = str(node)
            graph[node] = {
                "class_type": "ClipProjApply",
                "inputs": {"clip": ["13", 0], "projection": H3_CLIPPROJ_MATRIX},
            }
            conditioning["inputs"]["clip"] = [node, 0]
    if hybrid is not None:
        apply_h3_hybrid_performance(graph, performance, hybrid_steps)
    if lora is not None:
        # FL2VA keeps the existing sampler. Ref2VA uses its own adapter and
        # Euler + simple with the published video/audio shift for that release.
        node = 900
        while str(node) in graph:
            node += 1
        node = str(node)
        graph[node] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {"model": ["6", 0], "lora_name": lora, "strength_model": 1.0},
        }
        model_output = [node, 0]
        if ref_model is not None:
            shift_node = 902
            while str(shift_node) in graph:
                shift_node += 1
            shift_node = str(shift_node)
            graph[shift_node] = {
                "class_type": "MiniMaxH3SigmaShift",
                "inputs": {"model": model_output, "shift_video": shift_video, "shift_audio": 3.0},
            }
            model_output = [shift_node, 0]
        for target in ("9", "16"):
            graph[target]["inputs"]["model"] = model_output.copy()
        graph["9"]["inputs"].update(scheduler="simple", steps=steps, denoise=1)
        graph["17"]["inputs"]["sampler_name"] = "euler" if ref_model is not None else "res_multistep"
    return graph


def h3_text_model_options(overrides):
    """A Hybrid may use its base mode; pure Ref2VA needs an actual reference."""
    values = dict(overrides or {})
    model = values.get("h3_model")
    if h3_ref2va_filename(model) is not None:
        opening = h3_hybrid_mode_key(model, reference_only=False) if h3_hybrid_filename(model) else None
        if opening is None:
            raise OrchestratorError("参照画像なしのH3生成にはベースモデルまたはHybridを選択してください")
        values["h3_model"] = opening
    return values


def prepare_h3_text_workflow(template: dict, bindings: dict) -> dict:
    """Use the native base node without first/last-frame conditioning.

    Used for text-only single clips and opening cuts of long projects.
    Preserve all model, CLIP, sampler and audio wiring.
    """
    graph = copy.deepcopy(template)
    image = bindings.get("image", {})
    loader = image.get("node")
    cond = graph.get("104", {})
    inputs = cond.get("inputs", {})
    if (cond.get("class_type") != "MiniMaxH3ImageToVideo"
            or not isinstance(loader, str)
            or graph.get(loader, {}).get("class_type") != "LoadImage"
            or image.get("input") != "image"
            or inputs.get("first_frame") != [loader, 0]
            or "last_frame" in inputs):
        raise OrchestratorError("画像なしのH3生成には標準H3の開始フレーム用ワークフローが必要です")
    inputs.pop("first_frame")
    # A custom graph might also use the image as another condition; reject
    # that rather than accidentally leave an unprovided image dependency.
    for node_id, node in graph.items():
        if node_id != loader and any(isinstance(v, list) and len(v) == 2 and v[0] == loader
                                     for v in node.get("inputs", {}).values()):
            raise OrchestratorError("H3ワークフローに別の画像依存が残っています")
    graph.pop(loader)
    return graph
