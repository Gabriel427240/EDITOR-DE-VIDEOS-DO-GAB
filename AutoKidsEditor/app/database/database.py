import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import DATABASE_PATH, ensure_directories


class Database:
    """Encapsulates SQLite initialization and project persistence."""

    def __init__(self, database_path: Path = DATABASE_PATH) -> None:
        self.database_path = database_path
        ensure_directories()
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    folder_path TEXT NOT NULL,
                    preset TEXT NOT NULL DEFAULT 'kids_story_v1'
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    original_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    media_type TEXT NOT NULL CHECK (
                        media_type IN ('video', 'image', 'narration', 'music')
                    ),
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects (id)
                )
                """
            )
            existing_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(media)").fetchall()
            }
            project_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(projects)").fetchall()
            }
            if "preset" not in project_columns:
                connection.execute(
                    "ALTER TABLE projects ADD COLUMN preset TEXT NOT NULL DEFAULT 'kids_story_v1'"
                )
            media_columns = {
                "duration": "REAL",
                "width": "INTEGER",
                "height": "INTEGER",
                "fps": "REAL",
                "has_audio": "INTEGER",
                "probe_status": "TEXT NOT NULL DEFAULT 'pending'",
                "semantic_description": "TEXT",
                "semantic_status": "TEXT NOT NULL DEFAULT 'pending'",
                "semantic_data": "TEXT",
            }
            for column_name, column_definition in media_columns.items():
                if column_name not in existing_columns:
                    connection.execute(
                        f"ALTER TABLE media ADD COLUMN {column_name} {column_definition}"
                    )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS timelines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL UNIQUE,
                    duration REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects (id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    media_id INTEGER NOT NULL,
                    language TEXT,
                    full_text TEXT NOT NULL,
                    model TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(project_id, media_id),
                    FOREIGN KEY (project_id) REFERENCES projects (id),
                    FOREIGN KEY (media_id) REFERENCES media (id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS transcription_segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transcription_id INTEGER NOT NULL,
                    segment_order INTEGER NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    text TEXT NOT NULL,
                    FOREIGN KEY (transcription_id) REFERENCES transcriptions (id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS narrative_scenes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    scene_order INTEGER NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    text TEXT NOT NULL,
                    visual_description TEXT,
                    emotion TEXT,
                    importance REAL NOT NULL DEFAULT 0.5,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects (id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS timeline_segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timeline_id INTEGER NOT NULL,
                    media_id INTEGER NOT NULL,
                    segment_order INTEGER NOT NULL,
                    media_type TEXT NOT NULL,
                    source_start REAL,
                    source_end REAL,
                    timeline_start REAL NOT NULL,
                    timeline_end REAL NOT NULL,
                    duration REAL NOT NULL,
                    FOREIGN KEY (timeline_id) REFERENCES timelines (id),
                    FOREIGN KEY (media_id) REFERENCES media (id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS renders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    timeline_id INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    duration REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('success', 'error')),
                    preset TEXT NOT NULL DEFAULT 'kids_story_v1',
                    FOREIGN KEY (project_id) REFERENCES projects (id),
                    FOREIGN KEY (timeline_id) REFERENCES timelines (id)
                )
                """
            )
            render_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(renders)").fetchall()
            }
            if "preset" not in render_columns:
                connection.execute(
                    "ALTER TABLE renders ADD COLUMN preset TEXT NOT NULL DEFAULT 'kids_story_v1'"
                )
            connection.commit()

    def save_narrative_scenes(
        self, project_id: int, scenes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        timestamp = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            connection.execute(
                "DELETE FROM narrative_scenes WHERE project_id = ?", (project_id,)
            )
            for scene in scenes:
                connection.execute(
                    """
                    INSERT INTO narrative_scenes (
                        project_id, scene_order, start_time, end_time, text,
                        visual_description, emotion, importance, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        scene["scene_order"],
                        scene["start_time"],
                        scene["end_time"],
                        scene["text"],
                        scene.get("visual_description"),
                        scene.get("emotion"),
                        scene.get("importance", 0.5),
                        timestamp,
                    ),
                )
            connection.commit()
        return self.get_narrative_scenes(project_id)

    def get_narrative_scenes(self, project_id: int) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM narrative_scenes
                WHERE project_id = ? ORDER BY scene_order ASC
                """,
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_narrative_scenes(self, project_id: int) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "DELETE FROM narrative_scenes WHERE project_id = ?", (project_id,)
            )
            connection.commit()

    def create_project(
        self,
        name: str,
        folder_path: str,
        status: str = "created",
        preset: str = "kids_story_v1",
    ) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO projects (name, created_at, updated_at, status, folder_path, preset)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, timestamp, timestamp, status, folder_path, preset),
            )
            connection.commit()
            project_id = cursor.lastrowid

        return self.get_project(project_id)

    def list_projects(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM projects ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_project(self, project_id: int | None) -> dict[str, Any]:
        if project_id is None:
            raise RuntimeError("Nao foi possivel criar o projeto.")

        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()

        if row is None:
            raise RuntimeError("Projeto nao encontrado.")
        return dict(row)

    def rename_project(self, project_id: int, name: str) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "UPDATE projects SET name = ?, updated_at = ? WHERE id = ?",
                (name, timestamp, project_id),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise RuntimeError("Projeto nao encontrado.")
        return self.get_project(project_id)

    def delete_project(self, project_id: int) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN")
            try:
                connection.execute(
                    "DELETE FROM timeline_segments WHERE timeline_id IN "
                    "(SELECT id FROM timelines WHERE project_id = ?)",
                    (project_id,),
                )
                connection.execute("DELETE FROM timelines WHERE project_id = ?", (project_id,))
                connection.execute("DELETE FROM narrative_scenes WHERE project_id = ?", (project_id,))
                connection.execute("DELETE FROM renders WHERE project_id = ?", (project_id,))
                connection.execute("DELETE FROM media WHERE project_id = ?", (project_id,))
                cursor = connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
                if cursor.rowcount == 0:
                    raise RuntimeError("Projeto nao encontrado.")
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def add_media(
        self,
        project_id: int,
        original_name: str,
        stored_name: str,
        file_path: str,
        media_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        metadata = metadata or {}
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO media (
                    project_id, original_name, stored_name, file_path, media_type,
                    created_at, duration, width, height, fps, has_audio, probe_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    original_name,
                    stored_name,
                    file_path,
                    media_type,
                    timestamp,
                    metadata.get("duration"),
                    metadata.get("width"),
                    metadata.get("height"),
                    metadata.get("fps"),
                    int(metadata["has_audio"]) if "has_audio" in metadata else None,
                    metadata.get("probe_status", "pending"),
                ),
            )
            connection.commit()
            media_id = cursor.lastrowid
        return self.get_media(media_id)

    def update_media_metadata(
        self, media_id: int, metadata: dict[str, Any], probe_status: str
    ) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE media
                SET duration = ?, width = ?, height = ?, fps = ?, has_audio = ?, probe_status = ?
                WHERE id = ?
                """,
                (
                    metadata.get("duration"),
                    metadata.get("width"),
                    metadata.get("height"),
                    metadata.get("fps"),
                    int(metadata["has_audio"]) if "has_audio" in metadata else None,
                    probe_status,
                    media_id,
                ),
            )
            connection.commit()
        return self.get_media(media_id)

    def list_media(self, project_id: int) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM media WHERE project_id = ? ORDER BY created_at ASC",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_media(self, media_id: int | None) -> dict[str, Any]:
        if media_id is None:
            raise RuntimeError("Nao foi possivel registrar a midia.")

        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM media WHERE id = ?", (media_id,)
            ).fetchone()
        if row is None:
            raise RuntimeError("Midia nao encontrada.")
        return dict(row)

    def delete_media(self, media_id: int) -> dict[str, Any]:
        media = self.get_media(media_id)
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM media WHERE id = ?", (media_id,))
            connection.commit()
        return media

    def save_timeline(
        self, project_id: int, timeline_data: dict[str, Any]
    ) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            connection.execute(
                "DELETE FROM timeline_segments WHERE timeline_id IN "
                "(SELECT id FROM timelines WHERE project_id = ?)",
                (project_id,),
            )
            connection.execute("DELETE FROM timelines WHERE project_id = ?", (project_id,))
            cursor = connection.execute(
                "INSERT INTO timelines (project_id, duration, created_at) VALUES (?, ?, ?)",
                (project_id, timeline_data["duration"], timestamp),
            )
            timeline_id = cursor.lastrowid
            for segment in timeline_data["segments"]:
                connection.execute(
                    """
                    INSERT INTO timeline_segments (
                        timeline_id, media_id, segment_order, media_type,
                        source_start, source_end, timeline_start, timeline_end, duration
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        timeline_id,
                        segment["media_id"],
                        segment["order"],
                        segment["media_type"],
                        segment["source_start"],
                        segment["source_end"],
                        segment["timeline_start"],
                        segment["timeline_end"],
                        segment["duration"],
                    ),
                )
            connection.commit()
        return self.get_project_timeline(project_id) or {}

    def get_project_timeline(self, project_id: int) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM timelines WHERE project_id = ?", (project_id,)
            ).fetchone()
        if row is None:
            return None
        timeline = dict(row)
        timeline["segments"] = self.list_timeline_segments(timeline["id"])
        return timeline

    def list_timeline_segments(self, timeline_id: int) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM timeline_segments
                WHERE timeline_id = ? ORDER BY segment_order ASC
                """,
                (timeline_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_render(
        self,
        project_id: int,
        timeline_id: int,
        file_path: str,
        duration: float,
        status: str,
        preset: str = "kids_story_v1",
    ) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO renders (
                    project_id, timeline_id, file_path, duration, created_at, status, preset
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, timeline_id, file_path, duration, timestamp, status, preset),
            )
            connection.commit()
            render_id = cursor.lastrowid
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM renders WHERE id = ?", (render_id,)
            ).fetchone()
        return dict(row)

    def list_project_renders(self, project_id: int) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM renders WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_transcription(self, project_id: int, media_id: int) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM transcriptions WHERE project_id = ? AND media_id = ?",
                (project_id, media_id),
            ).fetchone()
        if row is None:
            return None
        transcription = dict(row)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM transcription_segments WHERE transcription_id = ? ORDER BY segment_order",
                (transcription["id"],),
            ).fetchall()
        transcription["segments"] = [dict(item) for item in rows]
        return transcription

    def save_transcription(
        self,
        project_id: int,
        media_id: int,
        language: str,
        full_text: str,
        model: str,
        segments: list[dict[str, Any]],
        status: str = "success",
    ) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN")
            connection.execute(
                "DELETE FROM transcription_segments WHERE transcription_id IN "
                "(SELECT id FROM transcriptions WHERE project_id = ? AND media_id = ?)",
                (project_id, media_id),
            )
            connection.execute(
                "DELETE FROM transcriptions WHERE project_id = ? AND media_id = ?",
                (project_id, media_id),
            )
            cursor = connection.execute(
                """
                INSERT INTO transcriptions (
                    project_id, media_id, language, full_text, model, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, media_id, language, full_text, model, status, timestamp),
            )
            transcription_id = cursor.lastrowid
            for index, segment in enumerate(segments, start=1):
                connection.execute(
                    """
                    INSERT INTO transcription_segments (
                        transcription_id, segment_order, start_time, end_time, text
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (transcription_id, index, segment["start"], segment["end"], segment["text"]),
                )
            connection.commit()
        return self.get_transcription(project_id, media_id) or {}
