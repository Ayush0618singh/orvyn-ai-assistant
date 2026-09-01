from pydantic import (
    BaseModel,
    Field,
    model_validator,
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

    @model_validator(
        mode="after"
    )
    def validate_content(
        self,
    ) -> "ChatRequest":
        self.message = (
            self.message.strip()
        )

        if (
            not self.message
            and not self.attachment_ids
        ):
            raise ValueError(
                "A message or attachment is required."
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

        return self


class ChatResponse(BaseModel):
    conversation_id: str

    user_message_id: str
    assistant_message_id: str

    response: str

    model: str
    provider: str