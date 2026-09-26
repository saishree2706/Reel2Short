"""Uvicorn entry point for the backend server."""
import uvicorn
from app.main import app

if __name__ == "__main__":
    from app.config import settings
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
        reload_dirs=["app"],
    )

