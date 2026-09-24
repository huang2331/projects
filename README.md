# Voice Coach for Teachers

A complete English-language FastAPI website that turns classroom MP3 recordings into a multidimensional speech-quality dashboard and downloadable timestamped transcripts in TXT and CSV formats. Transcript text is intentionally not rendered in the browser.

## Architecture

- **FastAPI + Jinja + vanilla JavaScript/CSS:** responsive server-rendered dashboard with an async upload experience.
- **faster-whisper:** free local speech-to-text. The default `base.en` model is downloaded on first use; no transcription API is required.
- **SQLite:** lesson history. Every upload creates a new analysis, even when the same MP3 was uploaded before. Audio is written only to a temporary file and deleted after processing.
- **Mutagen:** validates MP3 readability and reads real duration; pace is only shown when duration is available.
- **PyAV + NumPy:** locally calculates timing, pausing, pitch/prosody, vocal dynamics, speech-band clarity proxy, and filler-word metrics. No additional paid service is used.

File transcription through an API would be a separate paid capability, so this project deliberately uses free local Whisper instead.

## Run locally

Python 3.11 is recommended. Install [FFmpeg](https://ffmpeg.org/) and make it available on `PATH` (the PyAV wheel used by faster-whisper usually bundles decoding libraries, but FFmpeg is useful for creating/debugging audio).

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-transcription.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. The first real upload downloads the selected Whisper model. `base.en` is roughly 150 MB and commonly needs about 0.5–1 GB RAM while running; CPU transcription can be slower than the recording. Use `tiny.en` on constrained machines for lower accuracy and lower memory use.

## Validation and limits

- MP3 only, 100 MB by default (`MAX_UPLOAD_MB`). Extension, size, empty content, MP3 signature, and decoder readability are checked.
- Timestamps are shown only when faster-whisper returns real segments. The CSV contains `start_time`, `end_time`, and `text`, encoded as UTF-8 with a BOM for Excel compatibility.
- Speech-quality metrics are descriptive signals, not grades. The acoustic clarity metric is a speech-band energy proxy and must not be interpreted as pronunciation accuracy, student comprehension, or teaching effectiveness.
- Original audio is deleted after processing. Existing records created before speech-quality analysis was added must be re-uploaded because acoustic metrics cannot be reconstructed from text alone.
- SQLite works well locally and on one persistent instance. On ephemeral free hosting, records disappear when the container is replaced or redeployed; concurrent multi-instance deployments also need a shared database, which is intentionally not included.
- Upload limits may also be imposed by the hosting proxy. A 100 MB application limit is configured, but confirm the provider's current request-body and timeout limits before public use. Large recordings also require substantially more processing time and temporary memory.

## Tests

```powershell
pip install -r requirements-dev.txt
pytest -q
```

The suite covers word counting, acoustic metrics, validation errors, removal of the default demo, UTF-8 TXT download, timestamped CSV output, and an end-to-end upload flow using a real MP3 fixture with transcription stubbed for speed and repeatability.

## Free deployment (Render blueprint)

The included `Dockerfile` installs the local transcriber and `render.yaml` defines a free web service using `tiny.en`.

1. Push this repository to GitHub.
2. In Render, choose **New → Blueprint**, connect the repository, and apply `render.yaml`.
3. Wait for the image build and model download on first upload, then test with a short MP3.

Important limitations: free instances can sleep, have ephemeral disk, limited RAM/CPU, and request timeouts. Local Whisper may be slow or exceed memory on long recordings. Although the application accepts up to 100 MB, use short recordings when testing on a free CPU tier; it cannot guarantee production-scale transcription. Provider plans and limits change, so verify current Render limits before deploying. No public URL is claimed until it has been deployed and tested.

The upload endpoint streams incoming files to a random temporary file in 1 MB chunks, so a 100 MB upload is not duplicated in application memory. Render's reverse proxy and request timeout can still reject or interrupt a long upload or transcription before the application finishes.

## Privacy and security

Uploaded filenames are never used as filesystem paths. Audio is processed from a random OS temporary filename and removed in a `finally` block. The app stores transcripts and speech-quality metrics in SQLite, so do not upload sensitive student data to a public deployment. Add authentication and a retention policy before real institutional use.
