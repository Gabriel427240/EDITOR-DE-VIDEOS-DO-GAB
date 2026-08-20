import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

from app.config import FFPROBE_PATH


class MediaProbeError(RuntimeError):
    """Raised when FFprobe cannot analyze a media file."""


class MediaProbe:
    def __init__(self, executable: str | Path = FFPROBE_PATH) -> None:
        self.executable = str(executable)

    def find_executable(self) -> str | None:
        configured_path = Path(self.executable)
        if configured_path.parent != Path("."):
            return str(configured_path) if configured_path.is_file() else None
        return shutil.which(self.executable)

    def probe(self, file_path: str | Path) -> dict[str, Any]:
        executable = self.find_executable()
        if executable is None:
            raise MediaProbeError(
                "FFprobe nao foi encontrado. Instale FFmpeg e adicione ffprobe ao PATH."
            )

        try:
            result = subprocess.run(
                [
                    executable,
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    str(file_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            metadata = json.loads(result.stdout)
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
            raise MediaProbeError(f"Nao foi possivel analisar a midia: {error}") from error

        return self._normalize(metadata)

    @classmethod
    def _normalize(cls, metadata: dict[str, Any]) -> dict[str, Any]:
        streams = metadata.get("streams") or []
        format_name = str((metadata.get("format") or {}).get("format_name", ""))
        video_stream = next(
            (stream for stream in streams if stream.get("codec_type") == "video"), None
        )
        audio_stream = next(
            (stream for stream in streams if stream.get("codec_type") == "audio"), None
        )
        duration = cls._safe_float(
            (metadata.get("format") or {}).get("duration")
            or next((stream.get("duration") for stream in streams if stream.get("duration")), None)
        )

        if video_stream is not None and not cls._looks_like_image(format_name, video_stream):
            return {
                "duration": duration,
                "width": cls._safe_int(video_stream.get("width")),
                "height": cls._safe_int(video_stream.get("height")),
                "fps": cls.parse_fraction(video_stream.get("r_frame_rate")),
                "has_audio": audio_stream is not None,
            }
        if audio_stream is not None:
            return {"duration": duration}

        image_stream = next(
            (stream for stream in streams if stream.get("width") or stream.get("height")),
            None,
        )
        if image_stream is not None:
            return {
                "width": cls._safe_int(image_stream.get("width")),
                "height": cls._safe_int(image_stream.get("height")),
            }
        return {"duration": duration}

    @staticmethod
    def _looks_like_image(format_name: str, stream: dict[str, Any]) -> bool:
        image_formats = {"image2", "image2pipe", "png_pipe", "webp_pipe"}
        return format_name in image_formats or stream.get("codec_name") in {
            "png",
            "mjpeg",
            "webp",
        }

    @staticmethod
    def parse_fraction(value: Any) -> float | None:
        if value in (None, "", "0/0"):
            return None
        try:
            return float(Fraction(str(value)))
        except (ValueError, ZeroDivisionError):
            return None

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            return None if value in (None, "") else float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            return None if value in (None, "") else int(value)
        except (TypeError, ValueError):
            return None
