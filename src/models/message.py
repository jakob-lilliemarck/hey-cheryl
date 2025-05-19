from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class Message(BaseModel):
    message: str
    timestamp: datetime
    role: str
    conversation_id: UUID
