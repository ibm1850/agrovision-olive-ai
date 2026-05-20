from __future__ import annotations

try:
    import whisper

    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


class VoiceService:
    def __init__(self, model_name: str = "tiny") -> None:
        self.model_name = model_name
        self._model = None

    def _load(self):
        if not WHISPER_AVAILABLE:
            raise RuntimeError(
                "Whisper is not installed. Install `openai-whisper` to use /voice."
            )
        if self._model is None:
            self._model = whisper.load_model(self.model_name)

    def transcribe(self, audio_path: str) -> str:
        self._load()
        assert self._model is not None
        result = self._model.transcribe(audio_path, fp16=False)
        return (result.get("text") or "").strip()

