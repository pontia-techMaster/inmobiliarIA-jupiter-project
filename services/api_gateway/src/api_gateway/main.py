"""FastAPI application factory for api_gateway."""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api_gateway.results_store import start_consumer
from api_gateway.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    force=True,
)

_log = logging.getLogger("api_gateway.main")


def _ensure_table_background() -> None:
    """Create the local user-searches table on a daemon thread so a slow
    DDB-local startup never blocks uvicorn from accepting requests."""

    def _run() -> None:
        try:
            from shared.ddb import ensure_user_searches_table

            ensure_user_searches_table()
        except Exception:
            _log.exception("ensure_user_searches_table failed")

    threading.Thread(target=_run, name="ensure-user-searches-table", daemon=True).start()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Background thread that drains ``search-responses`` into the in-memory
    # store served by ``GET /results/{id}``. Daemonized so it dies with uvicorn.
    start_consumer()
    # Idempotent — local DDB only; cloud no-ops. Runs off-thread so a
    # not-yet-ready DDB container can't block startup.
    _ensure_table_background()
    yield


app = FastAPI(title="api_gateway", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
