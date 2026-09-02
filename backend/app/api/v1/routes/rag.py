from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.rag import (
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSourceResponse,
)
from app.services.rag_service import rag_service


router = APIRouter(
    prefix="/rag",
    tags=["RAG"],
)


@router.post(
    "/retrieve",
    response_model=RAGQueryResponse,
)
async def retrieve_rag_context(
    payload: RAGQueryRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
):
    query = payload.query.strip()

    try:
        chunks = await rag_service.retrieve(
            db=db,
            user_id=current_user.id,
            query=query,
            document_ids=(
                payload.document_ids
                or None
            ),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to retrieve "
                "document context."
            ),
        ) from exc

    return RAGQueryResponse(
        query=query,
        sources=[
            RAGSourceResponse(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_name=chunk.document_name,
                chunk_index=chunk.chunk_index,
                similarity=round(
                    chunk.similarity,
                    4,
                ),
                content=chunk.content,
            )
            for chunk in chunks
        ],
    )