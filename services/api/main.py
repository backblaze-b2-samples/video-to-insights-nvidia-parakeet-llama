import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

# Single source of truth: repo-root .env. Anchored to this file's path so it
# resolves correctly regardless of where uvicorn is invoked from.
REPO_ROOT_ENV = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(REPO_ROOT_ENV)

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.config import settings  # noqa: E402
from app.runtime import files, health, jobs  # noqa: E402

# Required B2 settings — declared with empty defaults so Settings() can be
# imported during test collection. We fail fast at startup with a clear
# message if any are missing or still hold the .env.example placeholders.
REQUIRED_B2_SETTINGS = (
    ("b2_endpoint", "B2_ENDPOINT"),
    ("b2_region", "B2_REGION"),
    ("b2_key_id", "B2_KEY_ID"),
    ("b2_application_key", "B2_APPLICATION_KEY"),
    ("b2_bucket_name", "B2_BUCKET_NAME"),
)

PLACEHOLDER_VALUES = frozenset({
    "your_b2_endpoint",
    "your_b2_region",
    "your_key_id",
    "your_application_key",
    "your-bucket-name",
})


@asynccontextmanager
async def lifespan(app: "FastAPI"):
    missing = [
        env_name
        for attr, env_name in REQUIRED_B2_SETTINGS
        if not getattr(settings, attr)
    ]
    if missing:
        raise RuntimeError(
            "Missing required B2 configuration: "
            + ", ".join(missing)
            + f". Add them to {REPO_ROOT_ENV} (see .env.example) and restart."
        )

    placeholders = [
        env_name
        for attr, env_name in REQUIRED_B2_SETTINGS
        if getattr(settings, attr) in PLACEHOLDER_VALUES
    ]
    if placeholders:
        raise RuntimeError(
            "B2 configuration still has placeholder values: "
            + ", ".join(placeholders)
            + f". Edit {REPO_ROOT_ENV} with your real B2 credentials and restart."
        )

    # Concurrency cap for the pipeline. State files are per-process — if
    # you scale horizontally, switch the repo for a shared store first.
    app.state.job_semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)
    app.state.background_tasks = set()
    try:
        yield
    finally:
        # Cancel awaiting pipeline tasks so the process can exit cleanly.
        # In-flight `to_thread` subprocess work isn't interrupted mid-syscall,
        # but the wrapping Python task is cancelled and its next `await`
        # raises `CancelledError`.
        for task in list(app.state.background_tasks):
            task.cancel()


# --- Structured JSON logging ---

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])
        return json.dumps(log_entry)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logging.root.handlers = [handler]
logging.root.setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


# --- App setup ---

app = FastAPI(
    title="Video to Insights Pipeline API",
    description="Paste a YouTube URL; get B2-hosted video + AI insights.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.api_cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(health.router, tags=["health"])
app.include_router(jobs.router, tags=["jobs"])
app.include_router(files.router, tags=["files"])
