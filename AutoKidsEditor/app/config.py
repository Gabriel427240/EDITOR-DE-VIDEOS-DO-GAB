from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROJECTS_DIR = DATA_DIR / "projects"
OUTPUTS_DIR = DATA_DIR / "outputs"
TEMP_DIR = DATA_DIR / "temp"
DATABASE_PATH = DATA_DIR / "autokids.db"
FFPROBE_PATH = "ffprobe"
FFMPEG_PATH = "ffmpeg"
PROJECT_SUBDIRECTORIES = ("videos", "images", "audio", "music", "temp", "output")


def ensure_directories() -> None:
    """Create the local directories required by the application."""
    for directory in (PROJECTS_DIR, OUTPUTS_DIR, TEMP_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def ensure_project_structure(project_path: Path) -> None:
    for directory_name in PROJECT_SUBDIRECTORIES:
        (project_path / directory_name).mkdir(parents=True, exist_ok=True)
