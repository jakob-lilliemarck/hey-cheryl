from uuid import uuid4
from src.repositories.messages import MessagesRepository
from src.repositories.concepts import ConceptsRepository
from src.repositories.users import UsersRepository, UserNotFoundError
from src.models import Message, Concept, User, UserSession
from uuid import UUID
from datetime import datetime, timezone
from src.repositories.users import UserSessionNotFoundError
import logging

NAME = 'Cheryl'
ROLE = 'assistant'

class Cheryl:
    user: User
    user_session: UserSession
    conversation_id: UUID
    messages_repository: MessagesRepository
    concepts_repository: ConceptsRepository
    users_repository: UsersRepository
    concepts = list[Concept]

    def __init__(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        conversation_id: UUID,
        messages_repository: MessagesRepository,
        concepts_repository: ConceptsRepository,
        users_repository: UsersRepository,
    ):
        self.concepts = concepts_repository.get_concepts()

        # Create or select the Cheryls user record
        try:
            cheryl = users_repository.get_user(user_id)
        except UserNotFoundError:
            cheryl = users_repository.create_user(User(
                id=user_id,
                name=NAME,
                timestamp=datetime.now(timezone.utc)
            ))

        # Create or select the Cheryls user record
        try:
            user_session = users_repository.get_latest_user_session(cheryl.id)
        except UserSessionNotFoundError:
            # And a session
            user_session = users_repository.create_user_session(UserSession(
                id=session_id,
                user_id=cheryl.id,
                timestamp=datetime.now(timezone.utc),
                event='connected'
            ))

        self.user = cheryl
        self.user_session = user_session
        self.conversation_id = conversation_id
        self.concepts_repository = concepts_repository
        self.messages_repository = messages_repository
        self.users_repository = users_repository

    def ask_to_reply(self, message: Message) -> Message:
        logging.info(f"ask_to_reply called for message ID: {message.id}")
        replies_in_progress = self.messages_repository.get_replies(
            acknowledged=True,
            completed=False,
            message_id=None,
            limit=1
        );

        if replies_in_progress:
            logging.info("Replies in progress found, returning 'busy' message.")
            return Message(
                id=uuid4(),
                conversation_id=self.conversation_id,
                user_id=self.user.id,
                role=ROLE,
                timestamp=datetime.now(timezone.utc),
                message="I am busy"
            )

        logging.info("No replies in progress, generating new response.")
        return Message(
            id=uuid4(),
            conversation_id=self.conversation_id,
            user_id=self.user.id,
            role=ROLE,
            timestamp=datetime.now(timezone.utc),
            message="Generate shiiet"
        )
