from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class User(BaseModel):
    id: UUID
    name: str
    timestamp: datetime

class UserSession(BaseModel):
    id: UUID
    user_id: UUID
    timestamp: datetime

class Message(BaseModel):
    id: UUID
    conversation_id: UUID
    user_id: UUID
    role: str
    timestamp: datetime
    message: str

class Concept(BaseModel):
    id: UUID
    concept: str
    meaning: str
