# Meeting Minute Generator

Upload transcripts (or transcribe audio/video), pick a template, and generate meeting minutes.

## Setup

1. Copy `.env.example` to `.env`
2. Run llama.cpp (port 8002) for generation + template conversion
3. Run WhisperX microservice (port 8000) for transcription + diarization

## Run

```bash
docker compose up --build
```

Open http://localhost:5173

Demo files live in `data/transcripts/` and `data/templates/`. Generated minutes go to `data/output/`.

## Config

| Variable | Used for |
|----------|----------|
| `LLM_BASE_URL` | Minutes generation, template conversion |
| `LLM_MODEL` | Copy `id` from `GET /v1/models` on your llama.cpp server |
| `WHISPERX_BASE_URL` | WhisperX `/diarize` endpoint (video/audio upload) |
| `TRANSCRIPTION_LANGUAGE` | Language code passed to WhisperX (default `en`) |
| `WHISPERX_REQUEST_TIMEOUT` | Max seconds to wait for transcription (default 3600) |

When backend runs in Docker, use `host.docker.internal` instead of `localhost` for service URLs.
