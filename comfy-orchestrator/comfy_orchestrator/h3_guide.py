"""Native H3 multi-frame conditioning without third-party ComfyUI nodes."""
from __future__ import annotations

import copy

from .parameters import OrchestratorError

GUIDE_LENGTHS = (5, 22)


def validate_guide_inputs(images):
    """The standard reference image is frame zero; these are the remaining frames."""
    if not isinstance(images, (list, tuple)) or len(images) not in (0, 4, 21):
        raise OrchestratorError("H3ガイドには先頭画像と合わせて5または22フレームが必要です")
    if any(image is None for image in images):
        raise OrchestratorError("H3ガイド画像が不足しています")
    return tuple(images)


def prepare_guide_workflow(template, following_names):
    """Replace the single-frame anchor with an ordered native IMAGE batch.

    MiniMaxH3AddGuide appends an encoded clip to minimax_keyframes. Do not
    retain the original first_frame keyframe at the same position.
    The existing LoadImage remains the first member of the guide batch.
    """
    names = validate_guide_inputs(following_names)
    if not names:
        return template
    if any(not isinstance(name, str) or not name for name in names):
        raise OrchestratorError("H3ガイド画像のアップロード名が不正です")
    graph = copy.deepcopy(template)
    cond = graph.get("104", {})
    inputs = cond.get("inputs", {})
    guider = graph.get("16", {})
    sampler = graph.get("14", {})
    first = graph.get("114", {})
    if (cond.get("class_type") != "MiniMaxH3ImageToVideo"
            or inputs.get("first_frame") != ["114", 0]
            or "last_frame" in inputs
            or inputs.get("vae") != ["11", 0]
            or first.get("class_type") != "LoadImage"
            or graph.get("11", {}).get("class_type") != "VAELoader"
            or guider.get("class_type") != "BasicGuider"
            or guider.get("inputs", {}).get("conditioning") != ["104", 0]
            or sampler.get("class_type") != "SamplerCustomAdvanced"
            or sampler.get("inputs", {}).get("latent_image") != ["104", 1]):
        raise OrchestratorError("H3ガイド接続には標準の開始フレーム用ワークフローが必要です")
    if inputs["length"] < len(names) + 1:
        raise OrchestratorError("H3ガイドが生成フレーム数を超えています")

    number = 1000

    def add(class_type, **fields):
        nonlocal number
        while str(number) in graph:
            number += 1
        node_id = str(number)
        number += 1
        graph[node_id] = {"class_type": class_type, "inputs": fields}
        return [node_id, 0]

    images = [["114", 0]] + [add("LoadImage", image=name) for name in names]
    # A balanced tree retains chronological order and avoids repeatedly
    # concatenating a progressively larger batch on every node.
    while len(images) > 1:
        images = [add("ImageBatch", image1=images[i], image2=images[i + 1])
                  if i + 1 < len(images) else images[i]
                  for i in range(0, len(images), 2)]
    inputs.pop("first_frame")
    guide = add("MiniMaxH3AddGuide", positive=["104", 0], latent=["104", 1],
                frame_idx=0, vae=["11", 0], image=images[0])
    guider["inputs"]["conditioning"] = guide
    return graph
