from dataclasses import dataclass
from pathlib import Path

from .config import settings


class TranscriptionUnavailable(RuntimeError):
    pass


@dataclass
class TranscriptResult:
    text: str
    segments: list[dict]


class LocalWhisperTranscriber:
    _model = None

    def transcribe(self, path: Path) -> TranscriptResult:
        try:
            from faster_whisper import WhisperModel
        except (ImportError, OSError) as exc:
            raise TranscriptionUnavailable(
                "Local transcription is not installed or could not load. Install requirements-transcription.txt and ensure the model can be downloaded."
            ) from exc
        if self._model is None:
            try:
                self._model = WhisperModel(settings.whisper_model, device=settings.whisper_device,
                                           compute_type=settings.whisper_compute_type)
            except Exception as exc:
                raise TranscriptionUnavailable(
                    f'The local Whisper model "{settings.whisper_model}" is unavailable. Check the network for the first download, free disk space, and WHISPER_DEVICE settings.'
                ) from exc
        try:
            segments, _ = self._model.transcribe(str(path), language="en", vad_filter=True)
            rows = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segments]
            text = " ".join(row["text"] for row in rows).strip()
            if not text:
                raise ValueError("No speech was detected in this audio file.")
            return TranscriptResult(text=text, segments=rows)
        except TranscriptionUnavailable:
            raise
        except Exception as exc:
            raise ValueError("The audio could not be transcribed. Make sure it is a readable MP3 containing clear English speech.") from exc
