from psycopg_pool import ConnectionPool
import psycopg
from src.models import SystemPrompt
from psycopg.rows import TupleRow,class_row


SELECT_SYSTEM_PROMPT = """
SELECT
    key,
    prompt
FROM latest_system_prompts
WHERE key = %s;
"""

class SystemPromptNotFound(Exception):
    pass

class MessagesRepository:
    pool: ConnectionPool[psycopg.Connection[TupleRow]]

    def __init__(self, pool: ConnectionPool[psycopg.Connection[TupleRow]]):
        self.pool = pool

    def get_system_prompt(self, key: str) -> SystemPrompt:
        """
        Selects a system prompt by key
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(SystemPrompt)) as cur:
                cur.execute(
                    SELECT_SYSTEM_PROMPT,
                    (key, )
                )
                message = cur.fetchone()

                if not message:
                    raise SystemPromptNotFound(f"SystemPrompt {key} not found")
                return message
