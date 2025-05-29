from src.repositories.users import UserNotFoundError, UserSessionNotFoundError, UsersRepository
from src.models import User, UserSession
from src.config.config import Config
from mong import get_random_name
from datetime import datetime
from uuid import UUID, uuid4
import logging

def generate_name():
    return get_random_name().replace('_', ' ').title()

class UsersService():
    config: Config
    users_repository: UsersRepository

    def __init__(
        self, *,
        config: Config,
        users_repository: UsersRepository
    ):
        self.config = config
        self.users_repository = users_repository

    def create_user(
        self, *,
        user_id: UUID,
        timestamp: datetime,
        name: str | None
    ) -> User:
        try:
            user = self.users_repository.get_user(user_id)
        except UserNotFoundError:
            name = name if name else generate_name()
            user = self.users_repository.create_user(User(
                id=user_id,
                name=name,
                timestamp=timestamp
            ))

        return user

    def register_user_connection(
        self, *,
        user_id: UUID,
        timestamp: datetime
    ) -> UserSession:
        sid = uuid4()

        try:
            session = self.users_repository.get_latest_user_session(user_id)
        except UserSessionNotFoundError:
            session = self.users_repository.create_user_session(UserSession(
                id=sid,
                user_id=user_id,
                timestamp=timestamp,
                event="connected"
            ))

        return session

    def register_user_disconnection(
        self,
        *,
        sid: UUID,
        timestamp: datetime
    ) -> UserSession | None:
        try:
            user_session = self.users_repository.get_user_session(sid)
        except UserSessionNotFoundError:
            logging.error("The user session could not be found")
            return

        self.users_repository.create_user_session(UserSession(
            id=user_session.id,
            user_id=user_session.user_id,
            timestamp=timestamp,
            event="disconnected"
        ))
