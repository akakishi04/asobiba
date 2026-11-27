"""Japanese natural-language character descriptions, without tagging in the editor.

The final image-generation planner still translates user-approved Japanese
features into appropriate model-specific English visual tags.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import character_refs, character_repair, core, lmstudio
from comfy_orchestrator.character_ui import CharacterReferenceWindow


def _observed(**extras):
    fields = {key: "不明" for key in character_refs.OBSERVATION_FIELDS}
    fields.update({
        "hair_color": "黒髪",
        "hair_style": "後ろに向かって丸みを帯びるショートボブ",
        "facial_geometry": "丸い頬と細い顎が見える",
    })
    fields.update(extras)
    return fields


def _hypothesis(support=(1, 2), conflict=(), confidence="medium"):
    return {
        "aspect": "face",
        "description": "丸みのある頬と小さな顎が印象的で、柔らかい顔立ちをしている",
        "supporting_images": list(support),
        "conflicting_images": list(conflict),
        "confidence": confidence,
        "rationale": "角度の異なる2枚でも頬と顎の形が似ているため",
    }


def _synthesis():
    return {
        "common": [
            {"feature": "hair_color", "value": "黒色", "images": [1, 2]},
            {"feature": "hair_style", "value": "短いボブ", "images": [1, 2]},
        ],
        "candidates": [
            {"feature": "eye_color", "value": "青色", "images": [1]},
        ],
        "variable": [
            {"feature": "outfit", "details": "1枚目は制服、2枚目は私服"},
        ],
        "uncertain": [
            {"feature": "body", "details": "全身の体格は確認できない"},
        ],
        "identity_hypotheses": [_hypothesis()],
    }


class JapaneseDraftTests(unittest.TestCase):
    def test_editable_draft_uses_japanese_sentences_and_not_tag_notation(self):
        result = character_refs.normalize_analysis(
            [_observed(), _observed()], _synthesis(),
        )
        draft = character_refs.suggested_traits(result)
        self.assertEqual(draft, (
            "丸みのある頬と小さな顎が印象的で、柔らかい顔立ちをしている。\n"
            "髪色は黒色。\n"
            "髪型・前髪は短いボブ。"
        ))
        self.assertNotIn("hair_color", draft)
        self.assertNotIn("1girl", draft)
        self.assertNotIn("制服", draft)
        self.assertNotIn("青色", draft)
        self.assertEqual(character_refs.normalize_approved(draft), draft)

    def test_evidence_is_labelled_japanese_and_skips_unseen_fields(self):
        result = character_refs.normalize_analysis(
            [_observed(), _observed()], _synthesis(),
        )
        report = character_refs.format_evidence(result)
        self.assertIn("キャラの核", report)
        self.assertIn("丸みのある頬と小さな顎", report)
        self.assertIn("確信度（推定）", report)
        self.assertIn("支持2/2", report)
        self.assertIn("青色 (1/2, 画像1)", report)
        self.assertIn("1枚目は制服、2枚目は私服", report)
        self.assertNotIn("体格: 不明", report)

    def test_contradiction_is_not_inserted_into_japanese_draft(self):
        broken = _synthesis()
        broken["identity_hypotheses"] = [
            _hypothesis(support=(1, 2), conflict=(3,), confidence="high"),
        ]
        broken["common"] = []
        result = character_refs.normalize_analysis(
            [_observed(), _observed(), _observed()], broken,
        )
        self.assertEqual(character_refs.suggested_traits(result), "")
        self.assertIn("反証 (画像3)", character_refs.format_evidence(result))

    def test_long_extraction_draft_does_not_exceed_editor_limit(self):
        long_description = "丸みのある顔立ちで目元が柔らかい" * 18
        synth = _synthesis()
        synth["identity_hypotheses"] = [
            {**_hypothesis(), "aspect": "face",
             "description": long_description[:340],
             "rationale": "双方の画像に見られる造形"}
        ]
        synth["common"] = [
            {"feature": "other", "value": "細かな意匠" * 25,
             "images": [1, 2]}
            for _ in range(40)
        ]
        result = character_refs.normalize_analysis(
            [_observed(), _observed()], synth,
        )
        draft = character_refs.suggested_traits(result)
        self.assertLessEqual(len(draft), character_refs.MAX_APPROVED_CHARS)
        self.assertFalse(draft.endswith("途中"))
        self.assertEqual(character_refs.normalize_approved(draft), draft)

    def test_old_user_confirmed_english_text_is_not_retranslated_or_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            refs = []
            for i in range(2):
                path = root / f"{i}.png"
                path.write_bytes(b"png")
                refs.append(path)
            analysis = character_refs.normalize_analysis(
                [_observed(), _observed()], _synthesis(),
            )
            character_refs.save_character_sheet(
                root, tuple(refs), analysis, "short black bob, blue eyes",
            )
            saved = character_refs.load_character_sheet(root)
            self.assertEqual(saved[2], "short black bob, blue eyes")

    def test_unknown_japanese_observations_are_not_used_as_identity(self):
        analysis = character_repair.repair_model_analysis(
            [_observed(), _observed()],
            {
                "common": [
                    {"feature": "hair_color", "value": "不明", "images": [1, 2]},
                    {"feature": "hair_style", "value": "短いボブ", "images": [1, 2]},
                ],
                "candidates": [], "variable": [], "uncertain": [],
                "identity_hypotheses": [],
            },
        )
        self.assertEqual(
            [item["value"] for item in analysis["common"]], ["短いボブ"]
        )
        self.assertEqual(
            character_refs.suggested_traits(analysis), "髪型・前髪は短いボブ。"
        )
        self.assertTrue(any("不明情報" in msg for msg in analysis["warnings"]))

    def test_gui_editor_explicitly_asks_for_japanese_prose(self):
        import inspect
        text = inspect.getsource(CharacterReferenceWindow.__init__)
        self.assertIn("日本語の文章で自由に修正", text)
        self.assertIn("修正内容を確定", text)

    def test_local_vlm_receives_japanese_only_content_instructions(self):
        with tempfile.TemporaryDirectory() as folder:
            sources = []
            for i in range(2):
                path = Path(folder) / f"reference{i}.png"
                path.write_bytes(b"fake-image")
                sources.append(path)
            answers = [_observed(), _observed(), _synthesis()]
            requests = []

            def fake_request(_settings, route, payload=None):
                requests.append((route, payload))
                if route == "/v1/chat/completions":
                    return {
                        "choices": [{
                            "message": {"content": json.dumps(answers.pop(0), ensure_ascii=False)}
                        }],
                    }
                if route == "/api/v1/models/unload":
                    return {"instance_id": "model"}
                raise AssertionError(route)

            with patch.object(
                lmstudio.LMStudio, "_ensure_loaded", return_value="model"
            ), patch.object(lmstudio, "_request", side_effect=fake_request):
                result = lmstudio.LMStudio({
                    "model": "local-japanese-vlm", "unload_after_inference": True,
                }).analyze_character_references(sources)
        self.assertEqual(len(requests), 4)
        first_system = requests[0][1]["messages"][0]["content"]
        final_system = requests[2][1]["messages"][0]["content"]
        self.assertIn("NATURAL JAPANESE", first_system)
        self.assertIn("natural, readable", final_system)
        self.assertIn("schema-defined English", final_system)
        self.assertEqual(
            result["identity_hypotheses"][0]["description"],
            "丸みのある頬と小さな顎が印象的で、柔らかい顔立ちをしている",
        )
        self.assertIn("髪色は黒色。", character_refs.suggested_traits(result))

    def test_generation_llm_can_consume_japanese_character_sheet_directly(self):
        config = core.load_config(
            Path(__file__).resolve().parents[1] / "config.example.json"
        )
        workflows = {
            "wai_t2i_basic": config["workflows"]["wai_t2i_basic"],
        }
        requests = []

        def fake_request(_settings, route, payload=None):
            requests.append((route, payload))
            if route == "/v1/chat/completions":
                return {"choices": [{"message": {"content": json.dumps({
                    "workflow_id": "wai_t2i_basic",
                    "parameters": {"positive_prompt": "black bob, round face, blue eyes"},
                })}}]}
            if route == "/api/v1/models/unload":
                return {"instance_id": "model"}
            raise AssertionError(route)

        with patch.object(
            lmstudio.LMStudio, "_ensure_loaded", return_value="model"
        ), patch.object(lmstudio, "_request", side_effect=fake_request):
            lmstudio.LMStudio({
                **config["llm"], "model": "local-model",
            }).interpret(
                "新しい衣装で立っている", workflows, None,
                character_traits="髪色は黒色。丸い顔立ちで、髪は短いボブ。",
            )
        user_message = requests[0][1]["messages"][1]["content"]
        self.assertIn("髪色は黒色。", user_message)
        self.assertIn("新しい衣装で立っている", user_message)



class NaturalLanguageRevisionTests(unittest.TestCase):
    def test_text_only_japanese_revision_and_model_unload(self):
        calls = []

        def fake_request(_settings, route, payload=None):
            calls.append((route, payload))
            if route == "/v1/chat/completions":
                return {"choices": [{"message": {"content": json.dumps({
                    "description_ja": "頬に丸みがあり、黒いショートボブの髪型をしている。",
                }, ensure_ascii=False)}}]}
            if route == "/api/v1/models/unload":
                return {"instance_id": "revise-model"}
            raise AssertionError(route)

        with patch.object(
            lmstudio.LMStudio, "_ensure_loaded", return_value="revise-model"
        ), patch.object(lmstudio, "_request", side_effect=fake_request):
            result = lmstudio.LMStudio({
                "model": "local", "unload_after_inference": True,
            }).revise_character_description(
                "頬に丸みがある。制服を着た黒髪の人物。",
                "制服の説明を消して、髪型をショートボブと書き直して",
            )
        self.assertEqual(
            result, "頬に丸みがあり、黒いショートボブの髪型をしている。",
        )
        self.assertEqual([name for name, _ in calls], [
            "/v1/chat/completions", "/api/v1/models/unload",
        ])
        payload = calls[0][1]
        self.assertEqual(
            payload["response_format"]["json_schema"]["name"],
            "comfy_character_revision_ja",
        )
        self.assertIn("制服の説明を消して", payload["messages"][1]["content"])
        self.assertNotIn("image_url", payload["messages"][1]["content"])

    def test_invalid_revision_instruction_is_rejected_before_loading(self):
        local = lmstudio.LMStudio({"model": "local"})
        for instruction in ("", " ", "あ" * 1201, None):
            with self.subTest(instruction=instruction):
                with patch.object(local, "_ensure_loaded") as load:
                    with self.assertRaises(core.OrchestratorError):
                        local.revise_character_description(
                            "髪は黒い。", instruction,
                        )
                    load.assert_not_called()

    def test_empty_model_revision_is_rejected_and_unloaded(self):
        calls = []
        def fake_request(_settings, route, payload=None):
            calls.append(route)
            if route == "/v1/chat/completions":
                return {"choices": [{"message": {"content": '{"description_ja":""}'}}]}
            if route == "/api/v1/models/unload":
                return {"instance_id": "local"}
            raise AssertionError(route)
        with patch.object(
            lmstudio.LMStudio, "_ensure_loaded", return_value="local"
        ), patch.object(lmstudio, "_request", side_effect=fake_request):
            with self.assertRaises(core.OrchestratorError):
                lmstudio.LMStudio({
                    "model": "local", "unload_after_inference": True,
                }).revise_character_description("髪は黒い。", "髪を短くして")
        self.assertEqual(calls[-1], "/api/v1/models/unload")

    def test_revision_result_stays_unconfirmed_until_explicit_action(self):
        import inspect
        from comfy_orchestrator import gui
        source = inspect.getsource(CharacterReferenceWindow.finish_revision)
        self.assertIn('self.editor.insert("1.0", revised_text)', source)
        self.assertNotIn("self.on_confirm(", source)
        self.assertIn(
            "character_revision_done",
            inspect.getsource(gui.Application._build_event_router),
        )

if __name__ == "__main__":
    unittest.main()
