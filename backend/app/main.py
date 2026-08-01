from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.routes import router as auth_router
from app.config import get_settings
from app.database import SessionLocal
from app.modules.routes import router as modules_router
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
app.include_router(modules_router)
app.include_router(requirements_router)
app.include_router(pipeline_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
