from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


ALLOWED_MEMORY_TYPES = {
    "fact",
    "preference",
    "instruction",
    "note",
    "profile",
}


class MemoryCreate(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
    )

    memory_type: str = Field(
        default="fact",
        max_length=30,
    )

    importance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )

    source_message_id: str | None = None

    @field_validator("content")
    @classmethod
    def clean_content(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "Memory content cannot be empty."
            )

        return cleaned

    @field_validator("memory_type")
    @classmethod
    def validate_memory_type(
        cls,
        value: str,
    ) -> str:
        cleaned = (
            value
            .lower()
            .strip()
        )

        if (
            cleaned
            not in ALLOWED_MEMORY_TYPES
        ):
            raise ValueError(
                "Unsupported memory type."
            )

        return cleaned


class MemoryUpdate(BaseModel):
    content: str | None = Field(
        default=None,
        min_length=1,
        max_length=5000,
    )

    memory_type: str | None = Field(
        default=None,
        max_length=30,
    )

    importance: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    is_active: bool | None = None

    @field_validator("content")
    @classmethod
    def clean_content(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "Memory content cannot be empty."
            )

        return cleaned

    @field_validator("memory_type")
    @classmethod
    def validate_memory_type(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned = (
            value
            .lower()
            .strip()
        )

        if (
            cleaned
            not in ALLOWED_MEMORY_TYPES
        ):
            raise ValueError(
                "Unsupported memory type."
            )

        return cleaned


class MemoryResponse(BaseModel):
    id: str

    user_id: str

    source_message_id: str | None

    memory_type: str

    content: str

    importance: float

    is_active: bool

    embedding_model: str | None

    created_at: datetime

    updated_at: datetime

    last_used_at: datetime | None

    model_config = {
        "from_attributes": True
    }


class MemorySearchRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=5000,
    )

    memory_types: list[str] = Field(
        default_factory=list,
        max_length=5,
    )

    limit: int = Field(
        default=5,
        ge=1,
        le=20,
    )

    min_similarity: float = Field(
        default=0.30,
        ge=-1.0,
        le=1.0,
    )

    @field_validator("query")
    @classmethod
    def clean_query(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "Search query cannot be empty."
            )

        return cleaned

    @field_validator("memory_types")
    @classmethod
    def validate_memory_types(
        cls,
        values: list[str],
    ) -> list[str]:
        cleaned_values: list[str] = []

        for value in values:
            cleaned = (
                value
                .lower()
                .strip()
            )

            if (
                cleaned
                not in ALLOWED_MEMORY_TYPES
            ):
                raise ValueError(
                    "Unsupported memory type."
                )

            if (
                cleaned
                not in cleaned_values
            ):
                cleaned_values.append(
                    cleaned
                )

        return cleaned_values


class MemorySearchResult(BaseModel):
    id: str

    memory_type: str

    content: str

    importance: float

    similarity: float