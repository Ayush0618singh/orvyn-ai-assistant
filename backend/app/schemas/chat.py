from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
    )

    conversation_id: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str

    user_message_id: str
    assistant_message_id: str

    response: str

    model: str
    provider: str