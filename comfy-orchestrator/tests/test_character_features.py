"""Named text-only character profiles and history recovery."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comfy_orchestrator import core
from comfy_orchestrator.character_features import CharacterFeatureStore, FeatureExistsError
from comfy_orchestrator.character_refs import save_character_sheet, load_character_sheet, validate_character_selection
from comfy_orchestrator.character_ui import CharacterReferenceWindow
from comfy_orchestrator.history import HistoryStore, HistoryError


class CharacterFeatureTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.database = self.root / "data" / "character_features.sqlite3"
        self.store = CharacterFeatureStore(self.database)

    def test_named_library_persists_independent_of_active_sheet(self):
        self.store.save("黒髪の人物", "黒髪のショート。")
        self.store.save("別キャラ", "白い髪。")
        self.assertEqual(load_character_sheet(self.root), ((), None, ""))
        saved = {f.name: f.traits for f in CharacterFeatureStore(self.database).list()}
        self.assertEqual(saved, {"黒髪の人物": "黒髪のショート。", "別キャラ": "白い髪。"})

    def test_requires_explicit_overwrite_and_deletion_is_independent(self):
        self.store.save("Test", "黒い髪。")
        with self.assertRaises(FeatureExistsError):
            self.store.save("test", "青い髪。")
        self.assertEqual(self.store.list()[0].traits, "黒い髪。")
        self.store.save("Test", "青い髪。", overwrite=True)
        save_character_sheet(self.root, (), None, "青い髪。")
        self.assertTrue(self.store.delete("Test"))
        self.assertEqual(self.store.list(), [])
        self.assertEqual(load_character_sheet(self.root), ((), None, "青い髪。"))

    def test_blank_or_overlong_features_are_rejected(self):
        for name, traits in (("", "黒髪"), ("A\nB", "黒髪"), ("人物", ""), ("人物", "あ" * 3001)):
            with self.subTest(name=name, length=len(traits)):
                with self.assertRaises((ValueError, core.OrchestratorError)):
                    self.store.save(name, traits)
        self.assertEqual(self.store.list(), [])

    def test_text_only_sheet_does_not_claim_visual_evidence(self):
        save_character_sheet(self.root, (), None, "短い黒髪。")
        self.assertEqual(load_character_sheet(self.root), ((), None, "短い黒髪。"))
        with self.assertRaises(core.OrchestratorError):
            validate_character_selection((self.root / "unrelated.png",), None, "短い黒髪。")

    def test_text_only_generation_history_roundtrip_and_listing(self):
        store = HistoryStore(self.root)
        output = store.outputs / "test.png"
        output.write_bytes(b"test")
        row = store.record(prompt_id="character-text", workflow_id="wai_t2i_basic",
                           kind="t2i", request_text="portrait",
                           parameters={"positive_prompt": "portrait"}, images=[output],
                           character_traits="短い黒髪。")
        output.unlink()
        recovered = store.get(row.id)
        self.assertEqual(recovered.character_traits, "短い黒髪。")
        self.assertEqual(recovered.character_references, ())
        self.assertIsNone(recovered.character_analysis)
        self.assertEqual(store.list_character_entries()[0].id, row.id)

    def test_loading_never_confirms_or_associates_current_images(self):
        dialog = SimpleNamespace(busy=False, is_open=lambda: True,
                                 editor=Mock(), status=Mock(), _text_only_evidence=Mock(),
                                 _enable_actions=Mock(), on_confirm=Mock(), window=Mock(),
                                 images=[self.root / "failed.png"], analysis={"old": True})
        dialog.editor.get.return_value = ""
        self.assertTrue(CharacterReferenceWindow.load_feature_traits(dialog, "黒髪", name="人物"))
        self.assertTrue(dialog.text_only)
        self.assertIsNone(dialog.analysis)
        self.assertEqual(dialog.images, [self.root / "failed.png"])
        dialog.on_confirm.assert_not_called()
        dialog.editor.get.return_value = "黒髪"
        CharacterReferenceWindow.confirm(dialog)
        dialog.on_confirm.assert_called_once_with((), None, "黒髪")
        dialog.window.destroy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
