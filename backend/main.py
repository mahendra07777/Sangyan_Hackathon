import asyncio
import logging
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as document_router
from app.api.compare_routes import compare_router
from app.services.comparison_session_store import session_store

logger = logging.getLogger(__name__)

# Load variables from .env into environment
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: cleans orphan comparison storage on startup and runs periodic expiration sweeper."""
    # 1. Startup orphan cleanup
    cleaned_count = session_store.startup_cleanup_orphans()
    if cleaned_count > 0:
        logger.info(f"Startup clean: removed {cleaned_count} orphan comparison directories.")

    # 2. Start background session expiration sweeper (runs every 5 minutes)
    sweeper_stop_event = asyncio.Event()

    async def _sweep_loop():
        while not sweeper_stop_event.is_set():
            try:
                await asyncio.sleep(300)
                session_store.sweep_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f"Error in session expiration sweeper: {exc}")

    sweeper_task = asyncio.create_task(_sweep_loop())

    try:
        yield
    finally:
        # 3. Shutdown cleanup
        sweeper_stop_event.set()
        sweeper_task.cancel()
        try:
            await sweeper_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Bharat Investor Copilot API",
    description="Backend API for Document Ingestion, Processing, and Comparison",
    version="0.2.0",
    lifespan=lifespan,
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(document_router)
app.include_router(compare_router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
