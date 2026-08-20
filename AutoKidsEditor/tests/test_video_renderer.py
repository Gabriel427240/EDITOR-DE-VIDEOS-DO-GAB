import json
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from app.database.database import Database
from app.services.media_probe import MediaProbe
from app.services.video_renderer import VideoRenderError, VideoRenderer


@unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg nao esta disponivel")
class VideoRendererTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database = Database(self.root / "renderer.sqlite3")
        self.project_path = self.root / "project"
        self.project = self.database.create_project("Renderer", str(self.project_path))
        self.ffmpeg = shutil.which("ffmpeg")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def add_media(
        self, name: str, media_type: str, path: Path, duration: float | None = None
    ) -> dict:
        metadata = {"probe_status": "success"}
        if duration is not None:
            metadata["duration"] = duration
        if media_type == "video":
            metadata.update({"width": 640, "height": 360, "fps": 30.0, "has_audio": 0})
        return self.database.add_media(
            self.project["id"], name, name, str(path), media_type, metadata
        )

    def save_timeline(self, media: dict, duration: float = 2) -> None:
        self.database.save_timeline(
            self.project["id"],
            {
                "project_id": self.project["id"],
                "duration": duration,
                "segments": [
                    {
                        "order": 1,
                        "media_id": media["id"],
                        "media_type": "video",
                        "source_start": 0.0,
                        "source_end": duration,
                        "timeline_start": 0.0,
                        "timeline_end": duration,
                        "duration": duration,
                    }
                ],
            },
        )

    def create_synthetic_media(self) -> tuple[Path, Path]:
        source_video = self.root / "source.mp4"
        narration = self.root / "narration.wav"
        subprocess.run(
            [
                self.ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=blue:s=640x360:r=30",
                "-t",
                "2",
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(source_video),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                self.ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=1000:sample_rate=48000",
                "-t",
                "2",
                "-c:a",
                "pcm_s16le",
                str(narration),
            ],
            check=True,
            capture_output=True,
        )
        return source_video, narration

    def create_media_file(self, filename: str, input_spec: str, duration: str, output_args: list[str]) -> Path:
        output = self.root / filename
        subprocess.run(
            [self.ffmpeg, "-y", "-f", "lavfi", "-i", input_spec, "-t", duration, *output_args, str(output)],
            check=True,
            capture_output=True,
        )
        return output

    def test_error_without_timeline(self) -> None:
        narration = self.root / "narration.wav"
        narration.write_bytes(b"audio")
        self.add_media("narration.wav", "narration", narration, 2)
        with self.assertRaisesRegex(VideoRenderError, "timeline"):
            VideoRenderer(self.database, self.ffmpeg).render(self.project["id"])

    def test_error_without_narration(self) -> None:
        video = self.root / "video.mp4"
        video.write_bytes(b"video")
        media = self.add_media("video.mp4", "video", video, 2)
        self.save_timeline(media)
        with self.assertRaisesRegex(VideoRenderError, "narracao"):
            VideoRenderer(self.database, self.ffmpeg).render(self.project["id"])

    def test_error_with_missing_media(self) -> None:
        narration = self.root / "narration.wav"
        narration.write_bytes(b"audio")
        self.add_media("narration.wav", "narration", narration, 2)
        missing = self.add_media("missing.mp4", "video", self.root / "missing.mp4", 2)
        self.save_timeline(missing)
        with self.assertRaisesRegex(VideoRenderError, "midias da timeline"):
            VideoRenderer(self.database, self.ffmpeg).render(self.project["id"])
        self.assertEqual(self.database.list_project_renders(self.project["id"])[0]["status"], "error")

    def test_unique_preview_name(self) -> None:
        output = self.project_path / "output"
        output.mkdir(parents=True)
        (output / "preview.mp4").write_bytes(b"one")
        (output / "preview_2.mp4").write_bytes(b"two")
        selected = VideoRenderer._unique_output_path(output / "preview.mp4")
        self.assertEqual(selected.name, "preview_3.mp4")

    def test_real_short_render_and_render_record(self) -> None:
        source_video, narration = self.create_synthetic_media()
        video = self.add_media("source.mp4", "video", source_video, 2)
        self.add_media("narration.wav", "narration", narration, 2)
        self.save_timeline(video)
        render = VideoRenderer(self.database, self.ffmpeg).render(self.project["id"])
        output = Path(render["file_path"])
        self.assertTrue(output.is_file())
        self.assertGreater(output.stat().st_size, 0)
        self.assertEqual(render["status"], "success")
        self.assertFalse((self.project_path / "temp" / "render_").exists())
        metadata = MediaProbe().probe(output)
        self.assertAlmostEqual(metadata["duration"], 2, delta=0.2)
        self.assertEqual(metadata["width"], 1920)
        self.assertEqual(metadata["height"], 1080)
        self.assertTrue(metadata["has_audio"])
        self.assertEqual(len(self.database.list_project_renders(self.project["id"])), 1)

    def test_real_render_with_music_image_and_transitions(self) -> None:
        video_one = self.create_media_file(
            "one.mp4", "color=c=blue:s=640x360:r=30", "2", ["-an", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
        )
        video_two = self.create_media_file(
            "two.mp4", "color=c=green:s=640x360:r=30", "2", ["-an", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
        )
        image = self.create_media_file(
            "story.png", "color=c=red:s=800x600", "1", ["-frames:v", "1", "-y"]
        )
        narration = self.create_media_file(
            "story.wav", "sine=frequency=600:sample_rate=48000", "6", ["-c:a", "pcm_s16le"]
        )
        music = self.create_media_file(
            "music.wav", "sine=frequency=220:sample_rate=48000", "1", ["-c:a", "pcm_s16le"]
        )
        first = self.add_media("one.mp4", "video", video_one, 2)
        second = self.add_media("two.mp4", "video", video_two, 2)
        picture = self.add_media("story.png", "image", image)
        self.add_media("story.wav", "narration", narration, 6)
        self.add_media("music.wav", "music", music, 1)
        self.database.save_timeline(
            self.project["id"],
            {
                "project_id": self.project["id"],
                "duration": 6,
                "segments": [
                    {"order": 1, "media_id": first["id"], "media_type": "video", "source_start": 0, "source_end": 2, "timeline_start": 0, "timeline_end": 2, "duration": 2},
                    {"order": 2, "media_id": picture["id"], "media_type": "image", "source_start": None, "source_end": None, "timeline_start": 2, "timeline_end": 4, "duration": 2},
                    {"order": 3, "media_id": second["id"], "media_type": "video", "source_start": 0, "source_end": 2, "timeline_start": 4, "timeline_end": 6, "duration": 2},
                ],
            },
        )
        render = VideoRenderer(self.database, self.ffmpeg).render(self.project["id"])
        metadata = MediaProbe().probe(render["file_path"])
        self.assertEqual(render["status"], "success")
        self.assertEqual(metadata["width"], 1920)
        self.assertEqual(metadata["height"], 1080)
        self.assertAlmostEqual(metadata["fps"], 30, delta=0.1)
        self.assertTrue(metadata["has_audio"])
        self.assertAlmostEqual(metadata["duration"], 6, delta=0.3)
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", render["file_path"]],
            capture_output=True,
            text=True,
            check=True,
        )
        codecs = {stream.get("codec_name") for stream in json.loads(probe.stdout)["streams"]}
        self.assertIn("h264", codecs)
        self.assertIn("aac", codecs)

    def test_transition_fallback_still_renders(self) -> None:
        source_video, narration = self.create_synthetic_media()
        video = self.add_media("source.mp4", "video", source_video, 2)
        self.add_media("narration.wav", "narration", narration, 2)
        self.save_timeline(video)
        with patch.object(
            VideoRenderer,
            "_build_transition_track",
            side_effect=VideoRenderError("forced transition failure"),
        ):
            render = VideoRenderer(self.database, self.ffmpeg).render(self.project["id"])
        self.assertTrue(Path(render["file_path"]).is_file())
        log = self.project_path / "output" / "render.log"
        self.assertIn("Fallback sem transicoes", log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
