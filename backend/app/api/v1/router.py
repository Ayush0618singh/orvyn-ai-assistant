
"""ORVYN API v1 router."""

from fastapi import APIRouter

from app.api.v1.routes import (
    agent_execution_monitoring,
    agent_execution_recovery,
    agent_executions,
    attachments,
    auth,
    auto_memory,
    chat,
    chat_tool_approvals,
    conversation_action_messages,
    conversations,
    documents,
    file_action_planner,
    health,
    memories,
    multilingual_file_planner,
    rag,
    tool_approvals,
    web,
    agent_plans,
)


api_router = APIRouter()


# =====================================================
# HEALTH AND AUTHENTICATION
# =====================================================

api_router.include_router(
    health.router
)

api_router.include_router(
    auth.router
)


# =====================================================
# CONVERSATIONS AND MESSAGES
# =====================================================

api_router.include_router(
    conversations.router
)

# Persist original user requests for agent/file actions.
# Authentication and conversation ownership are
# enforced by the route itself.
api_router.include_router(
    conversation_action_messages.router
)


# =====================================================
# ATTACHMENTS AND DOCUMENTS
# =====================================================

api_router.include_router(
    attachments.router
)

api_router.include_router(
    documents.router
)


# =====================================================
# RETRIEVAL, MEMORY AND WEB
# =====================================================

api_router.include_router(
    rag.router
)

api_router.include_router(
    memories.router
)

api_router.include_router(
    auto_memory.router
)

api_router.include_router(
    web.router
)


# =====================================================
# GEMINI / AGENT CHAT
# =====================================================

api_router.include_router(
    chat.router
)


# =====================================================
# AGENT EXECUTION AND MONITORING
# =====================================================

api_router.include_router(
    agent_executions.router
)

api_router.include_router(
    agent_execution_monitoring.router
)

api_router.include_router(
    agent_execution_recovery.router
)


# =====================================================
# SECURE TOOL APPROVALS
# =====================================================

api_router.include_router(
    tool_approvals.router
)

# Conversation-linked durable approvals.
api_router.include_router(
    chat_tool_approvals.router
)


# =====================================================
# FILE ACTION PLANNING
# =====================================================

# Deterministic natural-language file planner.
api_router.include_router(
    file_action_planner.router
)

# Gemini multilingual structured file planner.
api_router.include_router(
    multilingual_file_planner.router
)

api_router.include_router(
    agent_plans.router
)