import json
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


class OllamaService:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2:1b") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def is_available(self) -> bool:
        try:
            self._request("GET", "/api/tags")
            return True
        except (OSError, URLError, RuntimeError):
            return False

    def list_models(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/api/tags")
        return payload.get("models", [])

    def generate(self, prompt: str, model: str | None = None, **options: Any) -> str:
        payload = self._request(
            "POST",
            "/api/generate",
            {"model": model or self.model, "prompt": prompt, "stream": False, "options": options},
        )
        return str(payload.get("response", ""))

    def chat(self, messages: list[dict[str, str]], model: str | None = None, **options: Any) -> str:
        payload = self._request(
            "POST",
            "/api/chat",
            {"model": model or self.model, "messages": messages, "stream": False, "options": options},
        )
        return str((payload.get("message") or {}).get("content", ""))

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(self.base_url + path, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as error:
            raise RuntimeError(f"Ollama nao respondeu: {error}") from error
