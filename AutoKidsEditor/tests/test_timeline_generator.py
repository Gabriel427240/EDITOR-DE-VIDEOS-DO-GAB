import tempfile
import unittest
from pathlib import Path

from app.core.timeline_generator import TimelineGenerationError, TimelineGenerator
from app.database.database import Database


class TimelineGeneratorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database = Database(self.root / "timeline.sqlite3")
        self.project = self.database.create_project(
            "Timeline", str(self.root / "project")
        )
        self.generator = TimelineGenerator(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def add_media(self, name: str, media_type: str, duration: float | None = None) -> dict:
        metadata = {"probe_status": "success"}
        if duration is not None:
            metadata["duration"] = duration
        if media_type == "image":
            metadata.update({"width": 1920, "height": 1080})
        return self.database.add_media(
            self.project["id"], name, name, str(self.root / name), media_type, metadata
        )

    def add_standard_visuals(self) -> None:
        self.add_media("video01.mp4", "video", 30)
        self.add_media("imagem01.png", "image")
        self.add_media("video02.mp4", "video", 12)

    def add_narration(self, duration: float = 20) -> dict:
        return self.add_media("narracao.mp3", "narration", duration)

    def test_error_without_narration(self) -> None:
        self.add_standard_visuals()
        with self.assertRaisesRegex(TimelineGenerationError, "narracao"):
            self.generator.generate(self.project["id"])

    def test_error_without_visual_media(self) -> None:
        self.add_narration()
        with self.assertRaisesRegex(TimelineGenerationError, "videos ou imagens"):
            self.generator.generate(self.project["id"])

    def test_duration_matches_narration(self) -> None:
        self.add_narration(20)
        self.add_standard_visuals()
        timeline = self.generator.generate(self.project["id"])
        self.assertAlmostEqual(timeline["duration"], 20)
        self.assertAlmostEqual(timeline["segments"][-1]["timeline_end"], 20)

    def test_image_uses_five_seconds(self) -> None:
        self.add_narration(5)
        self.add_media("imagem.png", "image")
        timeline = self.generator.generate(self.project["id"])
        self.assertAlmostEqual(timeline["segments"][0]["duration"], 5)

    def test_video_does_not_exceed_available_duration(self) -> None:
        self.add_narration(3)
        self.add_media("curto.mp4", "video", 2)
        timeline = self.generator.generate(self.project["id"])
        self.assertLessEqual(timeline["segments"][0]["duration"], 2)
        self.assertLessEqual(timeline["segments"][0]["source_end"], 2)

    def test_long_video_uses_different_source_starts(self) -> None:
        self.add_narration(18)
        self.add_media("longo.mp4", "video", 30)
        timeline = self.generator.generate(self.project["id"])
        starts = [segment["source_start"] for segment in timeline["segments"]]
        self.assertEqual(starts, [0, 6, 12])

    def test_reuse_fills_timeline(self) -> None:
        self.add_narration(20)
        self.add_media("video.mp4", "video", 6)
        timeline = self.generator.generate(self.project["id"])
        self.assertAlmostEqual(timeline["segments"][-1]["timeline_end"], 20)
        self.assertGreater(len(timeline["segments"]), 1)

    def test_alternative_prevents_immediate_same_media(self) -> None:
        self.add_narration(20)
        self.add_media("video.mp4", "video", 30)
        self.add_media("imagem.png", "image")
        timeline = self.generator.generate(self.project["id"])
        for previous, current in zip(timeline["segments"], timeline["segments"][1:]):
            self.assertNotEqual(previous["media_id"], current["media_id"])

    def test_segments_have_no_negative_duration(self) -> None:
        self.add_narration(20)
        self.add_standard_visuals()
        timeline = self.generator.generate(self.project["id"])
        self.assertTrue(all(segment["duration"] > 0 for segment in timeline["segments"]))

    def test_timeline_is_saved(self) -> None:
        self.add_narration(10)
        self.add_standard_visuals()
        timeline = self.generator.generate(self.project["id"])
        saved = self.database.save_timeline(self.project["id"], timeline)
        self.assertEqual(len(saved["segments"]), len(timeline["segments"]))

    def test_new_timeline_replaces_previous(self) -> None:
        self.add_narration(10)
        self.add_standard_visuals()
        first = self.database.save_timeline(
            self.project["id"], self.generator.generate(self.project["id"])
        )
        self.database.save_timeline(
            self.project["id"], self.generator.generate(self.project["id"])
        )
        current = self.database.get_project_timeline(self.project["id"])
        self.assertNotEqual(first["id"], current["id"])
        self.assertEqual(len(current["segments"]), len(first["segments"]))

    def test_segments_are_ordered_and_continuous(self) -> None:
        self.add_narration(20)
        self.add_standard_visuals()
        timeline = self.generator.generate(self.project["id"])
        for index, segment in enumerate(timeline["segments"], start=1):
            self.assertEqual(segment["order"], index)
            if index > 1:
                self.assertEqual(
                    segment["timeline_start"], timeline["segments"][index - 2]["timeline_end"]
                )


if __name__ == "__main__":
    unittest.main()
