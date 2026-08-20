import shutil
from pathlib import Path
from typing import Any

from app.config import PROJECTS_DIR, ensure_directories, ensure_project_structure
from app.database.database import Database
from app.core.timeline_generator import TimelineGenerator
from app.core.preset_manager import PresetManager
from app.core.narrative_analyzer import NarrativeAnalyzer
from app.services.media_probe import MediaProbe, MediaProbeError
from app.services.video_renderer import VideoRenderer
from app.services.transcription_service import TranscriptionService
from app.core.narrative_analyzer import NarrativeAnalysisUnavailable


class ProjectManager:
    """Coordinates project folders and database records."""

    MEDIA_TYPES = {"video", "image", "narration", "music"}
    MEDIA_EXTENSIONS = {
        "video": {".mp4", ".mov", ".mkv", ".avi", ".webm"},
        "image": {".png", ".jpg", ".jpeg", ".webp"},
        "narration": {".mp3", ".wav", ".m4a", ".aac"},
        "music": {".mp3", ".wav", ".m4a", ".aac"},
    }
    MEDIA_DIRECTORIES = {
        "video": "videos",
        "image": "images",
        "narration": "audio",
        "music": "music",
    }

    def __init__(
        self,
        database: Database | None = None,
        projects_dir: Path = PROJECTS_DIR,
        media_probe: MediaProbe | None = None,
    ) -> None:
        ensure_directories()
        self.database = database or Database()
        self.projects_dir = projects_dir
        self.media_probe = media_probe or MediaProbe()
        self.timeline_generator = TimelineGenerator(self.database, self.media_probe)
        self.narrative_analyzer = NarrativeAnalyzer(self.database)
        self.transcription_service = self.narrative_analyzer.transcription_service

    def create_project(self, name: str) -> dict[str, Any]:
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValueError("O nome do projeto nao pode estar vazio.")

        folder_name = self._folder_name(clean_name)
        folder_path = self._available_folder(self.projects_dir / folder_name)
        folder_path.mkdir(parents=True, exist_ok=False)
        ensure_project_structure(folder_path)
        return self.database.create_project(
            clean_name, str(folder_path), preset=PresetManager.DEFAULT_PRESET
        )

    def list_projects(self) -> list[dict[str, Any]]:
        return self.database.list_projects()

    def open_project(self, project_id: int) -> dict[str, Any]:
        return self.get_project(project_id)

    def get_project(self, project_id: int) -> dict[str, Any]:
        project = self.database.get_project(project_id)
        ensure_project_structure(Path(project["folder_path"]))
        return project

    def import_media(
        self, project_id: int, file_path: str | Path, media_type: str
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        source_path = Path(file_path)
        if not source_path.is_file():
            raise FileNotFoundError(f"Arquivo nao encontrado: {source_path}")
        if media_type not in self.MEDIA_TYPES:
            raise ValueError("Tipo de midia invalido.")
        if source_path.suffix.lower() not in self.MEDIA_EXTENSIONS[media_type]:
            raise ValueError("A extensao do arquivo nao e valida para este tipo de midia.")

        project_path = Path(project["folder_path"])
        target_directory = project_path / self.MEDIA_DIRECTORIES[media_type]
        target_directory.mkdir(parents=True, exist_ok=True)
        target_path = self._available_file(target_directory / source_path.name)
        shutil.copy2(source_path, target_path)

        if media_type in {"narration", "music"}:
            for media in self.list_project_media(project_id):
                if media["media_type"] == media_type:
                    self.delete_media(media["id"])

        media = self.database.add_media(
            project_id,
            source_path.name,
            target_path.name,
            str(target_path),
            media_type,
            {"probe_status": "pending"},
        )
        try:
            metadata = self.media_probe.probe(target_path)
        except MediaProbeError:
            return self.database.update_media_metadata(media["id"], {}, "error")
        except Exception:
            return self.database.update_media_metadata(media["id"], {}, "error")
        return self.database.update_media_metadata(media["id"], metadata, "success")

    def list_project_media(self, project_id: int) -> list[dict[str, Any]]:
        self.get_project(project_id)
        return self.database.list_media(project_id)

    def delete_media(self, media_id: int) -> None:
        media = self.database.delete_media(media_id)
        stored_path = Path(media["file_path"])
        if stored_path.is_file():
            stored_path.unlink()

    def delete_project(self, project_id: int) -> None:
        project = self.get_project(project_id)
        project_path = Path(project["folder_path"])
        self.database.delete_project(project_id)
        if project_path.is_dir():
            shutil.rmtree(project_path)

    def rename_project(self, project_id: int, name: str) -> dict[str, Any]:
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValueError("O nome do projeto nao pode estar vazio.")
        return self.database.rename_project(project_id, clean_name)

    def generate_timeline(self, project_id: int, mode: str = "basic") -> dict[str, Any]:
        timeline_data = self.timeline_generator.generate(project_id, mode=mode)
        return self.database.save_timeline(project_id, timeline_data)

    def get_project_timeline(self, project_id: int) -> dict[str, Any] | None:
        self.get_project(project_id)
        return self.database.get_project_timeline(project_id)

    def save_timeline(
        self, project_id: int, timeline_data: dict[str, Any]
    ) -> dict[str, Any]:
        self.get_project(project_id)
        return self.database.save_timeline(project_id, timeline_data)

    def list_timeline_segments(self, timeline_id: int) -> list[dict[str, Any]]:
        return self.database.list_timeline_segments(timeline_id)

    def render_preview(
        self,
        project_id: int,
        progress_callback: Any | None = None,
    ) -> dict[str, Any]:
        renderer = VideoRenderer(self.database, progress_callback=progress_callback)
        return renderer.render(project_id)

    def create_test_scenes(self, project_id: int) -> list[dict[str, Any]]:
        return self.narrative_analyzer.generate_test_scenes(project_id)

    def get_narrative_scenes(self, project_id: int) -> list[dict[str, Any]]:
        self.get_project(project_id)
        return self.database.get_narrative_scenes(project_id)

    def transcribe_narration(
        self, project_id: int, progress_callback: Any | None = None
    ) -> dict[str, Any]:
        narration = next(
            (item for item in self.list_project_media(project_id) if item["media_type"] == "narration"),
            None,
        )
        if narration is None:
            raise ValueError("O projeto precisa de uma narracao principal.")
        cached = self.database.get_transcription(project_id, narration["id"])
        if cached is not None:
            return cached
        result = self.transcription_service.transcribe(narration["file_path"], progress_callback)
        return self.database.save_transcription(
            project_id,
            narration["id"],
            result["language"],
            result["text"],
            self.transcription_service.model_size,
            result["segments"],
        )

    def analyze_story(
        self, project_id: int, progress_callback: Any | None = None
    ) -> dict[str, Any]:
        if progress_callback:
            progress_callback(55, "Analisando historia...")
        return self.narrative_analyzer.analyze(project_id)

    def prepare_with_ai(self, project_id: int, progress_callback: Any | None = None) -> dict[str, Any]:
        self.transcribe_narration(project_id, progress_callback)
        if progress_callback:
            progress_callback(55, "Analisando historia...")
        try:
            self.analyze_story(project_id, progress_callback)
        except NarrativeAnalysisUnavailable:
            if progress_callback:
                progress_callback(70, "Ollama indisponivel; usando cenas manuais...")
        if progress_callback:
            progress_callback(85, "Criando timeline inteligente...")
        return self.generate_timeline(project_id, mode="smart")

    @staticmethod
    def _folder_name(name: str) -> str:
        safe_name = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in name
        )
        return safe_name.strip("._") or "projeto"

    @staticmethod
    def _available_folder(folder_path: Path) -> Path:
        if not folder_path.exists():
            return folder_path

        counter = 2
        while True:
            candidate = folder_path.with_name(f"{folder_path.name}_{counter}")
            if not candidate.exists():
                return candidate
            counter += 1

    @staticmethod
    def _available_file(file_path: Path) -> Path:
        if not file_path.exists():
            return file_path

        counter = 2
        while True:
            candidate = file_path.with_name(
                f"{file_path.stem}_{counter}{file_path.suffix}"
            )
            if not candidate.exists():
                return candidate
            counter += 1
