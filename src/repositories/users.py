from psycopg_pool import ConnectionPool
import psycopg
from psycopg.rows import TupleRow
from src.models import User, UserSession
from uuid import UUID
from psycopg.rows import class_row

INSERT_USER = """
    INSERT INTO users (id, name, timestamp)
    VALUES (%s, %s, %s) RETURNING *;
"""

INSERT_USER_SESSION = """
    INSERT INTO user_sessions (id, user_id, timestamp)
    VALUES (%s, %s, %s);
"""

SELECT_USER = """
    SELECT id, name, timestamp
    FROM users
    WHERE id = %s;
"""

class UserNotFoundError(Exception):
    pass

class DatabaseError(Exception):
    pass


class UsersRepository:
    pool: ConnectionPool[psycopg.Connection[TupleRow]]

    def __init__(self, pool: ConnectionPool[psycopg.Connection[TupleRow]]):
        self.pool = pool

    def create_user(self, user: User) -> User:
        """
        Inserts a user record
        """
        try:
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
                    created_user = cur.fetchone()
                    conn.commit()
                    if not created_user:
                        raise DatabaseError(f"Failed to create a new user")

                    return created_user
        except psycopg.Error as e:
            print(f"Database error: {e}")

    def create_user_session(self, user_session: UserSession):
        """
        Inserts a user record
        """
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        INSERT_USER_SESSION,
                        (
                            user_session.id,
                            user_session.user_id,
                            user_session.timestamp
                        )
                    )
                    conn.commit()
        except psycopg.Error as e:
            print(f"Database error: {e}")

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
                    raise UserNotFoundError(f"user {str(user_id)} not found")

                return user
