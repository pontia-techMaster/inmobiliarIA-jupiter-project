"""FastAPI application factory for api_gateway."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api_gateway.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    force=True,
)

app = FastAPI(title="api_gateway")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
