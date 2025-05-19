from pydantic import BaseModel

class Concept(BaseModel):
    id: int
    concept: str
    meaning: str
