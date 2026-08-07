from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.routes import router as auth_router
from app.config import get_settings
from app.database import SessionLocal
from app.export.routes import router as export_router
from app.pipeline.routes import router as pipeline_router
from app.projects.routes import router as projects_router
from app.prompts.seed import seed_prompts
from app.requirements.routes import router as requirements_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure prompt templates exist so agents always have an active prompt.
    db = SessionLocal()
    try:
        seed_prompts(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Multi-Agent AI Test Framework", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(requirements_router)
app.include_router(pipeline_router)
app.include_router(export_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


_PROVIDER_LABEL = {
    "gemini": "Google Gemini",
    "anthropic": "Anthropic Claude",
    "ollama": "Ollama (local)",
    "mock": "Mock (offline stub)",
}


@app.get("/meta/llm", tags=["meta"])
def llm_meta() -> dict:
    """What's actually powering the agents — so the UI can show it and the user
    can confirm real AI (not the offline stub) is in use."""
    provider = settings.llm_provider.lower().strip()
    is_mock = provider == "mock"
    key_missing = (
        (provider == "gemini" and not settings.gemini_api_key)
        or (provider == "anthropic" and not settings.anthropic_api_key)
    )
    return {
        "provider": provider,
        "provider_label": _PROVIDER_LABEL.get(provider, provider),
        "model": settings.effective_model,
        "is_mock": is_mock,
        "ready": not is_mock and not key_missing,
        "key_missing": key_missing,
    }


@app.get("/meta/models", tags=["meta"])
def model_catalog() -> dict:
    """The free models offered in the UI dropdown, each flagged `ready` when its
    provider's key/host is configured. `default` is the currently active model."""
    from app.llm import catalog

    return {
        "models": catalog.annotated(settings),
        "default": {"provider": settings.llm_provider.lower().strip(), "model": settings.effective_model},
    }
