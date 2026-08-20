from pathlib import Path
from typing import Any

from app.core.editing_rules import (
    DEFAULT_IMAGE_DURATION,
    DEFAULT_VIDEO_SEGMENT_DURATION,
    MAX_VIDEO_SEGMENT_DURATION,
)
from app.database.database import Database
from app.services.media_probe import MediaProbe, MediaProbeError


class TimelineGenerationError(ValueError):
    """Raised when a project cannot produce a planned timeline."""


class TimelineGenerator:
    def __init__(
        self,
        database: Database,
        media_probe: MediaProbe | None = None,
    ) -> None:
        self.database = database
        self.media_probe = media_probe or MediaProbe()

    def generate(self, project_id: int, mode: str = "basic") -> dict[str, Any]:
        """Generate the current mechanical timeline; smart modes currently fall back safely."""
        media = self.database.list_media(project_id)
        narration = next(
            (item for item in media if item["media_type"] == "narration"), None
        )
        if narration is None:
            raise TimelineGenerationError(
                "O projeto precisa de uma narracao para gerar a timeline."
            )

        narration = self._refresh_metadata_if_needed(narration)
        narration_duration = self._valid_duration(narration.get("duration"))
        if narration_duration is None:
            raise TimelineGenerationError(
                "Nao foi possivel determinar a duracao da narracao."
            )

        visual_media = self._prepare_visual_media(media)
        if not visual_media:
            raise TimelineGenerationError("O projeto precisa de videos ou imagens.")

        segments = self._build_segments(visual_media, narration_duration)
        return {
            "project_id": project_id,
            "duration": narration_duration,
            "segments": segments,
        }

    def _prepare_visual_media(self, media: list[dict[str, Any]]) -> list[dict[str, Any]]:
        prepared = []
        for item in media:
            if item["media_type"] not in {"video", "image"}:
                continue
            current = self._refresh_metadata_if_needed(item)
            if current["media_type"] == "video" and self._valid_duration(current.get("duration")) is None:
                continue
            prepared.append(current)
        return prepared

    def _refresh_metadata_if_needed(self, media: dict[str, Any]) -> dict[str, Any]:
        if media.get("probe_status") == "success" and self._has_required_metadata(media):
            return media

        file_path = Path(media["file_path"])
        if not file_path.is_file():
            return media
        try:
            metadata = self.media_probe.probe(file_path)
        except (MediaProbeError, OSError, ValueError):
            return media
        return self.database.update_media_metadata(media["id"], metadata, "success")

    @staticmethod
    def _has_required_metadata(media: dict[str, Any]) -> bool:
        if media["media_type"] == "video":
            return media.get("duration") is not None
        if media["media_type"] == "narration":
            return media.get("duration") is not None
        return media.get("width") is not None and media.get("height") is not None

    def _build_segments(
        self, visual_media: list[dict[str, Any]], target_duration: float
    ) -> list[dict[str, Any]]:
        offsets: dict[int, float] = {}
        segments: list[dict[str, Any]] = []
        timeline_position = 0.0
        last_media_id: int | None = None
        last_media_type: str | None = None
        order_index = 0

        while timeline_position < target_duration - 1e-9:
            media = self._choose_media(
                visual_media, last_media_id, last_media_type, order_index
            )
            if media is None:
                break
            remaining = target_duration - timeline_position
            if media["media_type"] == "video":
                source_duration = self._valid_duration(media.get("duration"))
                if source_duration is None:
                    order_index += 1
                    continue
                source_start = offsets.get(media["id"], 0.0)
                if source_start >= source_duration - 1e-9:
                    source_start = 0.0
                segment_duration = min(
                    DEFAULT_VIDEO_SEGMENT_DURATION,
                    MAX_VIDEO_SEGMENT_DURATION,
                    source_duration - source_start,
                    remaining,
                )
                source_end = source_start + segment_duration
                offsets[media["id"]] = source_end
            else:
                source_start = None
                source_end = None
                segment_duration = min(DEFAULT_IMAGE_DURATION, remaining)

            if segment_duration <= 0:
                order_index += 1
                continue
            timeline_end = timeline_position + segment_duration
            segments.append(
                {
                    "order": len(segments) + 1,
                    "media_id": media["id"],
                    "media_type": media["media_type"],
                    "source_start": source_start,
                    "source_end": source_end,
                    "timeline_start": timeline_position,
                    "timeline_end": timeline_end,
                    "duration": segment_duration,
                }
            )
            timeline_position = timeline_end
            last_media_id = media["id"]
            last_media_type = media["media_type"]
            order_index = (visual_media.index(media) + 1) % len(visual_media)

        return segments

    @staticmethod
    def _choose_media(
        visual_media: list[dict[str, Any]],
        last_media_id: int | None,
        last_media_type: str | None,
        order_index: int,
    ) -> dict[str, Any] | None:
        if not visual_media:
            return None
        ordered = visual_media[order_index:] + visual_media[:order_index]
        preferred_type = {"video": "image", "image": "video"}.get(last_media_type)
        candidates = [
            item
            for item in ordered
            if item["media_type"] == preferred_type and item["id"] != last_media_id
        ]
        if not candidates:
            candidates = [item for item in ordered if item["id"] != last_media_id]
        if not candidates:
            candidates = ordered
        return candidates[0]

    @staticmethod
    def _valid_duration(value: Any) -> float | None:
        try:
            duration = float(value)
        except (TypeError, ValueError):
            return None
        return duration if duration > 0 else None
