import csv
import io
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, store

client = TestClient(app)


def test_home_has_no_default_demo_or_feedback():
    page = client.get("/")
    assert page.status_code == 200
    assert "View demo" not in page.text
    assert "Teaching suggestions" not in page.text
    assert client.get("/lessons/demo").status_code == 404


def test_upload_rejects_wrong_extension_and_empty_file():
    wrong = client.post("/api/lessons", files={"audio": ("lesson.wav", b"abc", "audio/wav")})
    assert wrong.status_code == 415
    empty = client.post("/api/lessons", files={"audio": ("lesson.mp3", b"", "audio/mpeg")})
    assert empty.status_code == 400
    damaged = client.post("/api/lessons", files={"audio": ("lesson.mp3", b"ID3not-really-audio", "audio/mpeg")})
    assert damaged.status_code == 422


def test_full_upload_flow_with_transcriber_stub(monkeypatch, tmp_path):
    from app.transcription import TranscriptResult
    from app.storage import LessonStore
    import app.main as main
    monkeypatch.setattr(main, "store", LessonStore(tmp_path / "test.db"))
    fixture = Path(__file__).parent / "fixtures" / "test.mp3"
    if not fixture.exists():
        return
    monkeypatch.setattr(main.transcriber, "transcribe", lambda _: TranscriptResult("Welcome to our lesson about gravity. Gravity pulls objects toward Earth.", [{"start": 0.25, "end": 2.75, "text": "Welcome to our lesson about gravity."}, {"start": 2.75, "end": 5.1, "text": "Gravity pulls objects toward Earth."}]))
    monkeypatch.setattr(main, "analyze_speech_quality", lambda *args: {"speech_rate_wpm": 120, "articulation_rate_wpm": 145, "speaking_ratio_percent": 82.0, "pause_ratio_percent": 18.0, "average_pause_seconds": 0.4, "long_pause_count": 1, "pitch_median_hz": 180.0, "pitch_range_semitones": 5.2, "dynamic_range_db": 12.0, "clarity_proxy_percent": 76.0, "filler_count": 1, "fillers_per_100_words": 1.5})
    response = client.post("/api/lessons", files={"audio": ("gravity.mp3", fixture.read_bytes() + b"speech-quality-v2", "audio/mpeg")})
    assert response.status_code == 200
    lesson_id = response.json()["id"]
    assert client.get(f"/lessons/{lesson_id}").status_code == 200
    page = client.get(f"/lessons/{lesson_id}")
    assert "Teaching suggestions" not in page.text
    assert "CONTENT OVERVIEW" not in page.text
    assert "TOPICS" not in page.text
    assert "SPEECH QUALITY" in page.text
    assert "Welcome to our lesson about gravity" not in page.text
    assert "Download .csv" in page.text
    txt = client.get(f"/lessons/{lesson_id}/transcript.txt")
    assert "Gravity pulls objects" in txt.text
    assert "attachment" in txt.headers["content-disposition"]
    csv_download = client.get(f"/lessons/{lesson_id}/transcript.csv")
    rows = list(csv.reader(io.StringIO(csv_download.content.decode("utf-8-sig"))))
    assert csv_download.status_code == 200
    assert rows == [["start_time", "end_time", "text"], ["00:00:00.250", "00:00:02.750", "Welcome to our lesson about gravity."], ["00:00:02.750", "00:00:05.100", "Gravity pulls objects toward Earth."]]

    repeated = client.post("/api/lessons", files={"audio": ("gravity.mp3", fixture.read_bytes() + b"speech-quality-v2", "audio/mpeg")})
    assert repeated.status_code == 200
    assert repeated.json()["id"] != lesson_id
    repeated_page = client.get(f"/lessons/{repeated.json()['id']}")
    assert "SPEECH QUALITY" in repeated_page.text
