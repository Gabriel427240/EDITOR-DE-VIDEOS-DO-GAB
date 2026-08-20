import shutil
import subprocess
from pathlib import Path

from app.config import FFMPEG_PATH


class FrameExtractor:
    def __init__(self, ffmpeg_path: str = FFMPEG_PATH) -> None:
        self.ffmpeg_path = ffmpeg_path

    def extract_three_frames(self, file_path: str | Path, output_directory: str | Path) -> list[Path]:
        executable = shutil.which(self.ffmpeg_path)
        if executable is None:
            raise RuntimeError("FFmpeg nao foi encontrado no PATH.")
        output = Path(output_directory)
        output.mkdir(parents=True, exist_ok=True)
        pattern = output / "frame_%02d.jpg"
        subprocess.run(
            [executable, "-y", "-i", str(file_path), "-vf", "select=not(mod(n\\,3))", "-frames:v", "3", str(pattern)],
            capture_output=True,
            text=True,
            check=True,
        )
        return sorted(output.glob("frame_*.jpg"))
