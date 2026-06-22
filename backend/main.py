from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.dependencies import get_health_service
from backend.models.config import ENV_FILE, load_config
from backend.routers import export, generation, minutes, tasks, templates, transcripts
from backend.schemas import HealthResponse
from backend.services.health import HealthService
from backend.services.tasks import TaskService


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config(ENV_FILE)
    task_service = TaskService(config)
    app.state.task_service = task_service
    await task_service.start_worker()
    yield
    await task_service.stop_worker()
    task_service.close()


app = FastAPI(
    title="Meeting Minutes API",
    description="Upload transcripts and templates, convert PDF/DOCX examples to templates, and generate meeting minutes via Google Gemini.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transcripts.router, prefix="/api")
app.include_router(templates.router, prefix="/api")
app.include_router(minutes.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(generation.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")


@app.get("/api/health", response_model=HealthResponse, tags=["health"])
def health(service: HealthService = Depends(get_health_service)) -> HealthResponse:
    return service.get_health()
