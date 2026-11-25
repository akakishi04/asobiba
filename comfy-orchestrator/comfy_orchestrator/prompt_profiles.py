"""Versioned image-generation and MiniMax H3 video prompt policies.

Only the language-model instructions change. Workflows, ComfyUI nodes and
numeric generation settings are not modified by the profile switches.
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
    """Only use the WAI-Illustrious policy with matching T2I checkpoints.

    A future Qwen/Image or other T2I workflow must not silently inherit
    assumptions about Danbooru tags.
    """
    return bool(workflows) and all(
        isinstance(entry, dict)
        and entry.get("kind") == "t2i"
        and (
            "illustrious" in str(entry.get("description", "")).lower()
            or "wai" in name.lower()
        )
        for name, entry in workflows.items()
    )


def apply_t2i_profile(base_system: str, workflows: dict, profile: str) -> str:
    """Compose an opt-in policy, or reproduce the exact previous system text."""
    if profile not in T2I_PROFILES:
        raise ValueError(f"unsupported T2I prompt profile: {profile!r}")
    if profile == T2I_PROFILE_LEGACY or not is_t2i_context(workflows):
        return base_system
    return base_system + "\n\n" + ILLUSTRIOUS_T2I_V2_INSTRUCTIONS.strip()



# I2I is an EDITING task, not a second T2I scene invention. Keep a separate
# version switch so A/B comparisons do not change T2I policy or node graphs.
I2I_PROFILE_LEGACY = "legacy"
I2I_PROFILE_PRESERVE_EDIT_V1 = "preserve_edit_v1"
DEFAULT_I2I_PROFILE = I2I_PROFILE_PRESERVE_EDIT_V1
I2I_PROFILES = (I2I_PROFILE_PRESERVE_EDIT_V1, I2I_PROFILE_LEGACY)

I2I_PROFILE_LABELS = {
    I2I_PROFILE_PRESERVE_EDIT_V1: "保持重視 (v1)",
    I2I_PROFILE_LEGACY: "従来 (比較用)",
}
I2I_LABEL_TO_PROFILE = {label: key for key, label in I2I_PROFILE_LABELS.items()}


ILLUSTRIOUS_I2I_PRESERVE_EDIT_V1 = """
You are also a conservative image-edit prompt designer for WAI Illustrious
SDXL. This workflow starts from a SOURCE IMAGE. Your job is to implement the
user's requested EDIT, not to create or redesign an unrelated illustration.

Before writing JSON, distinguish internally:
- PRESERVE: subject count and identity, existing composition and crop, camera,
  pose, expression, clothes, background, lighting and colors, unless the user
  explicitly asks to change them.
- EDIT: only the elements and attributes that the user explicitly requests.
  Never change an unaffected element to make the prompt sound more detailed.

Build positive_prompt using concise English Danbooru-like tags, keeping
specific user-provided visual facts and the requested edits central.
For example, "fix hair flow" means more coherent hair strands following
gravity/movement, NOT a different hairstyle, outfit or camera angle.
"Make folds/shadows natural" means fabric tension, folds and light direction
consistent with the source, NOT a new lighting scheme.

IMPORTANT: When the reference image has NOT been shown to the LLM,
do not claim to know its actual appearance. You can request that its
unchanged composition, character and clothing be retained, but NEVER
invent specific pose, clothes, hair, background or light direction.
When an image is visible, rely only on observable facts; an absent or
hidden feature must stay uncertain, not hallucinated.

Keep negative_prompt concise and artifact-focused: quality/lowres and
specific unwanted artifacts, without negating requested elements.
Avoid adding random accessories, named characters, styles, colors,
artists or conflicting quality boosters.

