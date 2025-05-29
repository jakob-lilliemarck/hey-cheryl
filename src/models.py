from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
import enum
from typing import List

from pydantic.root_model import RootModel

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

class ReplyStatus(enum.Enum):
    PENDING = "pending"
    READY = "ready"
    PUBLISHED = "published"

class Reply(BaseModel):
    id: UUID
    timestamp: datetime
    message_id: UUID
    status: ReplyStatus
    message: str | None

class Concept(BaseModel):
    id: UUID
    timestamp: datetime
    concept: str
    meaning: str

class SystemPromptKey(enum.Enum):
    BASE = "base"

class SystemPrompt(BaseModel):
    key: SystemPromptKey
    prompt: str

# Response models
class ReplyingTo(BaseModel):
    user_id: UUID | None

class Role(enum.Enum):
    SYSTEM = "system"
    ASSISTANT = "assistant"
    USER = "user"

class ChatTemplateRecord(BaseModel):
    role: Role
    content: str

class ChatTemplate(RootModel[List[ChatTemplateRecord]]):
    pass
