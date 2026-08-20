import json
from typing import Any

from app.database.database import Database
from app.services.ollama_service import OllamaService
from app.services.transcription_service import TranscriptionService


class NarrativeAnalysisUnavailable(RuntimeError):
    """Raised because intelligent narrative analysis is not configured yet."""


class NarrativeAnalyzer:
    def __init__(
        self,
        database: Database,
        transcription_service: TranscriptionService | None = None,
        ollama_service: OllamaService | None = None,
    ) -> None:
        self.database = database
        self.transcription_service = transcription_service or TranscriptionService()
        self.ollama_service = ollama_service or OllamaService()

    def analyze(self, project_id: int) -> dict[str, Any]:
        narration = next(
            (item for item in self.database.list_media(project_id) if item["media_type"] == "narration"),
            None,
        )
        if narration is None:
            raise NarrativeAnalysisUnavailable("Analise inteligente ainda nao esta configurada.")
        cached = self.database.get_transcription(project_id, narration["id"])
        transcription = cached
        if transcription is None:
            try:
                result = self.transcription_service.transcribe(narration["file_path"])
            except (FileNotFoundError, RuntimeError) as error:
                raise NarrativeAnalysisUnavailable(
                    "Analise inteligente ainda nao esta configurada."
                ) from error
            transcription = self.database.save_transcription(
                project_id,
                narration["id"],
                result["language"],
                result["text"],
                self.transcription_service.model_size,
                result["segments"],
            )
        if not self.ollama_service.is_available():
            raise NarrativeAnalysisUnavailable("Ollama local nao esta disponivel.")
        prompt = self._build_prompt(transcription)
        response = self.ollama_service.generate(prompt, format="json", temperature=0)
        scenes = self.parse_scene_response(response)
        return {"scenes": self.create_manual_scenes(project_id, scenes)}

    @staticmethod
    def parse_scene_response(response: str) -> list[dict[str, Any]]:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        try:
            payload = json.loads(cleaned)
        except (TypeError, ValueError) as error:
            raise ValueError("A resposta do modelo nao contem JSON valido.") from error
        scenes = payload.get("scenes") if isinstance(payload, dict) else None
        if not isinstance(scenes, list):
            raise ValueError("A resposta do modelo nao contem cenas validas.")
        normalized = []
        for scene in scenes:
            normalized.append(
                {
                    "start_time": scene["start_time"],
                    "end_time": scene["end_time"],
                    "text": scene["text"],
                    "visual_description": scene.get("visual_description", ""),
                    "emotion": scene.get("emotion", "neutral"),
                    "importance": scene.get("importance", 0.5),
                    "keywords": scene.get("keywords", []),
                }
            )
        return normalized

    @staticmethod
    def _build_prompt(transcription: dict[str, Any]) -> str:
        return (
            "Divida a transcricao abaixo em cenas narrativas. Responda somente JSON no formato "
            '{"scenes":[{"start_time":0,"end_time":1,"text":"...","visual_description":"...",'
            '"emotion":"neutral","importance":0.5,"keywords":[]}]}\\n\\n'
            f"TRANSCRICAO:\n{transcription.get('full_text', '')}"
        )

    def create_manual_scenes(
        self, project_id: int, scenes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        narration_duration = self._narration_duration(project_id)
        validated = self._validate_scenes(scenes, narration_duration)
        return self.database.save_narrative_scenes(project_id, validated)

    def generate_test_scenes(self, project_id: int) -> list[dict[str, Any]]:
        narration_duration = self._narration_duration(project_id)
        scenes = []
        start_time = 0.0
        scene_order = 1
        while start_time < narration_duration:
            end_time = min(start_time + 10.0, narration_duration)
            scenes.append(
                {
                    "scene_order": scene_order,
                    "start_time": start_time,
                    "end_time": end_time,
                    "text": f"Cena de teste {scene_order}",
                    "visual_description": "Descricao visual de teste",
                    "emotion": "neutral",
                    "importance": 0.5,
                }
            )
            start_time = end_time
            scene_order += 1
        return self.create_manual_scenes(project_id, scenes)

    def _narration_duration(self, project_id: int) -> float:
        narration = next(
            (
                media
                for media in self.database.list_media(project_id)
                if media["media_type"] == "narration"
            ),
            None,
        )
        if narration is None or narration.get("duration") is None:
            raise ValueError("O projeto precisa de uma narracao com duracao valida.")
        try:
            duration = float(narration["duration"])
        except (TypeError, ValueError) as error:
            raise ValueError("A duracao da narracao e invalida.") from error
        if duration <= 0:
            raise ValueError("A duracao da narracao e invalida.")
        return duration

    @staticmethod
    def _validate_scenes(
        scenes: list[dict[str, Any]], narration_duration: float
    ) -> list[dict[str, Any]]:
        if not scenes:
            raise ValueError("E necessario informar pelo menos uma cena.")
        validated = []
        for index, scene in enumerate(scenes, start=1):
            if not scene.get("text"):
                raise ValueError("Cada cena precisa possuir texto.")
            try:
                start_time = float(scene["start_time"])
                end_time = float(scene["end_time"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("Cada cena precisa possuir tempos validos.") from error
            if start_time < 0:
                raise ValueError("O inicio da cena nao pode ser negativo.")
            if end_time <= start_time:
                raise ValueError("O fim da cena deve ser maior que o inicio.")
            if end_time > narration_duration:
                raise ValueError("A cena nao pode ultrapassar a duracao da narracao.")
            try:
                importance = float(scene.get("importance", 0.5))
            except (TypeError, ValueError):
                importance = 0.5
            validated.append(
                {
                    "scene_order": index,
                    "start_time": start_time,
                    "end_time": end_time,
                    "text": str(scene["text"]),
                    "visual_description": str(scene.get("visual_description") or ""),
                    "emotion": str(scene.get("emotion") or ""),
                    "importance": max(0.0, min(1.0, importance)),
                }
            )
        validated.sort(key=lambda scene: (scene["start_time"], scene["end_time"]))
        for previous, current in zip(validated, validated[1:]):
            if current["start_time"] < previous["end_time"]:
                raise ValueError("As cenas narrativas nao podem se sobrepor.")
        for index, scene in enumerate(validated, start=1):
            scene["scene_order"] = index
        return validated
