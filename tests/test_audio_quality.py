from pathlib import Path

from app.audio_quality import analyze_speech_quality


def test_audio_quality_metrics_from_real_mp3():
    fixture = Path(__file__).parent / "fixtures" / "test.mp3"
    result = analyze_speech_quality(
        fixture,
        "Um gravity pulls objects toward Earth.",
        [{"start": 0.1, "end": 0.8, "text": "Um gravity pulls objects toward Earth."}],
        1.0,
    )
    assert result["speech_rate_wpm"] == 360
    assert result["articulation_rate_wpm"] == 514
    assert result["speaking_ratio_percent"] == 70.0
    assert result["pause_ratio_percent"] == 30.0
    assert result["filler_count"] == 1
    assert result["clarity_proxy_percent"] is not None
