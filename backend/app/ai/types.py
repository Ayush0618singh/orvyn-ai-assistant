from dataclasses import dataclass


@dataclass(slots=True)
class AIAttachment:
    filename: str
    mime_type: str
    data: bytes