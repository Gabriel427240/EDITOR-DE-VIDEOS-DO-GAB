import tempfile
import unittest
from pathlib import Path

from app.core.project_manager import ProjectManager
from app.database.database import Database


class ProjectMediaTest(unittest.TestCase):
    def test_project_structure_import_and_remove_media(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manager = ProjectManager(
                database=Database(root / "database.sqlite3"),
                projects_dir=root / "projects",
            )
            project = manager.create_project("Projeto de Teste")
            project_path = Path(project["folder_path"])

            for directory_name in ("videos", "images", "audio", "music", "temp", "output"):
                self.assertTrue((project_path / directory_name).is_dir())

            original_file = root / "imagem.png"
            original_file.write_bytes(b"fake image content")
            media = manager.import_media(project["id"], original_file, "image")
            stored_file = Path(media["file_path"])

            self.assertTrue(stored_file.is_file())
            self.assertEqual(stored_file.read_bytes(), b"fake image content")
            self.assertEqual(len(manager.list_project_media(project["id"])), 1)

            manager.delete_media(media["id"])
            self.assertFalse(stored_file.exists())
            self.assertTrue(original_file.exists())
            self.assertEqual(manager.list_project_media(project["id"]), [])


if __name__ == "__main__":
    unittest.main()
