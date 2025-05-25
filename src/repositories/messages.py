from psycopg_pool import ConnectionPool
from uuid import UUID
from typing import Optional
import psycopg
from src.models import Message
from pydantic import ValidationError
from datetime import datetime
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

SET_MESSAGE = """
    INSERT INTO messages (conversation_id, timestamp, message, role)
    VALUES (%s, %s, %s, %s);
"""

class MessagesRepository:
    pool: ConnectionPool[psycopg.Connection[TupleRow]]

    def __init__(self, pool: ConnectionPool[psycopg.Connection[TupleRow]]):
        self.pool = pool

    def set_message(self, message: Message):
        """
        Inserts a message record.
        """
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        SET_MESSAGE,
                        (
                            str(message.conversation_id),
                            message.timestamp,
                            message.message,
                            message.role
                        ),
                    )
                    conn.commit()
        except psycopg.Error as e:
            print(f"Database error: {e}")

    def get_messages_of_conversation(
        self,
        conversation_id: UUID,
        exclude_system_prompts: bool,
        timestamp: Optional[datetime] = None
    ) -> list[Message]:
        """
        Retrieves messages for a given conversation ID, optionally filtering by timestamp.
        """

        messages: list[Message] = []
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        GET_MESSAGES_OF_CONVERSATION,
                        (
                            str(conversation_id),
                            timestamp,
                            timestamp,
                            exclude_system_prompts
                        ),
                    )
                    for row in cur.fetchall():
                        try:
                            message = Message(
                                message=row[0],
                                timestamp=row[1],
                                role=row[2],
                                conversation_id=row[3]
                            )
                            messages.append(message)
                        except ValidationError as e:
                            print(f"Validation error for message: {row} - {e}")
        except psycopg.Error as e:
            print(f"Database error: {e}")
        return messages
