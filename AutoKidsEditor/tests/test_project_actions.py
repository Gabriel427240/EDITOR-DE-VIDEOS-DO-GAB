import tempfile
import unittest
from pathlib import Path

from app.core.project_manager import ProjectManager
from app.database.database import Database
from app.ui.main_window import MainWindow


class ProjectActionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.projects_dir = root / "projects"
        self.database = Database(root / "database.sqlite3")
        self.manager = ProjectManager(self.database, self.projects_dir)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_rename_project_keeps_folder(self) -> None:
        project = self.manager.create_project("Nome antigo")
        folder = Path(project["folder_path"])
        renamed = self.manager.rename_project(project["id"], "Nome novo")
        self.assertEqual(renamed["name"], "Nome novo")
        self.assertTrue(folder.is_dir())

    def test_delete_project_removes_dependents_and_folder(self) -> None:
        project = self.manager.create_project("Excluir")
        folder = Path(project["folder_path"])
        external = Path(self.temporary_directory.name) / "original.mp4"
        external.write_bytes(b"external")
        media = self.database.add_media(
            project["id"], "original.mp4", "original.mp4", str(external), "video",
            {"duration": 2, "probe_status": "success"},
        )
        self.database.save_timeline(
            project["id"],
            {"project_id": project["id"], "duration": 2, "segments": [{
                "order": 1, "media_id": media["id"], "media_type": "video",
                "source_start": 0, "source_end": 2, "timeline_start": 0,
                "timeline_end": 2, "duration": 2,
            }]},
        )
        self.manager.delete_project(project["id"])
        self.assertFalse(folder.exists())
        self.assertTrue(external.exists())
        self.assertEqual(self.database.list_projects(), [])
        self.assertEqual(self.database.list_media(project["id"]), [])
        self.assertIsNone(self.database.get_project_timeline(project["id"]))

    def test_project_filter_matches_name(self) -> None:
        projects = [{"name": "História do Leão"}, {"name": "Aula de Ciências"}]
        filtered = MainWindow.filter_projects(projects, "leão")
        self.assertEqual([item["name"] for item in filtered], ["História do Leão"])


if __name__ == "__main__":
    unittest.main()
