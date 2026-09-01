from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    await init_db()

    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "Backend API for ORVYN Personal Multilingual "
        "Agentic AI Assistant"
    ),
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)


allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

if (
    settings.frontend_url
    not in allowed_origins
):
    allowed_origins.append(
        settings.frontend_url
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    api_router,
    prefix=settings.api_v1_prefix,
)


@app.get(
    "/",
    tags=["Root"],
)
async def root():
    return {
        "name":
            settings.app_name,

        "message":
            "ORVYN API is running",

        "version":
            settings.app_version,

        "environment":
            settings.app_env,

        "docs":
            "/docs",

        "api":
            settings.api_v1_prefix,
    }