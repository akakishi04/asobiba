"""Offline tests of H3-only prompt profiles, settings and saved history."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comfy_orchestrator import core, gui, lmstudio, prompt_profiles as pp
from comfy_orchestrator.history import HistoryStore

ROOT = Path(__file__).resolve().parents[1]


class Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class H3ProfileTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(ROOT / "config.example.json")
        self.workflows = {core.H3_I2V_ID: self.config["workflows"][core.H3_I2V_ID]}

    def test_default_and_five_distinct_profiles(self):
        self.assertEqual(self.config["llm"]["h3_prompt_profile"], pp.H3_PROFILE_ILLUSTRATION)
        self.assertEqual(len(pp.H3_PROFILES), 5)
        self.assertEqual(set(pp.H3_PROFILES), set(pp.H3_LABEL_TO_PROFILE.values()))
        systems = [pp.apply_h3_profile("base", self.workflows, key) for key in pp.H3_PROFILES]
        self.assertEqual(len(set(systems)), 5)
        self.assertEqual(systems[0], "base")

    def test_h3_guidance_does_not_leak_into_other_workflows(self):
        for key, entry in self.config["workflows"].items():
            if key == core.H3_I2V_ID:
                continue
            for profile in pp.H3_PROFILES:
                self.assertEqual(pp.apply_h3_profile("base", {key: entry}, profile), "base")
        with self.assertRaises(ValueError):
            pp.apply_h3_profile("base", self.workflows, "invalid")

    def test_existing_config_migrates_without_overwriting_explicit_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
            cfg["llm"].pop("h3_prompt_profile")
            path.write_text(json.dumps(cfg), encoding="utf-8")
            with patch.object(gui, "CONFIG", path):
                migrated = gui.bootstrap_config()
                self.assertEqual(migrated["llm"]["h3_prompt_profile"], pp.DEFAULT_H3_PROFILE)
                migrated["llm"]["h3_prompt_profile"] = pp.H3_PROFILE_ACTION
                path.write_text(json.dumps(migrated), encoding="utf-8")
                self.assertEqual(gui.bootstrap_config()["llm"]["h3_prompt_profile"], pp.H3_PROFILE_ACTION)

    def test_invalid_config_is_rejected(self):
        # Place the config beside the shipped workflows via an absolute path
        # only for the early profile-validation failure; no files are modified.
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
            cfg["llm"]["h3_prompt_profile"] = "not-a-profile"
            path.write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaisesRegex(core.OrchestratorError, "h3_prompt_profile"):
                core.load_config(path)

    def test_lmstudio_uses_selected_policy_without_changing_schema_or_lifecycle(self):
        answer = {"workflow_id": core.H3_I2V_ID, "parameters": {"positive_prompt": "Her hair moves gently."}}
        def interpret(profile):
            calls = []
            logs = []
            settings = dict(self.config["llm"], model="local-test", h3_prompt_profile=profile,
                            h3_prompt_format="legacy", send_reference_to_llm=False, _h3_duration_seconds=10.125)
            def request(_settings, route, payload=None):
                calls.append((route, payload))
                if route == "/v1/chat/completions":
                    return {"choices": [{"message": {"content": json.dumps(answer)}}]}
                if route == "/api/v1/models/unload":
                    return {"instance_id": "test"}
                raise AssertionError(route)
            with patch.object(lmstudio.LMStudio, "_ensure_loaded", return_value="test"), patch.object(
                lmstudio, "_request", side_effect=request
            ):
                result = lmstudio.LMStudio(settings).interpret(
                    "髪だけ揺れる", self.workflows, Path("not-read-by-text-only-llm.png"), progress=logs.append
                )
            self.assertEqual(result, answer)
            self.assertEqual([route for route, _ in calls], ["/v1/chat/completions", "/api/v1/models/unload"])
            self.assertIn("H3プロンプト: " + pp.H3_PROFILE_LABELS[profile], logs)
            return calls[0][1]
        baseline = interpret(pp.H3_PROFILE_GENERAL)
        self.assertNotIn("ILLUSTRATION PRESERVATION", baseline["messages"][0]["content"])
        for profile, marker in (
            (pp.H3_PROFILE_ILLUSTRATION, "ILLUSTRATION PRESERVATION"),
            (pp.H3_PROFILE_CEL, "2D CEL ANIMATION"),
            (pp.H3_PROFILE_MICROMOTION, "LIVE2D-LIKE MICRO-MOTION"),
            (pp.H3_PROFILE_ACTION, "ACTION ANIMATION"),
        ):
            with self.subTest(profile=profile):
                actual = interpret(profile)
                self.assertIn(marker, actual["messages"][0]["content"])
                self.assertIn("Explicit user directions take precedence", actual["messages"][0]["content"])
                self.assertIn("Host video duration:", actual["messages"][1]["content"])
                self.assertEqual(actual["response_format"], baseline["response_format"])
                self.assertEqual(actual["temperature"], baseline["temperature"])
                self.assertEqual(actual["max_tokens"], baseline["max_tokens"])

    def test_history_restores_profile_and_old_history_remains_unlabeled(self):
        with tempfile.TemporaryDirectory() as folder:
            store = HistoryStore(Path(folder))
            video = store.outputs / "clip.mp4"
            video.write_bytes(b"video")
            source = Path(folder) / "source.png"
            source.write_bytes(b"image")
            params = dict(self.workflows[core.H3_I2V_ID]["defaults"],
                          positive_prompt="Recorded original prompt.", seed=7)
            def record(profile, prompt_id):
                return store.record(
                    prompt_id=prompt_id, workflow_id=core.H3_I2V_ID, kind="i2v",
                    request_text="髪を揺らす", parameters=params, images=[video],
                    reference_image=source, prompt_profile=profile,
                )
            new = record(pp.H3_PROFILE_MICROMOTION, "new")
            old = record(None, "old")
            for saved, expected in ((new, pp.H3_PROFILE_MICROMOTION), (old, pp.H3_PROFILE_GENERAL)):
                entry = store.get(saved.id)
                info = gui.history_prompt_details(entry)
                self.assertEqual(info["profile"], saved.prompt_profile)
                self.assertEqual(info["positive_prompt"], params["positive_prompt"])
                state = SimpleNamespace(
                    config=self.config, prompt=Mock(), workflow=Var(), reference_image=Var(),
                    mask_image=Var(), pose_image=Var(), composition_image=Var(), pose_mode=Var(),
                    width=Var(), height=Var(), steps=Var(), cfg=Var(), denoise=Var(), seed=Var(),
                    h3_size=Var(), h3_duration=Var(), h3_profile=Var(), status=Var(),
                    _one_history=lambda: entry, _update_generation_controls=Mock(), _log=Mock(),
                )
                gui.Application._restore_selected_history(state)
                self.assertEqual(state.h3_profile.get(), pp.H3_PROFILE_LABELS[expected])
                self.assertEqual(state.seed.get(), "7")
            self.assertIsNone(store.get(old.id).prompt_profile)


if __name__ == "__main__":
    unittest.main()
