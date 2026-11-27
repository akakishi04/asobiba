"""Faithful Japanese prompt review, protected tokens and independent cache.

Planning and prompt editing share this service; it never creates video jobs
or changes a saved English plan.
"""
from __future__ import annotations

import hashlib
import json
import re

from . import h3_prompt as hp
from .prompt_inference import check_cancel, request_validated
from .parameters import OrchestratorError
from .prompt_cache import PromptCache, CACHE_ERRORS

JA_FIELDS = {
    "integrated_multimodal_description": "映像・動作・カメラ・台詞",
    "subject_definitions": "参照対象",
    "summary": "生成概要",
    "retention_analysis": "参照要素の維持・変更",
    "detailed_description": "映像・動作・カメラ・台詞",
    "overall_soundscape": "環境音・効果音",
    "non_diegetic_music": "BGM",
}
TRANSLATION_POLICY = """Translate every sentence of the supplied English H3 prompt into natural Japanese.
This is a faithful review translation, never a summary, enhancement or new prompt.
Do not add, omit, soften, combine or reinterpret visual facts, conditions, actions,
timing, camera, audio, prohibitions or uncertainty. Preserve every protected token
__H3KEEP_0000__ etc. exactly once in the same sequence within its own field.
Return only the requested JSON keys. Use Japanese for the surrounding prose."""
PROTECTED = re.compile(
    r'<d>.*?</d>|<scenetrans>|<cutoff>|<(?:Picture|Subject|Video|Audio) \d+>'
    r'|\[Shot \d+\]|\[(?:reference generation|keyframe completion)(?: \+ (?:reference generation|keyframe completion))*\]'
    r'|\(S\d+(?:,S\d+)*\)|\d{2}:\d{2}\.\d{3}'
    r'|\b(?:fully_preserved|partially_preserved|attribute_transfer|weak_reference|N/A)\b'
    r'|"[^"\n]*"', re.S
)
TOKEN = re.compile(r"__H3KEEP_\d{4}__")
VERSION = "h3_ja_review_v1"
# A maximum-length project has 300 cuts plus its common prompt. Keep
# several such projects in the separate Japanese cache.
TRANSLATION_CACHE_LIMIT = 2048


