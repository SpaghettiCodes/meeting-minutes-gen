# Meeting Minute Generator

Upload transcripts (or transcribe audio/video), pick a template, and generate meeting minutes with Google Gemini.

## Setup

1. Copy `.env.example` to `.env`
2. Add your Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

## Run

```bash
docker compose up --build
```

Open http://localhost:5173

Demo files live in `data/transcripts/` and `data/templates/`. Generated minutes go to `data/output/`.

No local GPU or vLLM stack required — generation and transcription call Gemini in the cloud.
