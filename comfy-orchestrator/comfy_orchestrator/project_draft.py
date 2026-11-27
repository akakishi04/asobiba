"""Editable continuous-video draft and revision/action guards, independent of Tk."""
from __future__ import annotations

from dataclasses import dataclass

from .long_video_plan import project_cut_lengths, first_changed_cut
from .parameters import OrchestratorError
from .h3_prompt import FORMAT as H3_OFFICIAL_FORMAT
from .timeline import validate_cut_frames, validate_prompt_plan


@dataclass(frozen=True)
class ProjectAction:
    action: str
    prompt_plan: dict
    cut_frames: list[int]
    regenerate_from: int | None = None


class ProjectDraft:
    """The persisted manifest is immutable until an action creates a revision."""
    def __init__(self, manifest):
        self.manifest = manifest
        self.original = manifest.get("prompt_plan")
        self.original_cuts = project_cut_lengths(manifest)
        self.cuts = list(self.original_cuts)
        self.common = self.original["common"] if self.original else ""
        self.parts = list(self.original["segments"]) if self.original else []
        self.current = 0
        self.selected = (0,)

    def selected_indices(self):
        # The current row remains the single-cut editor anchor. Older callers
        # can still set current directly without inheriting a stale selection.
        if self.current not in self.selected:
            return (self.current,)
        return self.selected

    def select_cuts(self, indices, focus=None):
        selected = tuple(sorted({i for i in indices if 0 <= i < len(self.cuts)}))
        if not selected:
            selected = (self.current,)
        if focus in selected:
            self.current = focus
        elif self.current not in selected:
            self.current = selected[0]
        self.selected = selected

    def plan(self):
        plan = {"common": self.common.strip(), "segments": [p.strip() for p in self.parts]}
        if self.original and self.original.get("format") == H3_OFFICIAL_FORMAT:
            plan["format"] = H3_OFFICIAL_FORMAT
        return plan

    def changed_from(self):
        if self.original is None:
            return None
        return first_changed_cut(self.manifest, self.plan(), self.cuts)

    def dirty(self):
        return self.changed_from() is not None

    def valid_prefix(self):
        changed = self.changed_from()
        return min(len(self.manifest["segments"]), changed if changed is not None else len(self.cuts))

    def action(self, name, regenerate=False):
        if self.original is None:
            if name not in ("generate_join", "join"):
                raise OrchestratorError("旧形式は従来の再開・結合のみ対応します")
            return ProjectAction(name, {}, self.cuts)
        approved = validate_prompt_plan(self.plan(), len(self.cuts))
        if self.cuts != self.original_cuts:
            validate_cut_frames(self.cuts)
        if name == "join" and (self.dirty() or self.valid_prefix() != len(self.cuts)):
            raise OrchestratorError("変更のない全生成済みカットだけを結合できます")
        return ProjectAction(name, approved, list(self.cuts), self.current if regenerate else None)

    def accept_prompt_result(self, run_id, cuts, result):
        """Worker results may only update the exact draft they were derived from."""
        d = self
        if (d.manifest["run_id"] != run_id or d.current != result["index"]
                or d.cuts != cuts or d.plan() != result["before"]):
            return False
        after = result["after"]
        if len(after["segments"]) != len(d.parts):
            return False
        before = result["before"]
        targets = result.get("rewritten_indices")
        if targets is not None:
            if tuple(targets) != d.selected_indices() or after["common"] != before["common"]:
                return False
        allowed = set(targets) if targets is not None else {d.current}
        if any(text != before["segments"][i] for i, text in enumerate(after["segments"]) if i not in allowed):
            return False
        d.common = after["common"]
        d.parts[:] = after["segments"]
        return True


def available_project_actions(draft, *, enabled, pending=False, missing_clips=()):
    d = draft
    active = enabled and d is not None
    editable = active and d.original is not None and not pending
    single = active and len(d.selected_indices()) == 1
    return {"save": editable, "generate": editable, "regenerate": editable and single,
            "generate_join": active and not pending,
            "join": active and not pending and d.valid_prefix() == len(d.cuts) and not d.dirty() and not missing_clips,
            "preview": single and d.current < len(d.manifest["segments"])}
