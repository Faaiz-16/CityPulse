"""FastAPI application entry point.

Run with:  uvicorn app.main:app --reload   (from the backend/ folder)
"""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.services.pipeline import CityPulse
from app.simulation.controller import SimulationError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("citypulse")


async def _run_loop(pipeline: CityPulse, every: float) -> None:
    while True:
        await asyncio.sleep(every)
        try:
            await asyncio.to_thread(pipeline.tick)
        except Exception:  # tick() already logs; the loop must never die
            log.exception("background tick failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    pipeline = CityPulse(settings)
    await asyncio.to_thread(pipeline.startup)
    app.state.pipeline = pipeline
    task = asyncio.create_task(_run_loop(pipeline, settings.tick_seconds)) if settings.run_background_loop else None
    log.info("CityPulse ready (live APIs: %s, AI: %s)", settings.live_apis, pipeline.summarizer.status)
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CityPulse API",
        description="Civic data fusion: normalized feeds, anomalies, possible relationships and "
                    "plain-language summaries for a demonstration city.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    from app.api.routes import router
    app.include_router(router)

    @app.exception_handler(SimulationError)
    async def simulation_error(_: Request, exc: SimulationError):
        return JSONResponse(status_code=400, content={"error": "invalid_simulation", "detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        fields = [".".join(str(p) for p in e["loc"][1:]) + ": " + e["msg"] for e in exc.errors()]
        return JSONResponse(status_code=422, content={"error": "invalid_request", "detail": fields})

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception):
        log.exception("unhandled error")  # full details stay in the server log only
        return JSONResponse(status_code=500, content={
            "error": "internal_error",
            "detail": "Something went wrong on our side. The rest of CityPulse keeps running."})

    return app


app = create_app()
