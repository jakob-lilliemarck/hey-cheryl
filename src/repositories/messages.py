from psycopg_pool import ConnectionPool
from uuid import UUID
from typing import Optional
import psycopg
from src.models import Message, Reply
from datetime import datetime
from psycopg.rows import TupleRow,class_row

INSERT_MESSAGE = """
    INSERT INTO messages (
        id,
        conversation_id,
        user_id,
        role,
        timestamp,
        message
    ) VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING *;
"""

SELECT_MESSAGE = """
    SELECT *
    FROM messages
    WHERE id = %s;
"""

SELECT_MESSAGES = """
    SELECT *
    FROM messages
    WHERE
        conversation_id = %s
        AND (%s::timestamptz IS NULL OR timestamp >= %s::timestamptz)
    ORDER BY timestamp
    LIMIT 50;
"""

SELECT_USER_IDS_OF_CONVERSATION = """
    SELECT DISTINCT(user_id)
    FROM messages
    WHERE conversation_id = %s;
"""

INSERT_REPLY = """
    INSERT INTO replies (
        id,
        timestamp,
        message_id,
        acknowledged,
        published,
        message
    ) VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING *;
"""

SELECT_REPLIES = """
SELECT *
FROM latest_replies
WHERE
    (
	    %(acknowledged)s::BOOL IS NULL
	    OR acknowledged = %(acknowledged)s::BOOL
    )
    AND (
	    %(completed)s::BOOL IS NULL
	    OR (message IS NOT NULL) = %(completed)s::BOOL
    )
	AND (
	    %(published)s::BOOL IS NULL
	    OR published = %(published)s::BOOL
    )
	AND (
	    %(message_id)s::UUID IS NULL
		OR message_id = %(message_id)s::UUID
	)
ORDER BY timestamp DESC
LIMIT %(limit)s::INTEGER;
"""

class MessageInsertionError(Exception):
    pass

class MessageNotFoundError(Exception):
    pass

class ReplyInsertionError(Exception):
    pass

class MessagesRepository:
    pool: ConnectionPool[psycopg.Connection[TupleRow]]

    def __init__(self, pool: ConnectionPool[psycopg.Connection[TupleRow]]):
        self.pool = pool

    def create_message(self, message: Message) -> Message:
        """
        Creates a new message record.
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(Message)) as cur:
                cur.execute(
                    INSERT_MESSAGE,
                    (
                        str(message.id),
                        str(message.conversation_id),
                        str(message.user_id),
                        message.role,
                        message.timestamp,
                        message.message,
                    ),
                )

                new_message = cur.fetchone()
                if not new_message:
                    raise MessageInsertionError("Failed to insert message")

                return new_message

    def get_message(
        self,
        *,
        message_id: UUID
    ) -> Message:
        """
        Selects a message by id
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(Message)) as cur:
                cur.execute(
                    SELECT_MESSAGE,
                    (str(message_id), )
                )
                message = cur.fetchone()

                if not message:
                    raise MessageNotFoundError(f"User {str(message_id)} not found")
                return message

    def get_messages(
        self,
        *,
        conversation_id: UUID,
        timestamp: Optional[datetime] = None
    ) -> list[Message]:
        """
        Retrieves messages for a given conversation ID, optionally filtering by timestamp.
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(Message)) as cur:
                cur.execute(
                    SELECT_MESSAGES,
                    (
                        str(conversation_id),
                        timestamp,
                        timestamp,
                    ),
                )

                return cur.fetchall()

    def get_user_ids_of_conversation(self, conversation_id: UUID) -> list[UUID]:
        """
        Selects all user ids of a conversation
        """
        with self.pool.connection() as conn:
            with conn.cursor() as cur:  # Remove row_factory=class_row(UUID)
                cur.execute(SELECT_USER_IDS_OF_CONVERSATION, (str(conversation_id), ))
                rows = cur.fetchall()
                return [row[0] for row in rows if row and row[0] is not None]

    def get_replies(
        self,
        *,
        acknowledged: bool | None,
        completed: bool | None,
        published: bool | None,
        message_id: UUID | None,
        limit: int
    ) -> list[Reply]:
        """
        Selects replies from Cheryl
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(Reply)) as cur:
                cur.execute(SELECT_REPLIES, {
                    'acknowledged': acknowledged,
                    'completed': completed,
                    'published': published,
                    'message_id': message_id,
                    'limit': limit
                })
                return cur.fetchall()

    def create_reply(self, reply: Reply) -> Reply:
        """
        Create a new reply record
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(Reply)) as cur:
                cur.execute(
                    INSERT_REPLY,
                    (
                        str(reply.id),
                        reply.timestamp,
                        str(reply.message_id),
                        reply.acknowledged,
                        reply.published,
                        reply.message,
                    ),
                )

                new_reply = cur.fetchone()
                if not new_reply:
                    raise ReplyInsertionError("Failed to insert reply")

                return new_reply
