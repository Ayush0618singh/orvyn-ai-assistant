from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Message sent by the user to ORVYN.",
    )


class ChatResponse(BaseModel):
    response: str
    model: str
    provider: str