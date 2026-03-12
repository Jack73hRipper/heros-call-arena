"""
Arena Prototype - Entry Point

Run with: uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.redis_client import redis_manager
from app.services.scheduler import scheduler_manager
from app.routes.lobby import router as lobby_router
from app.routes.match import router as match_router
from app.routes.town import router as town_router
from app.routes.maps import router as maps_router
from app.services.websocket import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    await redis_manager.connect()
    scheduler_manager.start()
    # Ensure player data directory exists (Phase 4E-1)
    data_dir = Path(__file__).resolve().parent.parent / "data" / "players"
    data_dir.mkdir(parents=True, exist_ok=True)
    print(f"[Arena] Server started — tick rate: {settings.TICK_RATE_SECONDS}s")
    yield
    # Shutdown
    scheduler_manager.shutdown()
    await redis_manager.disconnect()
    print("[Arena] Server shut down.")


app = FastAPI(
    title="Arena Prototype",
    description="Turn-based multiplayer combat arena — Phase 1",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(lobby_router, prefix="/api/lobby", tags=["Lobby"])
app.include_router(match_router, prefix="/api/match", tags=["Match"])
app.include_router(town_router, prefix="/api/town", tags=["Town"])
app.include_router(maps_router, prefix="/api/maps", tags=["Maps"])
app.include_router(ws_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


# ── Standalone entry point (used by PyInstaller bundle) ─────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
