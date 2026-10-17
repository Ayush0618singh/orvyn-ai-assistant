
from fastapi import APIRouter

from app.api.v1.routes import (
    agent_executions,
    attachments,
    auth,
    auto_memory,
    chat,
    conversations,
    documents,
    health,
    memories,
    rag,
    web,
)


api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(conversations.router)
api_router.include_router(attachments.router)
api_router.include_router(documents.router)
api_router.include_router(rag.router)
api_router.include_router(memories.router)
api_router.include_router(auto_memory.router)
api_router.include_router(web.router)
api_router.include_router(chat.router)

# Phase 10J-E4: Authenticated execution history.
api_router.include_router(agent_executions.router)
