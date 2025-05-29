from psycopg_pool import ConnectionPool
import psycopg
from psycopg.rows import TupleRow, class_row
from src.models import User, UserSession
from uuid import UUID

INSERT_USER = """
    INSERT INTO users (id, name, timestamp)
    VALUES (%s, %s, %s)
    RETURNING *;
"""

SELECT_USER = """
    SELECT *
    FROM users
    WHERE id = %s;
"""

SELECT_CONNECTED_USER_IDS = """
    SELECT user_id
    FROM latest_user_sessions
    WHERE event = 'connected'
"""

SELECT_USERS_BY_IDS = """
    SELECT *
    FROM users
    WHERE id = ANY(%s);
"""

INSERT_USER_SESSION = """
    INSERT INTO user_sessions (id, user_id, timestamp, event)
    VALUES (%s, %s, %s, %s)
    RETURNING *;
"""

SELECT_USER_SESSION = """
    SELECT id, user_id, timestamp, event
    FROM user_sessions
    WHERE id = %s;
"""

SELECT_LATEST_USER_SESSION = """
    SELECT id, user_id, timestamp, event
    FROM latest_user_sessions
    WHERE user_id = %s;
"""

class UserInsertionError(Exception):
    pass

class UserNotFoundError(Exception):
    pass

class UserSessionNotFoundError(Exception):
    pass

class UserSessionInsertionError(Exception):
    pass


class UsersRepository:
    pool: ConnectionPool[psycopg.Connection[TupleRow]]

    def __init__(self, pool: ConnectionPool[psycopg.Connection[TupleRow]]):
        self.pool = pool

    def create_user(self, user: User) -> User:
        """
        Inserts a user record
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(User)) as cur:
                cur.execute(
                    INSERT_USER,
                    (
                        user.id,
                        user.name,
                        user.timestamp
                    )
                )

                new_user = cur.fetchone()
                if not new_user:
                    raise UserInsertionError("Failed to insert user")

                return new_user

    def get_user(self, user_id: UUID) -> User:
        """
        Selects a user by id
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(User)) as cur:
                cur.execute(
                    SELECT_USER,
                    (str(user_id), )
                )

                user = cur.fetchone()

                if not user:
                    raise UserNotFoundError(f"User {str(user_id)} not found")

                return user

    def get_connected_user_ids(self) -> list[UUID]:
        """
        Selects all connected users
        """
        with self.pool.connection() as conn:
            with conn.cursor() as cur:  # Remove row_factory=class_row(UUID)
                cur.execute(SELECT_CONNECTED_USER_IDS)
                rows = cur.fetchall()
                return [row[0] for row in rows if row and row[0] is not None]

    def get_users_by_id(self, user_ids: list[UUID]) -> list[User]:
        """
        Selects all connected users
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(User)) as cur:
                cur.execute(SELECT_USERS_BY_IDS, (user_ids, ))
                return cur.fetchall()

    def create_user_session(self, user_session: UserSession) -> UserSession:
        """
        Inserts a user session record
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(UserSession)) as cur:
                cur.execute(
                    INSERT_USER_SESSION,
                    (
                        user_session.id,
                        user_session.user_id,
                        user_session.timestamp,
                        user_session.event
                    )
                )

                new_user_session = cur.fetchone()
                if not new_user_session:
                    raise UserSessionInsertionError("Failed to insert user session")

                return new_user_session

    def get_user_session(self, sid: UUID) -> UserSession:
        """
        Selects a user session by id
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(UserSession)) as cur:
                cur.execute(
                    SELECT_USER_SESSION,
                    (str(sid), )
                )

                user = cur.fetchone()

                if not user:
                    raise UserSessionNotFoundError(f"User session {str(sid)} not found")

                return user

    def get_latest_user_session(self, user_id: UUID) -> UserSession:
        """
        Selects a user session by id
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(UserSession)) as cur:
                cur.execute(
                    SELECT_LATEST_USER_SESSION,
                    (str(user_id), )
                )

                user = cur.fetchone()

                if not user:
                    raise UserSessionNotFoundError(f"User session {str(user_id)} not found")

                return user
