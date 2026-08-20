import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.core.narrative_analyzer import NarrativeAnalyzer
from app.core.scene_matcher import SceneMatcher
from app.database.database import Database
from app.services.ollama_service import OllamaService
from app.services.transcription_service import TranscriptionService
from app.services.visual_analysis_service import VisualAnalysisService


class AiServicesTest(unittest.TestCase):
    def test_transcription_service_is_lazy(self) -> None:
        service = TranscriptionService()
        self.assertIsNone(service._model)
        self.assertEqual(service.device, "cpu")
        self.assertEqual(service.compute_type, "int8")

    def test_parser_accepts_json_fence(self) -> None:
        scenes = NarrativeAnalyzer.parse_scene_response(
            '```json\n{"scenes":[{"start_time":0,"end_time":2,"text":"Oi"}]}\n```'
        )
        self.assertEqual(scenes[0]["text"], "Oi")
        self.assertEqual(scenes[0]["importance"], 0.5)

    def test_parser_rejects_invalid_json(self) -> None:
        with self.assertRaises(ValueError):
            NarrativeAnalyzer.parse_scene_response("not json")

    def test_scene_matcher_basic_text_uses_filename_fallback(self) -> None:
        result = SceneMatcher().match(
            {"text": "urso na floresta"},
            [{"id": 1, "original_name": "casa.mp4"}, {"id": 2, "original_name": "floresta_urso.mp4"}],
        )
        self.assertEqual(result["best_media_id"], 2)

    def test_visual_analysis_is_disabled(self) -> None:
        service = VisualAnalysisService()
        self.assertFalse(service.available)
        with self.assertRaisesRegex(RuntimeError, "Modelo visual"):
            service.analyze_image("missing.png")

    def test_ollama_client_methods_are_local(self) -> None:
        service = OllamaService()
        self.assertEqual(service.base_url, "http://localhost:11434")
        self.assertEqual(service.model, "llama3.2:1b")

    def test_transcription_cache_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = Database(Path(temporary_directory) / "cache.sqlite3")
            project = database.create_project("Cache", "folder")
            cached = database.save_transcription(
                project["id"], 7, "pt", "texto", "base", [{"start": 0, "end": 1, "text": "texto"}]
            )
            loaded = database.get_transcription(project["id"], 7)
            self.assertEqual(loaded["full_text"], cached["full_text"])
            self.assertEqual(len(loaded["segments"]), 1)


if __name__ == "__main__":
    unittest.main()
