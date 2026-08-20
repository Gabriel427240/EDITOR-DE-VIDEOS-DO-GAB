from typing import Any

from app.services.ollama_service import OllamaService


class SceneMatchingUnavailable(RuntimeError):
    """Raised because semantic media matching is not configured yet."""


class SceneMatcher:
    def __init__(self, mode: str = "basic_text", ollama_service: OllamaService | None = None) -> None:
        self.mode = mode
        self.ollama_service = ollama_service or OllamaService()

    def match(
        self, scene: dict[str, Any], media_candidates: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if self.mode == "vision":
            raise SceneMatchingUnavailable("Selecao visual requer GPU e modelo visual.")
        if not media_candidates:
            raise SceneMatchingUnavailable(
                "Selecao semantica de midia ainda nao esta configurada."
            )
        ranked = sorted(
            media_candidates,
            key=lambda media: self._text_score(scene, media),
            reverse=True,
        )
        best = ranked[0]
        return {"best_media_id": best["id"], "score": self._text_score(scene, best)}

    @staticmethod
    def _text_score(scene: dict[str, Any], media: dict[str, Any]) -> float:
        query = " ".join(
            str(scene.get(key, "")) for key in ("text", "visual_description", "emotion")
        ).lower()
        candidate = " ".join(
            str(media.get(key, "")) for key in ("semantic_description", "original_name")
        ).lower()
        words = {word for word in query.split() if len(word) > 2}
        if not words:
            return 0.0
        return round(sum(word in candidate for word in words) / len(words), 3)
