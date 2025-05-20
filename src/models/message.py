from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Dict

class ChatMessage(BaseModel):
    role: str
    content: str

class Message(BaseModel):
    message: str
    timestamp: datetime
    role: str
    conversation_id: UUID

    def to_chat_message(self) -> Dict[str, str]:
        return { 'role': self.role, 'content': self.message }
