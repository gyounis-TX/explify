from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.middleware import add_cors_middleware
from api.routes import router
from server import find_free_port, start_server
from storage import get_db, get_keychain


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    get_db()
    get_keychain()
    yield
    # Shutdown (nothing to do currently)


def create_app() -> FastAPI:
    app = FastAPI(title="Explify Sidecar", version="0.3.0", lifespan=lifespan)
    add_cors_middleware(app)
    app.include_router(router)
    return app


if __name__ == "__main__":
    port = find_free_port()
    app = create_app()
    start_server(app, port)
