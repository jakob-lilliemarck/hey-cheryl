from src.repositories.messages import MessagesRepository
from src.config.config import Config
from src.models import Message, Reply, ReplyStatus
from uuid import UUID, uuid4
from datetime import datetime
import logging

class ReplyWithoutBodyError(Exception):
    pass

class MessagesService():
    config: Config
    messages_repository: MessagesRepository

    def __init__(
        self, *,
        config: Config,
        messages_repository: MessagesRepository
    ):
        self.config = config
        self.messages_repository = messages_repository

    def create_user_message(
        self, *,
        user_id: UUID,
        content: str,
        timestamp: datetime
    ) -> Message:
        logging.info("MessagesService::create_user_message")

        message = self.messages_repository.create_message(Message(
            id=uuid4(),
            user_id=user_id,
            role='user',
            conversation_id=self.config.CONVERSATION_ID,
            message=content,
            timestamp=timestamp
        ))

        return message

    def create_assistant_message(
        self, *,
        content: str,
        timestamp: datetime
    ) -> Message:
        logging.info("MessagesService::create_assistant_message")

        message = self.messages_repository.create_message(Message(
            id=uuid4(),
            user_id=self.config.ASSISTANT_USER_ID,
            role='assistant',
            conversation_id=self.config.CONVERSATION_ID,
            message=content,
            timestamp=timestamp
        ))

        return message

    def enqueue_if_available(
        self, *,
        message_id: UUID,
        timestamp: datetime
    ) -> Reply | None:
        logging.info("MessagesService.enqueue_if_available: checking availability")
        replies_in_progress = self.messages_repository.get_replies(
            status=[ReplyStatus.PENDING, ReplyStatus.READY], # TODO - or just PENDING maybe?
            message_id=None,
            limit=1
        );

        # if there are work in progress we just return
        if replies_in_progress:
            logging.info("MessagesService.enqueue_if_available: no availability")
            return

        # If not we request a reply
        logging.info(f"MessagesService.enqueue_if_available: enqueued reply for {message_id}")
        reply = self.messages_repository.create_reply(Reply(
            id=uuid4(),
            timestamp=timestamp,
            message_id=message_id,
            status=ReplyStatus.PENDING,
            message=None,
        ));

        return reply

    def get_next_enqueued_reply(
        self, *,
        timestamp: datetime
    ) -> Reply | None:
        replies = self.messages_repository.get_replies(
            status=[ReplyStatus.PENDING],
            message_id=None,
            limit=1
        );

        if not replies:
            return

        return replies[0]

    def get_next_reply_to_publish(self) -> Reply | None:
        replies = self.messages_repository.get_replies(
            status=[ReplyStatus.READY],
            message_id=None,
            limit=1
        );

        if not replies:
            return

        reply = replies[0]
        if not reply.message:
            raise ReplyWithoutBodyError(f"reply with id {reply.id} is missing a message body")

        return reply

    def append_reply_content(
        self, *,
        reply: Reply,
        timestamp: datetime,
        content: str
    ) -> Reply:
        logging.info(f"MessagesService.append_reply_content: Appending content for reply {reply.id}")
        reply = self.messages_repository.create_reply(Reply(
             id=reply.id,
             timestamp=timestamp,
             message_id=reply.message_id,
             status=ReplyStatus.READY,
             message=content,
        ));
        return reply

    def mark_reply_as_published(
        self, *,
        reply: Reply,
        timestamp: datetime
    ) -> Reply:
        reply = self.messages_repository.create_reply(Reply(
             id=reply.id,
             timestamp=timestamp,
             message_id=reply.message_id,
             status=ReplyStatus.PUBLISHED,
             message=reply.message,
        ));
        return reply
