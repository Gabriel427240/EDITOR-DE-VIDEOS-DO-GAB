from pathlib import Path
from typing import Any


class VisualAnalysisService:
    available = False
    message = "Modelo visual nao instalado neste computador."

    def analyze_image(self, file_path: str | Path) -> dict[str, Any]:
        raise RuntimeError(self.message)

    def analyze_video(self, file_path: str | Path) -> dict[str, Any]:
        raise RuntimeError(self.message)
