import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.core.preset_manager import PresetManager
from app.database.database import Database


class PresetTest(unittest.TestCase):
    def test_loads_kids_story_v1(self) -> None:
        preset = PresetManager.get_preset("kids_story_v1")
        self.assertEqual(preset.NAME, "Kids Story V1")
        self.assertEqual(preset.BACKGROUND_MUSIC_VOLUME, 0.12)

    def test_new_project_has_default_preset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = Database(Path(temporary_directory) / "project.sqlite3")
            project = database.create_project("Projeto", "folder")
            self.assertEqual(project["preset"], "kids_story_v1")

    def test_old_project_gets_default_preset_without_data_loss(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "legacy.sqlite3"
            connection = sqlite3.connect(database_path)
            connection.execute(
                """
                CREATE TABLE projects (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    folder_path TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO projects VALUES (1, 'Antigo', 'a', 'b', 'created', 'folder')"
            )
            connection.commit()
            connection.close()
            database = Database(database_path)
            project = database.get_project(1)
            self.assertEqual(project["name"], "Antigo")
            self.assertEqual(project["preset"], "kids_story_v1")


if __name__ == "__main__":
    unittest.main()
