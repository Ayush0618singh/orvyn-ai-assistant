from pydantic import (
    BaseModel,
    Field,
    model_validator,
)

from app.schemas.rag import (
    RAGSourceResponse,
)
from app.schemas.web_source import (
    WebSourceResponse,
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(
        default="",
        max_length=10000,
    )

    conversation_id: str | None = None

    attachment_ids: list[str] = Field(
        default_factory=list,
        max_length=5,
    )

    document_ids: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    web_allowed: bool = Field(
        default=True,
        description=(
            "Controls whether this chat request "
            "is allowed to access the public web."
        ),
    )

    @model_validator(mode="after")
    def validate_content(
        self,
    ) -> "ChatRequest":
        self.message = (
            self.message.strip()
        )

        if (
            not self.message
            and not self.attachment_ids
            and not self.document_ids
        ):
            raise ValueError(
                "A message, attachment, or document is required."
            )

        if (
            len(
                set(
                    self.attachment_ids
                )
            )
            != len(
                self.attachment_ids
            )
        ):
            raise ValueError(
                "Duplicate attachments are not allowed."
            )

        if (
            len(
                set(
                    self.document_ids
                )
            )
            != len(
                self.document_ids
            )
        ):
            raise ValueError(
                "Duplicate document IDs are not allowed."
            )

        return self


class ChatResponse(BaseModel):
    conversation_id: str

    user_message_id: str
    assistant_message_id: str

    response: str

    model: str
    provider: str

    sources: list[
        RAGSourceResponse
    ] = Field(
        default_factory=list
    )

    web_sources: list[
        WebSourceResponse
    ] = Field(
        default_factory=list
    )