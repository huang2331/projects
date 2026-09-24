FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-transcription.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements-transcription.txt
COPY . .
RUN mkdir -p /app/data
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

