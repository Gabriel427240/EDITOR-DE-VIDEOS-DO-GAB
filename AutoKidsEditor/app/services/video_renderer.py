import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.config import FFMPEG_PATH
from app.core.preset_manager import PresetManager
from app.database.database import Database


class VideoRenderError(RuntimeError):
    """Raised when a preview render cannot be completed."""


class VideoRenderer:
    def __init__(
        self,
        database: Database,
        ffmpeg_path: str = FFMPEG_PATH,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> None:
        self.database = database
        self.executable = ffmpeg_path
        self.progress_callback = progress_callback

    def find_executable(self) -> str | None:
        configured_path = Path(self.executable)
        if configured_path.parent != Path("."):
            return str(configured_path) if configured_path.is_file() else None
        return shutil.which(self.executable)

    def render(self, project_id: int) -> dict[str, Any]:
        project = self.database.get_project(project_id)
        preset_name = project.get("preset", PresetManager.DEFAULT_PRESET)
        preset = PresetManager.get_preset(preset_name)
        timeline = self.database.get_project_timeline(project_id)
        project_path = Path(project["folder_path"])
        render_log = project_path / "output" / "render.log"
        render_log.parent.mkdir(parents=True, exist_ok=True)
        output_path: Path | None = None
        render_directory: Path | None = None
        self._write_log(render_log, f"Inicio do render | Preset: {preset.NAME}")

        try:
            executable = self.find_executable()
            if executable is None:
                raise VideoRenderError("FFmpeg nao foi encontrado no PATH.")
            if timeline is None or not timeline.get("segments"):
                raise VideoRenderError("O projeto nao possui uma timeline valida.")
            planned_duration = float(timeline.get("duration") or 0)
            if planned_duration <= 0:
                raise VideoRenderError("A timeline possui uma duracao invalida.")

            media = self.database.list_media(project_id)
            narration = next((item for item in media if item["media_type"] == "narration"), None)
            if narration is None or not Path(narration["file_path"]).is_file():
                raise VideoRenderError("O projeto nao possui uma narracao principal valida.")
            music = next((item for item in media if item["media_type"] == "music"), None)
            music_path = Path(music["file_path"]) if music else None
            if music_path is not None and not music_path.is_file():
                raise VideoRenderError("Uma ou mais midias da timeline nao foram encontradas.")

            media_by_id = {item["id"]: item for item in media}
            segments = timeline["segments"]
            self._validate_segments(segments, media_by_id)
            used_paths = [Path(media_by_id[item["media_id"]]["file_path"]) for item in segments]
            if any(not path.is_file() for path in used_paths):
                raise VideoRenderError("Uma ou mais midias da timeline nao foram encontradas.")

            render_directory = project_path / "temp" / "render_"
            render_directory.mkdir(parents=True, exist_ok=True)
            self._write_log(
                render_log,
                f"Musica: {'sim' if music_path else 'nao'} | Volume da musica: {preset.BACKGROUND_MUSIC_VOLUME} | "
                f"Segmentos: {len(segments)} | Transicoes: {max(0, len(segments) - 1)} | "
                f"Duracao planejada: {planned_duration:.3f}",
            )
            self._progress(5, "Preparando render")
            segment_paths: list[Path] = []
            for index, segment in enumerate(segments, start=1):
                segment_path = render_directory / f"segment_{index:04d}.mp4"
                self._render_segment(
                    executable,
                    media_by_id[segment["media_id"]],
                    segment,
                    segment_path,
                    preset,
                    index == len(segments),
                )
                segment_paths.append(segment_path)
                self._progress(min(65, 5 + int(index * 60 / len(segments))), f"Processando segmento {index}/{len(segments)}")

            concat_path = render_directory / "concat.txt"
            visual_track = render_directory / "visual_track.mp4"
            self._progress(72, "Aplicando transicoes")
            try:
                self._build_transition_track(executable, segment_paths, segments, visual_track, planned_duration, preset, render_log)
            except VideoRenderError as error:
                self._write_log(render_log, f"Fallback sem transicoes: {error}")
                self._write_concat_file(concat_path, segment_paths)
                self._run_ffmpeg(executable, ["-y", "-f", "concat", "-safe", "0", "-i", str(concat_path), "-c", "copy", "-an", str(visual_track)], render_log)

            output_directory = project_path / "output"
            output_directory.mkdir(parents=True, exist_ok=True)
            output_path = self._unique_output_path(output_directory / "preview.mp4")
            self._progress(90, "Adicionando narracao e musica")
            self._add_audio(executable, visual_track, Path(narration["file_path"]), music_path, output_path, planned_duration, preset, render_log)
            self._write_log(render_log, f"Arquivo final: {output_path}")
            render = self.database.add_render(project_id, timeline["id"], str(output_path), planned_duration, "success", preset_name)
            shutil.rmtree(render_directory, ignore_errors=True)
            self._progress(100, "Concluido")
            return render
        except VideoRenderError as error:
            self._write_log(render_log, f"Erro: {error}")
            if timeline is not None:
                self.database.add_render(project_id, timeline["id"], str(output_path or ""), float(timeline.get("duration") or 0), "error", preset_name)
            raise
        except Exception as error:
            self._write_log(render_log, f"Erro inesperado: {error}")
            if timeline is not None:
                self.database.add_render(project_id, timeline["id"], str(output_path or ""), float(timeline.get("duration") or 0), "error", preset_name)
            raise VideoRenderError(f"Falha ao gerar o video: {error}") from error

    def _render_segment(
        self,
        executable: str,
        media: dict[str, Any],
        segment: dict[str, Any],
        output_path: Path,
        preset: Any,
        is_last: bool,
    ) -> None:
        duration = float(segment["duration"])
        segment_order = segment.get("order", segment.get("segment_order", 1))
        fade_in = min(preset.FADE_IN_DURATION, duration / 2) if segment_order == 1 else 0
        fade_out = min(preset.FADE_OUT_DURATION, duration / 2) if is_last else 0
        visual_filter = (
            f"scale={preset.VIDEO_WIDTH}:{preset.VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={preset.VIDEO_WIDTH}:{preset.VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
        )
        if media["media_type"] == "image":
            frames = max(1, int(duration * preset.FPS))
            zoom = f"zoom='min({preset.IMAGE_ZOOM_START}+({preset.IMAGE_ZOOM_END - preset.IMAGE_ZOOM_START})*on/{frames}, {preset.IMAGE_ZOOM_END})'"
            visual_filter = f"scale={preset.VIDEO_WIDTH}:{preset.VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={preset.VIDEO_WIDTH}:{preset.VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,zoompan={zoom}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={preset.VIDEO_WIDTH}x{preset.VIDEO_HEIGHT}:fps={preset.FPS},format=yuv420p"
            arguments = ["-y", "-loop", "1", "-i", media["file_path"], "-t", str(duration), "-vf", visual_filter]
        else:
            arguments = ["-y", "-ss", str(segment["source_start"] or 0), "-i", media["file_path"], "-t", str(duration), "-an", "-vf", visual_filter, "-r", str(preset.FPS)]
        if fade_in:
            arguments[arguments.index("-vf") + 1] += f",fade=t=in:st=0:d={fade_in}"
        if fade_out:
            arguments[arguments.index("-vf") + 1] += f",fade=t=out:st={duration - fade_out}:d={fade_out}"
        arguments += ["-an", "-r", str(preset.FPS), "-c:v", "libx264", "-preset", preset.VIDEO_PRESET, "-crf", str(preset.VIDEO_CRF), "-pix_fmt", "yuv420p", str(output_path)]
        self._run_ffmpeg(executable, arguments, output_path.parents[2] / "output" / "render.log")

    def _build_transition_track(self, executable: str, paths: list[Path], segments: list[dict[str, Any]], output: Path, duration: float, preset: Any, log: Path) -> None:
        if len(paths) == 1:
            self._run_ffmpeg(executable, ["-y", "-i", str(paths[0]), "-c", "copy", "-an", str(output)], log)
            return
        inputs: list[str] = []
        for path in paths:
            inputs += ["-i", str(path)]
        filters = []
        transition = preset.DEFAULT_TRANSITION_DURATION
        filters.append(f"[0:v][1:v]xfade=transition=fade:duration={transition}:offset={float(segments[0]['duration']) - transition}[v1]")
        cumulative = float(segments[0]["duration"]) + float(segments[1]["duration"]) - transition
        for index in range(2, len(paths)):
            filters.append(f"[v{index-1}][{index}:v]xfade=transition=fade:duration={transition}:offset={cumulative - transition}[v{index}]")
            cumulative += float(segments[index]["duration"]) - transition
        filters.append(f"[v{len(paths)-1}]tpad=stop_mode=clone:stop_duration={max(0, duration - cumulative)},trim=duration={duration},setpts=PTS-STARTPTS[vout]")
        arguments = ["-y", *inputs, "-filter_complex", ";".join(filters), "-map", "[vout]", "-an", "-r", str(preset.FPS), "-c:v", "libx264", "-preset", preset.VIDEO_PRESET, "-crf", str(preset.VIDEO_CRF), "-pix_fmt", "yuv420p", str(output)]
        self._run_ffmpeg(executable, arguments, log)

    def _add_audio(self, executable: str, visual: Path, narration: Path, music: Path | None, output: Path, duration: float, preset: Any, log: Path) -> None:
        if music is None:
            arguments = ["-y", "-i", str(visual), "-i", str(narration), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-shortest", str(output)]
        else:
            fade_out_start = max(0, duration - preset.FADE_OUT_DURATION)
            filter_complex = f"[1:a]aresample=48000[narr];[2:a]aresample=48000,volume={preset.BACKGROUND_MUSIC_VOLUME},afade=t=in:st=0:d={preset.FADE_IN_DURATION},afade=t=out:st={fade_out_start}:d={preset.FADE_OUT_DURATION}[music];[narr][music]amix=inputs=2:duration=first:dropout_transition=0[aout]"
            arguments = ["-y", "-i", str(visual), "-i", str(narration), "-stream_loop", "-1", "-i", str(music), "-filter_complex", filter_complex, "-map", "0:v:0", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-t", str(duration), "-shortest", str(output)]
        self._run_ffmpeg(executable, arguments, log)

    @staticmethod
    def _validate_segments(segments: list[dict[str, Any]], media_by_id: dict[int, dict[str, Any]]) -> None:
        for segment in segments:
            if segment.get("media_id") not in media_by_id or float(segment.get("duration") or 0) <= 0:
                raise VideoRenderError("A timeline possui um segmento invalido.")
            if segment.get("media_type") == "video" and (segment.get("source_start") is None or segment.get("source_end") is None):
                raise VideoRenderError("A timeline possui um trecho de video invalido.")

    @staticmethod
    def _write_concat_file(path: Path, segments: list[Path]) -> None:
        with path.open("w", encoding="utf-8") as file:
            for segment in segments:
                file.write(f"file '{segment.resolve().as_posix()}'\n")

    @staticmethod
    def _unique_output_path(path: Path) -> Path:
        if not path.exists():
            return path
        counter = 2
        while True:
            candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def _run_ffmpeg(self, executable: str, arguments: list[str], log: Path) -> None:
        try:
            result = subprocess.run([executable, "-hide_banner", "-loglevel", "error", *arguments], capture_output=True, text=True, check=False)
        except OSError as error:
            raise VideoRenderError(f"Nao foi possivel executar o FFmpeg: {error}") from error
        if result.returncode:
            self._write_log(log, result.stderr.strip())
            summary = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "erro desconhecido"
            raise VideoRenderError(f"FFmpeg falhou: {summary}")

    def _progress(self, percent: int, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(percent, message)

    @staticmethod
    def _write_log(path: Path, message: str) -> None:
        with path.open("a", encoding="utf-8") as file:
            file.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")
