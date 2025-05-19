from psycopg_pool import ConnectionPool
import psycopg
from src.models.conversation import Conversation
from psycopg.rows import TupleRow

GET_MESSAGES_OF_CONVERSATION = """
    SELECT message, timestamp, role, conversation_id
    FROM messages
    WHERE conversation_id = %s
        AND (%s::timestamptz IS NULL OR timestamp >= %s::timestamptz)
        AND (
            %s IS NOT TRUE OR role != 'system'
        )
    ORDER BY timestamp
    LIMIT 100;
"""

class ConversationsRepository:
    pool: ConnectionPool[psycopg.Connection[TupleRow]]

    def __init__(self, pool: ConnectionPool[psycopg.Connection[TupleRow]]):
        self.pool = pool  # Assignment, type already declared at class level

    def set_conversation(self, conversation: Conversation):
        """
        Inserts a sid_conversation_id record
        """
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO sid_conversation_ids (conversation_id, sid, "timestamp")
                        VALUES (%s, %s, %s)
                        ON CONFLICT (sid) DO UPDATE SET
                        conversation_id = EXCLUDED.conversation_id,
                        "timestamp" = EXCLUDED."timestamp";
                        """,
                        (
                            str(conversation.conversation_id),
                            conversation.sid,
                            conversation.timestamp
                        )
                    )
                    conn.commit()
        except psycopg.Error as e:
            print(f"Database error: {e}")
