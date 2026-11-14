"""Versioned T2I prompt-design policies for the installed WAI-Illustrious model.

Only the system instructions change. Workflows, ComfyUI nodes and numeric
generation settings are not modified by the prompt-profile switch.
"""

from __future__ import annotations

T2I_PROFILE_LEGACY = "legacy"
T2I_PROFILE_ILLUSTRIOUS_V2 = "illustrious_v2"
DEFAULT_T2I_PROFILE = T2I_PROFILE_ILLUSTRIOUS_V2
T2I_PROFILES = (T2I_PROFILE_ILLUSTRIOUS_V2, T2I_PROFILE_LEGACY)

T2I_PROFILE_LABELS = {
    T2I_PROFILE_ILLUSTRIOUS_V2: "品質改善 (v2)",
    T2I_PROFILE_LEGACY: "従来 (比較用)",
}
T2I_LABEL_TO_PROFILE = {label: key for key, label in T2I_PROFILE_LABELS.items()}


ILLUSTRIOUS_T2I_V2_INSTRUCTIONS = """
You are also the prompt designer for waiIllustrious SDXL v1.7, an anime illustration
checkpoint using Danbooru-like visual tags. Your primary goal is to translate
the user's Japanese natural-language request into a faithful, coherent and
image-generatable scene, NOT to make the prompt longer.

Think through the scene internally before producing the required JSON:
1. Identify the requested subject, subject count and intended action. Respect
   whether the user wants a portrait, full-body, character design or scenery.
2. Resolve only the details needed for a coherent image: appearance/clothing,
   expression and action, pose and limb placement, camera angle and framing,
   subject placement, setting, and light direction. Preserve specific details
   given by the user, including exact counts, colors, directions and exclusions.
3. Assemble one positive_prompt using concise English comma-separated
   Danbooru-style tags where possible. Prefer this ordering:
   subject count / identity if specified; visible appearance and clothing;
   expression / action / pose; viewpoint / shot scale / composition;
   background and context; physically consistent lighting and shading;
   a few quality/style tags. Use short plain-English clauses ONLY where
   the spatial relationship is too specific for a known tag.
4. Quality: for a polished anime illustration, a small set such as
   "masterpiece, best quality, very aesthetic" can be used. Do NOT
   stack dozens of vague boosters, "4k/8k/ultra HD", or Pony's
   "score_9, score_8_up" tags. Never inject artists, named characters,
   styles, costumes or props unless the user actually requests them.
5. Concrete visual coherence beats generic decoration: anatomically
   plausible visible joints/hands, readable silhouette, hair following
   pose and gravity, fabric folds corresponding to tension and weight,
   highlights and cast shadows consistent with the chosen light source.
   Use these details only when appropriate to what is visibly depicted.
   Do not add anatomical/hand/fabric tags to landscapes or head-only shots.
6. Avoid incompatible tags: conflicting emotions, camera directions,
   lighting conditions, subject counts, ages, duplicate body parts,
   or conflicting outfits. Do not silently change an explicit request to
   fit a default art style or background. Do not introduce random details
   to fill unspecified fields.
7. Negative_prompt should be SHORT and relevant. For an ordinary polished
   illustration a starting point may be "worst quality, low quality, lowres";
   add specific artifact negatives only where appropriate, and do not
   negate any requested content or duplicate every positive tag.
8. The GUI/application is authoritative for width, height, steps, CFG and
   seed. Do not try to tune those fields unless the user explicitly asks
   for a corresponding value and it is allowed by the catalog.

Return ONLY the requested JSON with a valid workflow_id and its supported
parameters, including positive_prompt and an appropriate negative_prompt.
Do not include commentary, markdown, a numbered plan or unrecognized fields.
"""


def is_t2i_context(workflows: dict) -> bool:
    """Do not apply T2I illustration instructions to I2I, pose or inpainting."""
    return bool(workflows) and all(
        isinstance(entry, dict) and entry.get("kind") == "t2i"
        for entry in workflows.values()
    )


def apply_t2i_profile(base_system: str, workflows: dict, profile: str) -> str:
    """Compose an opt-in policy, or reproduce the exact previous system text."""
    if profile not in T2I_PROFILES:
        raise ValueError(f"unsupported T2I prompt profile: {profile!r}")
    if profile == T2I_PROFILE_LEGACY or not is_t2i_context(workflows):
        return base_system
    return base_system + "\n\n" + ILLUSTRIOUS_T2I_V2_INSTRUCTIONS.strip()
