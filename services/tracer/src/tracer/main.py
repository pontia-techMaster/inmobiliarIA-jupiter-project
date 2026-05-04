"""Tracer FastAPI app.

Endpoints:
- ``GET /``                   — small HTML UI
- ``GET /traces``             — recent request_ids (JSON)
- ``GET /trace/{request_id}`` — full timeline for one request (JSON)
- ``GET /health``             — liveness probe
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from tracer.collector import CollectorManager
from tracer.store import TraceStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    force=True,
)

store = TraceStore(capacity=500)
collector = CollectorManager(store=store)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    collector.start()
    yield
    collector.stop()


app = FastAPI(title="tracer", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


_INDEX_HTML = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _INDEX_HTML


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/traces")
def traces(limit: int = 50) -> dict:
    items = [
        {
            "request_id": t.request_id,
            "first_seen": t.entries[0].timestamp if t.entries else None,
            "last_seen": t.entries[-1].timestamp if t.entries else None,
            "services": sorted({e.service for e in t.entries}),
            "entry_count": len(t.entries),
        }
        for t in store.recent(limit=limit)
    ]
    return {"traces": items}


@app.get("/trace/{request_id}")
def trace(request_id: str) -> dict:
    t = store.get(request_id)
    if t is None:
        raise HTTPException(status_code=404, detail="trace not found (yet)")
    return {
        "request_id": t.request_id,
        "entries": [asdict(e) for e in t.entries],
    }
