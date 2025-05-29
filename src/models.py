from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

# Domain models
class User(BaseModel):
    id: UUID
    name: str
    timestamp: datetime

class UserSession(BaseModel):
    id: UUID
    user_id: UUID
    timestamp: datetime
    event: str

class Message(BaseModel):
    id: UUID
    conversation_id: UUID
    user_id: UUID
    role: str
    timestamp: datetime
    message: str

class Reply(BaseModel):
    id: UUID
    timestamp: datetime
    message_id: UUID
    status: str
    message: str | None

class Concept(BaseModel):
    id: UUID
    concept: str
    meaning: str

# Response models
class ReplyingTo(BaseModel):
    user_id: UUID | None
