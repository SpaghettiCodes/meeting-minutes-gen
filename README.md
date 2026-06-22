# Meeting Minute Generator

Upload transcripts (or transcribe audio/video), pick a template, and generate meeting minutes.

## Setup

1. Copy `.env.example` to `.env`
2. Run local llama.cpp (port 8002) for generation + template conversion
3. Run local vLLM Whisper (port 8000) for transcription

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
| `WHISPER_BASE_URL` | Audio/video transcription |
| `WHISPER_MODEL` | Whisper model name on vLLM |

When backend runs in Docker, use `host.docker.internal` instead of `localhost` for both URLs.
