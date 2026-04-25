"""FastAPI application factory for api_gateway."""

import logging

from fastapi import FastAPI

from api_gateway.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    force=True,
)

app = FastAPI(title="api_gateway")
app.include_router(router)
