import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.database.database import Database
from app.services.media_probe import MediaProbe, MediaProbeError
from app.ui.project_details import format_duration


class MediaProbeTest(unittest.TestCase):
    def test_parse_fraction(self) -> None:
        self.assertAlmostEqual(MediaProbe.parse_fraction("30/1"), 30.0)
        self.assertAlmostEqual(MediaProbe.parse_fraction("30000/1001"), 29.97002997)
        self.assertIsNone(MediaProbe.parse_fraction("0/0"))
        self.assertIsNone(MediaProbe.parse_fraction("invalid"))

    def test_format_duration(self) -> None:
        self.assertEqual(format_duration(8.4), "00:08")
        self.assertEqual(format_duration(65), "01:05")
        self.assertEqual(format_duration(272), "04:32")
        self.assertEqual(format_duration(3665), "01:01:05")
        self.assertEqual(format_duration(None), "Metadados indisponiveis")

    def test_missing_ffprobe_is_friendly(self) -> None:
        with self.assertRaisesRegex(MediaProbeError, "FFprobe"):
            MediaProbe("missing-ffprobe-executable").probe("missing.png")

    def test_migrates_existing_media_table(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "legacy.sqlite3"
            connection = sqlite3.connect(database_path)
            try:
                connection.execute(
                    """
                    CREATE TABLE media (
                        id INTEGER PRIMARY KEY,
                        project_id INTEGER NOT NULL,
                        original_name TEXT NOT NULL,
                        stored_name TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        media_type TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                connection.commit()
            finally:
                connection.close()

            Database(database_path)
            connection = sqlite3.connect(database_path)
            try:
                columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(media)")
                }
            finally:
                connection.close()
            self.assertTrue(
                {"duration", "width", "height", "fps", "has_audio", "probe_status"}
                <= columns
            )

    def test_updates_media_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = Database(Path(temporary_directory) / "metadata.sqlite3")
            connection = database._connect()
            try:
                connection.execute(
                    "INSERT INTO projects (name, created_at, updated_at, status, folder_path) "
                    "VALUES ('Test', 'now', 'now', 'created', 'folder')"
                )
                project_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
                connection.commit()
            finally:
                connection.close()
            media = database.add_media(
                project_id, "image.png", "image.png", "folder/image.png", "image"
            )
            updated = database.update_media_metadata(
                media["id"], {"width": 1024, "height": 768}, "success"
            )
            self.assertEqual(updated["width"], 1024)
            self.assertEqual(updated["height"], 768)
            self.assertEqual(updated["probe_status"], "success")


if __name__ == "__main__":
    unittest.main()
