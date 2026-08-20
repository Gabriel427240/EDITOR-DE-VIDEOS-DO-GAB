import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.core.narrative_analyzer import (
    NarrativeAnalysisUnavailable,
    NarrativeAnalyzer,
)
from app.core.scene_matcher import SceneMatcher, SceneMatchingUnavailable
from app.database.database import Database


class NarrativeScenesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database = Database(self.root / "narrative.sqlite3")
        self.project = self.database.create_project("Narrativa", str(self.root / "project"))
        self.database.add_media(
            self.project["id"],
            "narration.wav",
            "narration.wav",
            str(self.root / "narration.wav"),
            "narration",
            {"duration": 25.0, "probe_status": "success"},
        )
        self.analyzer = NarrativeAnalyzer(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def scene(self, start: float, end: float, text: str = "Texto", **values: object) -> dict:
        return {"start_time": start, "end_time": end, "text": text, **values}

    def test_save_and_load_scenes(self) -> None:
        saved = self.analyzer.create_manual_scenes(
            self.project["id"], [self.scene(0, 5)]
        )
        loaded = self.database.get_narrative_scenes(self.project["id"])
        self.assertEqual(len(saved), 1)
        self.assertEqual(loaded[0]["text"], "Texto")

    def test_new_scenes_replace_previous(self) -> None:
        self.analyzer.create_manual_scenes(self.project["id"], [self.scene(0, 5)])
        self.analyzer.create_manual_scenes(self.project["id"], [self.scene(5, 10, "Novo")])
        scenes = self.database.get_narrative_scenes(self.project["id"])
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["text"], "Novo")

    def test_order_is_by_start_time(self) -> None:
        scenes = self.analyzer.create_manual_scenes(
            self.project["id"], [self.scene(10, 15, "B"), self.scene(0, 5, "A")]
        )
        self.assertEqual([scene["text"] for scene in scenes], ["A", "B"])
        self.assertEqual([scene["scene_order"] for scene in scenes], [1, 2])

    def test_negative_start_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "negativo"):
            self.analyzer.create_manual_scenes(self.project["id"], [self.scene(-1, 2)])

    def test_end_must_be_after_start(self) -> None:
        with self.assertRaisesRegex(ValueError, "maior"):
            self.analyzer.create_manual_scenes(self.project["id"], [self.scene(2, 2)])

    def test_overlapping_scenes_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "sobrepor"):
            self.analyzer.create_manual_scenes(
                self.project["id"], [self.scene(0, 10), self.scene(8, 15)]
            )

    def test_default_and_clamped_importance(self) -> None:
        scenes = self.analyzer.create_manual_scenes(
            self.project["id"],
            [self.scene(0, 5), self.scene(5, 10, "Alta", importance=3)],
        )
        self.assertEqual(scenes[0]["importance"], 0.5)
        self.assertEqual(scenes[1]["importance"], 1.0)

    def test_scene_cannot_exceed_narration(self) -> None:
        with self.assertRaisesRegex(ValueError, "ultrapassar"):
            self.analyzer.create_manual_scenes(self.project["id"], [self.scene(20, 26)])

    def test_generate_test_scenes(self) -> None:
        scenes = self.analyzer.generate_test_scenes(self.project["id"])
        self.assertEqual(len(scenes), 3)
        self.assertEqual(scenes[0]["text"], "Cena de teste 1")
        self.assertEqual(scenes[-1]["end_time"], 25.0)

    def test_analyzer_is_unavailable(self) -> None:
        with self.assertRaisesRegex(NarrativeAnalysisUnavailable, "nao esta configurada"):
            self.analyzer.analyze(self.project["id"])

    def test_scene_matcher_is_unavailable(self) -> None:
        with self.assertRaisesRegex(SceneMatchingUnavailable, "nao esta configurada"):
            SceneMatcher().match({}, [])

    def test_semantic_columns_migrate(self) -> None:
        connection = self.database._connect()
        try:
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(media)")}
        finally:
            connection.close()
        self.assertTrue({"semantic_description", "semantic_status"} <= columns)


if __name__ == "__main__":
    unittest.main()