The host controls denoise, seed, steps, CFG and workflow selection.
An edit-strength hint can express risk of deviation, but does not give
permission to override any explicit preservation request. Higher denoise
can change MORE of the source even with a cautious prompt.
Return ONLY valid JSON with positive_prompt, negative_prompt and
supported parameters. Never append explanations or extra schema fields.
""".strip()

ILLUSTRIOUS_INPAINT_EXTRA = """
INPAINT-SPECIFIC: The user painted a mask. Focus the prompt on the requested
correction within that masked region. Areas outside the mask must not be
redesigned. Do not claim to know the mask's exact outline or contents unless
they were explicitly described. The compositing workflow, not the prompt,
enforces protection outside the mask; seams and edges still need care.
""".strip()


def is_i2i_context(workflows: dict) -> bool:
    """Restrict the editing policy to the shipped WAI image-edit workflows."""
    return bool(workflows) and all(
        isinstance(entry, dict)
        and entry.get("kind") in ("i2i", "inpaint")
        and (
            "illustrious" in str(entry.get("description", "")).lower()
            or "wai" in name.lower()
        )
        for name, entry in workflows.items()
    )


def apply_i2i_profile(base_system: str, workflows: dict, profile: str) -> str:
    """Return an unchanged legacy prompt, or conservative image-edit guidance."""
    if profile not in I2I_PROFILES:
        raise ValueError(f"unsupported I2I prompt profile: {profile!r}")
    if profile == I2I_PROFILE_LEGACY or not is_i2i_context(workflows):
        return base_system
    suffix = ILLUSTRIOUS_I2I_PRESERVE_EDIT_V1
    if workflows and all(entry.get("kind") == "inpaint" for entry in workflows.values()):
        suffix += "\n\n" + ILLUSTRIOUS_INPAINT_EXTRA
    return base_system + "\n\n" + suffix


def edit_strength_hint(denoise: float) -> str:
    """Translate the host's actual denoise into a cautious language-only hint."""
    if isinstance(denoise, bool) or not isinstance(denoise, (int, float)):
        raise ValueError("denoise must be numeric")
    if not 0 <= denoise <= 1:
        raise ValueError("denoise must be between 0 and 1")
    if denoise <= 0.40:
        return "preserve-oriented"
    if denoise <= 0.60:
        return "balanced"
    return "transform-oriented"



# H3 accepts natural language and has its own conditioning path, not SDXL tags.
H3_PROFILE_GENERAL = "h3_general_v1"
H3_PROFILE_ILLUSTRATION = "h3_illustration_v1"
H3_PROFILE_CEL = "h3_cel_v1"
H3_PROFILE_MICROMOTION = "h3_micromotion_v1"
H3_PROFILE_ACTION = "h3_action_v1"
DEFAULT_H3_PROFILE = H3_PROFILE_ILLUSTRATION

H3_PROFILE_LABELS = {
    H3_PROFILE_GENERAL: "汎用動画",
    H3_PROFILE_ILLUSTRATION: "イラストの画風維持",
    H3_PROFILE_CEL: "2Dセル画アニメ",
    H3_PROFILE_MICROMOTION: "Live2D風の微動",
    H3_PROFILE_ACTION: "アクションアニメ",
}
H3_PROFILES = tuple(H3_PROFILE_LABELS)
H3_LABEL_TO_PROFILE = {label: key for key, label in H3_PROFILE_LABELS.items()}

# General intentionally preserves the existing H3 behavior for A/B tests.
H3_SHARED_STYLE_INSTRUCTIONS = """
The selected H3 preset is motion and rendering guidance, not additional story
content. Explicit user directions take precedence over preset defaults.
Start from the actual first frame, preserve its identity, composition and
style unless the user requests a change. If the reference was not provided
to the LLM, refer to its existing visual features generically; never invent
specific colors, anatomy, objects or scenery. Describe temporal continuity
in concise natural English sentences, not Danbooru tags or quality keywords.
Do not introduce unsolicited actions, camera moves, scene cuts, dialogue,
music or effects. Maintain the requested audio, language and spoken words.
Fit all motion to the host-specified duration at 24 fps: describe coherent
continuous motion for short/simple requests, and use ordered time beats
only when useful for a requested multi-stage action. Never place an event
beyond the clip's duration. Express preservation and motion constraints
inside positive_prompt; this workflow has no negative_prompt or CFG.
""".strip()

