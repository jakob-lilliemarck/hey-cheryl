from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class Conversation(BaseModel):
    sid: UUID
    conversation_id: UUID
    timestamp: datetime