def _key(kind, source, official):
    encoded = json.dumps([VERSION, kind, bool(official), source.strip()], ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class TranslationCache:
    """Separate local cache; never part of a saved generation plan or its digest."""
    def __init__(self, database):
        self.disk = PromptCache(database, limit=TRANSLATION_CACHE_LIMIT)
        self.memory = {}

    def _load_keys(self, keys):
        # Memoize both hits and misses for this UI session. A worker's put
        # supersedes a miss; setdefault avoids racing with a successful put.
        missing = tuple(dict.fromkeys(key for key in keys if key not in self.memory))
        if not missing:
            return
        try:
            rows = self.disk.get_many(missing)
        except CACHE_ERRORS:
            rows = {}
        for key in missing:
            row = rows.get(key)
            value = row.get("japanese") if isinstance(row, dict) else None
            self.memory.setdefault(key, value if isinstance(value, str) and value.strip() else None)

    def get(self, kind, source, official):
        if not source.strip():
            return ""
        key = _key(kind, source, official)
        self._load_keys((key,))
        return self.memory.get(key)

    def missing(self, plan, index=None, *, indices=None):
        """Untranslated distinct, nonempty texts in playback order.

        index=None covers common plus every cut; an index restricts review
        to the current cut; indices restricts it to multiple selected cuts.
        Identical cut text needs translation only once.
        """
        official = plan.get("format") == hp.FORMAT
        if indices is None:
            indices = range(len(plan["segments"])) if index is None else (index,)
        candidates = [("共通", "common", plan["common"])]
        candidates.extend((f"カット{i+1}", "cut", plan["segments"][i]) for i in indices)
        targets = {}
        for label, kind, source in candidates:
            source = source.strip()
            if source:
                targets.setdefault(_key(kind, source, official), (label, kind, source))
        self._load_keys(targets)
        return [item for key, item in targets.items() if self.memory.get(key) is None]

    def put(self, kind, source, official, japanese):
        if not source.strip():
            return
        key = _key(kind, source, official)
        self.memory[key] = japanese
        try:
            self.disk.put(key, {"japanese": japanese})
        except CACHE_ERRORS:
            # In-session review still works if the optional disk cache fails.
            pass


def protect(text):
    if TOKEN.search(text):
        raise OrchestratorError("翻訳対象に予約済みの保護トークンがあります")
    values = []
    def token(match):
        values.append(match.group())
        return f"__H3KEEP_{len(values)-1:04d}__"
    return PROTECTED.sub(token, text), values


def restore(text, values):
    expected = [f"__H3KEEP_{i:04d}__" for i in range(len(values))]
    if TOKEN.findall(text) != expected:
        raise OrchestratorError("日本語訳で参照・台詞・時刻の保護トークンが変化しました")
    return TOKEN.sub(lambda m: values[int(m.group()[9:13])], text)


def _fields(kind, source, official):
    if kind == "cut" and official:
        return hp.parse_sections(source)[0]
    return {"text": source}


def _jp_text(fields):
    if set(fields) == {"text"}:
        return fields["text"]
    return "\n\n".join(f"【{JA_FIELDS[key]}】\n{value}" for key, value in fields.items())


def _translate(client, instance, kind, source, official, progress, cancel_event):
    if not source.strip():
        return ""
    fields = _fields(kind, source, official)
    masked, tokens = {}, {}
    for key, value in fields.items():
        masked[key], tokens[key] = protect(value)
    limits = {key: min(15000, max(1600, len(value) * 5 + 256)) for key, value in masked.items()}

    def validate(value):
        if set(value) != set(fields):
            raise OrchestratorError("日本語訳の項目が一致しません")
        result = {}
        for key in fields:
            text = value[key]
            if not isinstance(text, str) or not text.strip() or len(text) > limits[key]:
                raise OrchestratorError("日本語訳が空欄または長すぎます")
            result[key] = restore(text.strip(), tokens[key])
        return _jp_text(result)

    return request_validated(client, instance, TRANSLATION_POLICY,
                     json.dumps(masked, ensure_ascii=False), hp.object_schema(fields, limits),
                     "h3_japanese_review", validate, progress, cancel_event,
                     translation_chars=sum(len(value) for value in masked.values()))


class ReviewInterrupted(OrchestratorError):
    """One item failed; earlier validated translations remain cached."""
    def __init__(self, label, completed, total, original):
        self.label = label
        self.completed = completed
        self.total = total
        self.original = original
        super().__init__(str(original))


def translate_pending(client, instance_id, pending, cache, official, progress, cancel_event, *,
                      numbered=False, detailed_progress=False):
    """Translate each distinct pending entry once; do not publish English edits."""
    from .jobs import JobCancellationRequested
    completed = 0
    total = len(pending)
    for label, kind, raw in pending:
        check_cancel(cancel_event)
        title = f"日本語訳 {completed+1}/{total}: {label}" if numbered else f"日本語訳: {label}"
        if progress:
            progress(title)
        try:
            value = _translate(
                client, instance_id, kind, raw, official,
                (lambda line: progress(f"{title} / {line}")) if detailed_progress and progress else progress,
                cancel_event,
            )
        except JobCancellationRequested:
            raise
        except OrchestratorError as exc:
            raise ReviewInterrupted(label, completed, total, exc) from exc
        cache.put(kind, raw, official, value)
        completed += 1
    check_cancel(cancel_event)
    return completed


# Exact source strings for the deterministic image-only plans. These are
# intentionally keyed by English text, so changing a template cannot silently
# attach an obsolete Japanese translation to a new prompt.
_DEFAULT_REVIEW = {
    "Preserve the supplied subject appearance and visual style.": "参照対象の外見と画風を維持する。",
    "Natural coherent motion, without introducing new actions or scenery.": "新たな動作や風景を加えず、自然で一貫した動きを続ける。",
    "Natural quiet ambience and subtle sounds of the visible motion.": "自然で静かな環境音と、映像内の動きに伴うかすかな音。",
    "N/A": "N/A",
    "<Subject 1> is the visible subject or visual motif in <Picture 1>, including its established appearance and style.": "<Subject 1> は <Picture 1> に写る対象または視覚的モチーフで、既存の外見と画風を含む。",
    "[reference generation] Bring <Subject 1> into a coherent naturally moving shot.": "[reference generation] <Subject 1> を、一貫性のある自然な動きのショットとして描く。",
    "<Subject 1> (appears in [Shot 1]): fully_preserved - retain the defined appearance and visual style.": "<Subject 1>（[Shot 1] に登場）：fully_preserved - 定義された外見と画風を維持する。",
    "The reference determines the visual style. [Shot 1] <Subject 1> moves naturally with consistent proportions and coherent framing.": "参照画像が画風を決める。[Shot 1] <Subject 1> は一貫したプロポーションと構図を保ちながら自然に動く。",
    "[Shot 1] The supplied image determines the initial composition, subject and rendering style. Natural coherent movement develops continuously, retaining visible identity and spatial relationships.": "[Shot 1] 参照画像が初期構図、対象、描画スタイルを決める。見えている対象の同一性と空間的な位置関係を維持し、自然で一貫した動きが連続して展開する。",
}


def prepare_plan_review(config, plan, cache, *, client=None, instance_id=None,
                        progress=None, cancel_event=None, release_comfy=True, fixed=False):
    """Best-effort Japanese review of a validated English plan.

    Fresh inference supplies its existing loaded session. Cached English plans
    acquire a session only if translations are missing. Image-only defaults
    have exact built-in translations and never need an LLM. Translation errors
    preserve the English plan and previously cached translations; cancellation
    retains its normal semantics and is not reported as a translation failure.
    """
    if cache is None:
        return
    from .jobs import JobCancellationRequested
    from .lmstudio import LMStudio
    from .model_runtime import release_comfy_before_llm

    def note(line):
        if progress:
            progress(line)

    check_cancel(cancel_event)
    official = plan.get("format") == hp.FORMAT
    pending = cache.missing(plan)
    if not pending:
        return
    if fixed:
        for label, kind, raw in pending:
            check_cancel(cancel_event)
            fields = _fields(kind, raw, official)
            if not all(value in _DEFAULT_REVIEW for value in fields.values()):
                note(f"日本語訳: {label}の固定訳が未登録です。英語計画を保持します")
                continue
            cache.put(kind, raw, official, _jp_text({k: _DEFAULT_REVIEW[v] for k, v in fields.items()}))
        return

    own_session = client is None
    completed = 0
    total = len(pending)
    try:
        if own_session:
            settings = dict(config["llm"], send_reference_to_llm=False)
            if release_comfy:
                release_comfy_before_llm(config["comfyui"], progress=note)
            check_cancel(cancel_event)
            client = LMStudio(settings)
            instance_id = client._ensure_loaded()
        completed = translate_pending(
            client, instance_id, pending, cache, official, note, cancel_event,
            numbered=True, detailed_progress=True,
        )
        note(f"日本語訳完了: {completed}件")
    except JobCancellationRequested:
        raise
    except ReviewInterrupted as exc:
        note(f"日本語訳を中断しました（{exc.completed}/{exc.total}件完了）。英語計画と完了分を保持します: {exc.original}")
    except OrchestratorError as exc:
        note(f"日本語訳を中断しました（{completed}/{total}件完了）。英語計画と完了分を保持します: {exc}")
    finally:
        if own_session and client is not None and instance_id is not None:
            try:
                client.unload_selected(instance_id, note)
            except OrchestratorError as exc:
                note(f"日本語訳後のモデル解放失敗: {exc}")
    check_cancel(cancel_event)
