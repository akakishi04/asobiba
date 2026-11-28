"""Keep completed prompt review metadata separate from pending generation input."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path

from .image_prompts import KEY as IMAGE_PROMPT_BUNDLE


@dataclass(frozen=True)
class ReviewMetadata:
    request_text: str | None = None
    profile: str | None = None
    character_traits: str | None = None
    character_analysis: dict | None = None
    character_references: tuple[Path, ...] = ()


class ResultReviewState:
    """A result and its own inputs are published as one snapshot, or not at all."""
    def __init__(self):
        self._pending = None
        self._published = None

    def begin(self, *, request_text=None, profile=None, character_traits=None,
              character_analysis=None, character_references=()):
        self._pending = ReviewMetadata(request_text, profile, character_traits,
                                       copy.deepcopy(character_analysis), tuple(character_references))

    def publish(self, result, workflows):
        if self._pending is None:
            raise RuntimeError("No generation metadata is pending")
        if not isinstance(result.get("parameters"), dict):
            self._published = None
        else:
            params = result["parameters"]
            workflow_id = result.get("workflow_id", "")
            meta = self._pending
            self._published = {
                "workflow_id": workflow_id,
                "kind": workflows.get(workflow_id, {}).get("kind"),
                "profile": meta.profile,
                "request_text": meta.request_text,
                "positive_prompt": params.get("positive_prompt", ""),
                "negative_prompt": params.get("negative_prompt"),
                **({IMAGE_PROMPT_BUNDLE: copy.deepcopy(params[IMAGE_PROMPT_BUNDLE])}
                   if IMAGE_PROMPT_BUNDLE in params else {}),
                "seed": params.get("seed"),
                "steps": params.get("steps"),
                "cfg": params.get("cfg"),
                "denoise": params.get("denoise"),
                "character_traits": meta.character_traits,
                "character_analysis": meta.character_analysis,
                "character_references": meta.character_references,
            }
        self._pending = None

    def details(self):
        return copy.deepcopy(self._published)

    def finish(self):
        """Failure, cancellation or non-result tasks must not replace a result."""
        self._pending = None
