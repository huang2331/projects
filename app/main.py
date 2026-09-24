import csv
import hashlib
import io
import os
import re
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from mutagen.mp3 import MP3, HeaderNotFoundError
from mutagen import MutagenError

from .analysis import count_words
from .audio_quality import analyze_speech_quality
from .config import settings
from .storage import LessonStore
from .transcription import LocalWhisperTranscriber, TranscriptionUnavailable

app = FastAPI(title="Voice Coach for Teachers")
app.mount("/static", StaticFiles(directory=settings.base_dir / "app" / "static"), name="static")
templates = Jinja2Templates(directory=settings.base_dir / "app" / "templates")
store = LessonStore(settings.db_path)
transcriber = LocalWhisperTranscriber()


store.remove_demo_lessons()


def enrich(lesson):
    lesson = dict(lesson)
    lesson["word_count"] = count_words(lesson["transcript"])
    duration = lesson.get("duration_seconds")
    lesson["duration_label"] = f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else None
    lesson["wpm"] = round(lesson["word_count"] / (duration / 60)) if duration and duration > 0 else None
    return lesson


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"lessons": [enrich(x) for x in store.list()], "max_mb": settings.max_upload_mb})


@app.get("/lessons/{lesson_id}", response_class=HTMLResponse)
def lesson_page(request: Request, lesson_id: str):
    lesson = store.get(lesson_id)
    if not lesson:
        raise HTTPException(404, "Lesson not found.")
    return templates.TemplateResponse(request, "lesson.html", {"lesson": enrich(lesson)})


@app.get("/lessons/{lesson_id}/transcript.txt")
def download_transcript(lesson_id: str):
    lesson = store.get(lesson_id)
    if not lesson:
        raise HTTPException(404, "Lesson not found.")
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", lesson["title"]).strip("-").lower() or "transcript"
    return PlainTextResponse(lesson["transcript"], media_type="text/plain; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{safe}.txt"'})


def format_timestamp(seconds: float) -> str:
    milliseconds = round(float(seconds) * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


@app.get("/lessons/{lesson_id}/transcript.csv")
def download_transcript_csv(lesson_id: str):
    lesson = store.get(lesson_id)
    if not lesson:
        raise HTTPException(404, "Lesson not found.")
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", lesson["title"]).strip("-").lower() or "transcript"
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["start_time", "end_time", "text"])
    for segment in lesson["analysis"].get("segments", []):
        writer.writerow([format_timestamp(segment["start"]), format_timestamp(segment["end"]), segment["text"]])
    content = "\ufeff" + output.getvalue()
    return PlainTextResponse(content, media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{safe}.csv"'})


@app.post("/api/lessons")
async def upload_lesson(audio: UploadFile = File(...)):
    if not audio.filename or Path(audio.filename).suffix.lower() != ".mp3":
        raise HTTPException(415, "Please choose an MP3 file. Other audio formats are not accepted.")
    limit = settings.max_upload_mb * 1024 * 1024
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as handle:
            temp_path = Path(handle.name)
            digest_builder = hashlib.sha256()
            total_size = 0
            signature = b""
            while chunk := await audio.read(1024 * 1024):
                if not signature:
                    signature = chunk[:3]
                total_size += len(chunk)
                if total_size > limit:
                    raise HTTPException(413, f"The file is larger than the {settings.max_upload_mb} MB limit.")
                digest_builder.update(chunk)
                handle.write(chunk)
        if total_size == 0:
            raise HTTPException(400, "The selected file is empty.")
        if signature[:3] != b"ID3" and not (len(signature) > 1 and signature[0] == 0xFF and signature[1] & 0xE0 == 0xE0):
            raise HTTPException(415, "This file does not appear to be a valid MP3.")
        digest = digest_builder.hexdigest()
        try:
            duration = MP3(temp_path).info.length
        except (MutagenError, HeaderNotFoundError, OSError, ValueError):
            raise HTTPException(422, "The MP3 could not be read. It may be damaged or use an unsupported encoding.")
        result = transcriber.transcribe(temp_path)
        analysis = {"segments": result.segments}
        try:
            analysis["speech_quality"] = analyze_speech_quality(temp_path, result.text, result.segments, duration)
        except ValueError:
            analysis["speech_quality_warning"] = "Some acoustic speech-quality metrics could not be calculated for this recording."
        lesson_id = uuid.uuid4().hex[:12]
        title = Path(audio.filename).stem[:80] or "Classroom recording"
        store.save({"id": lesson_id, "audio_hash": digest, "title": title, "transcript": result.text,
                    "duration_seconds": duration, "analysis": analysis})
        return {"id": lesson_id, "cached": False}
    except HTTPException:
        raise
    except TranscriptionUnavailable as exc:
        raise HTTPException(503, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception:
        raise HTTPException(500, "Processing failed unexpectedly. Please try again or check the server logs.")
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)
