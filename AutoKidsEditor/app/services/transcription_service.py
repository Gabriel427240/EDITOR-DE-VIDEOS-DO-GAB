import logging
from pathlib import Path
from typing import Any, Callable


class TranscriptionService:
    """CPU transcription service. The Whisper model is loaded only on demand."""

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: Any | None = None

    def _get_model(self) -> Any:
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as error:
                raise RuntimeError("faster-whisper nao esta instalado.") from error
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    def transcribe(
        self,
        file_path: str | Path,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> dict[str, Any]:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Arquivo nao encontrado: {path}")
        if progress_callback:
            progress_callback(10, "Carregando modelo de transcricao...")
        logging.getLogger(__name__).info("Transcription model=%s device=%s compute=%s", self.model_size, self.device, self.compute_type)
        segments, info = self._get_model().transcribe(
            str(path), vad_filter=True, beam_size=1
        )
        normalized = []
        texts = []
        for index, segment in enumerate(segments, start=1):
            text = segment.text.strip()
            normalized.append({"start": float(segment.start), "end": float(segment.end), "text": text})
            texts.append(text)
            if progress_callback:
                progress_callback(min(90, 10 + index), "Transcrevendo narracao...")
        duration = float(getattr(info, "duration", 0.0) or 0.0)
        language = str(getattr(info, "language", "") or "")
        if progress_callback:
            progress_callback(100, "Transcricao concluida.")
        return {"language": language, "duration": duration, "text": " ".join(texts).strip(), "segments": normalized}
