"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .api import health, instagram, videos, jobs, auth, youtube


def create_app() -> FastAPI:
    app = FastAPI(
        title="Reel2Short API",
        version="3.0.0",
        description="Instagram → YouTube Shorts conversion pipeline",
    )

    # CORS — allow the Vite dev server and same-origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router)
    app.include_router(instagram.router)
    app.include_router(videos.router)
    app.include_router(jobs.router)
    app.include_router(auth.router)
    app.include_router(youtube.router)

    @app.on_event("startup")
    async def startup():
        settings.ensure_dirs()
        init_db()

    return app


app = create_app()