H3_PROFILE_INSTRUCTIONS = {
    H3_PROFILE_ILLUSTRATION: """
ILLUSTRATION PRESERVATION:
Describe the requested motion while explicitly retaining the source
illustration's original linework, line weight, palette, painting texture,
shading style, facial design, hair silhouette, clothing details and background.
Keep them temporally consistent rather than re-rendering them into a different
medium. Maintain the source's intended two-dimensional rendering if present;
do not add realistic skin, photographic lighting, 3D/CGI materials or a new
rendering style. Respect changes that the user actually requests. Keep
unaffected areas visually stable and use a fixed camera unless the user
requests or clearly implies a different camera movement. Do not flatten an
existing painted or painterly style into cel shading.
""".strip(),
    H3_PROFILE_CEL: """
2D CEL ANIMATION:
Describe hand-drawn 2D animation with coherent outlines, defined color areas,
consistent cel-shadow shapes and stable character model proportions.
Use readable key poses, purposeful timing and clear transitions between them
when the requested action benefits from those qualities. Maintain the source
character and scene; adapt rendering toward the selected cel-animation
aesthetic without redesigning them. Avoid unsolicited photorealism, volumetric
3D shading, excessive motion blur, interpolation artifacts or arbitrary
cuts. Do not force choppy motion, a frame-rate change, or a specific era
of animation; retain the host's 24 fps output.
""".strip(),
    H3_PROFILE_MICROMOTION: """
LIVE2D-LIKE MICRO-MOTION:
Use tightly bounded motion in the source illustration. Prioritize requested
subtle motions such as breathing, blinking, gaze, tiny expression changes,
or gentle hair and cloth motion. These are examples, not a mandatory action
list. Keep the framing and background stationary by default, preserve the
original drawing and silhouette, and limit changes in depth, perspective and
body orientation. Keep motion restrained and smooth without unintended zooms,
full-body actions, morphing, or scene changes. If the user requests a loop,
describe motion that can return naturally to the initial pose; do not claim
seamless looping is guaranteed. Explicitly requested larger actions still
take precedence.
""".strip(),
    H3_PROFILE_ACTION: """
ACTION ANIMATION:
Translate the requested action into a continuous, physically readable
sequence of anticipation, weight shift, acceleration, main movement and
follow-through when appropriate. Preserve character identity, anatomy,
silhouette, outfit, spatial orientation and the source's rendering style
through motion. Keep limb trajectories and contacts coherent; use clear
key poses and readable camera framing. Match tempo to the requested action
and available duration. Secondary hair and clothing motion should follow
the main movement naturally. Do not invent additional attacks, explosions,
other characters, camera cuts, speed lines or effects merely to increase
excitement. Use dynamic camera movement only when requested or clearly
implied, and avoid uncontrolled shaking that obscures the action.
""".strip(),
}


def is_h3_context(workflows: dict) -> bool:
    """Apply H3 profiles only to the registered local FL2VA workflow."""
    from .core import H3_I2V_ID

    return set(workflows) == {H3_I2V_ID} and workflows[H3_I2V_ID].get("kind") == "i2v"


def apply_h3_profile(base_system: str, workflows: dict, profile: str) -> str:
    """Keep non-H3 workflows and the general baseline unchanged."""
    if profile not in H3_PROFILES:
        raise ValueError(f"unsupported H3 prompt profile: {profile!r}")
    if not is_h3_context(workflows) or profile == H3_PROFILE_GENERAL:
        return base_system
    return (
        base_system + "\n\n" + H3_SHARED_STYLE_INSTRUCTIONS
        + "\n\n" + H3_PROFILE_INSTRUCTIONS[profile]
    )
