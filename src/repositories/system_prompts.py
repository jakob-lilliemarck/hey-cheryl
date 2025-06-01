from psycopg_pool import ConnectionPool
import psycopg
from src.models import SystemPrompt
from psycopg.rows import TupleRow,class_row
from typing import List
from datetime import datetime

SELECT_SYSTEM_PROMPT = """
SELECT
    key,
    prompt,
    timestamp
FROM latest_system_prompts
WHERE key = %(key)s;
"""

SELECT_SYSTEM_PROMPTS = """
SELECT
    key,
    prompt,
    timestamp
FROM latest_system_prompts;
"""

BATCH_INSERT_SYSTEM_PROMPTS = """
INSERT INTO system_prompts (
    key,
    prompt,
    timestamp
)
SELECT *
FROM UNNEST(
    %s::TEXT[],
    %s::TEXT[],
    %s::TIMESTAMPTZ[]
)
RETURNING *
"""

class SystemPromptNotFound(Exception):
    pass

class SystemPromptInsertionError(Exception):
    pass

class SystemPromptsRepository:
    pool: ConnectionPool[psycopg.Connection[TupleRow]]

    def __init__(self, pool: ConnectionPool[psycopg.Connection[TupleRow]]):
        self.pool = pool

    def get_system_prompt(self, key: str) -> SystemPrompt:
        """Selects a system prompt by key"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(SystemPrompt)) as cur:
                cur.execute(
                    SELECT_SYSTEM_PROMPT, {
                        "key": key
                    }
                )
                prompt = cur.fetchone()

                if not prompt:
                    raise SystemPromptNotFound(f"SystemPrompt {key} not found")
                return prompt

    def get_system_prompts(self) -> List[SystemPrompt]:
        """Retrieves all system prompts"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(SystemPrompt)) as cur:
                cur.execute(SELECT_SYSTEM_PROMPTS)
                return cur.fetchall()

    def upsert_system_prompts(
        self, *,
        system_prompts: List[SystemPrompt]
    ) -> List[SystemPrompt]:
        if not system_prompts:
            return []

        keys: List[str] = []
        prompts: List[str] = []
        timestamps: List[datetime] = []
        for sp in system_prompts:
            keys.append(sp.key.value)
            prompts.append(sp.prompt)
            timestamps.append(sp.timestamp)

        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(SystemPrompt)) as cur:
                params = (keys, prompts, timestamps)
                cur.execute(
                    BATCH_INSERT_SYSTEM_PROMPTS,
                    params
                )
                return cur.fetchall()
