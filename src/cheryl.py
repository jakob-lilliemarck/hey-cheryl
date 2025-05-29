from time import sleep
import logging
from src.repositories.concepts import ConceptsRepository
from src.repositories.messages import MessagesRepository
from src.repositories.users import UsersRepository
from src.config.config import Config
from psycopg_pool import ConnectionPool
from psycopg.rows import TupleRow
from psycopg import Connection
from datetime import datetime, timezone
from src.services.messages import MessagesService
from src.services.users import UsersService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

config = Config.new_from_env()

pool = ConnectionPool(
    config.DATABASE_URL,
    connection_class=Connection[TupleRow]
)

# Repositories
users_repository = UsersRepository(pool)
messages_repository = MessagesRepository(pool)
concepts_repository = ConceptsRepository(pool)

# Services
users_service = UsersService(
    config=config,
    users_repository=users_repository
)
messages_service = MessagesService(
    config=config,
    messages_repository=messages_repository
)


def main():
    while True:
        logging.info("polling for messages to reply to")
        reply = messages_service.get_next_enqueued_reply(
            timestamp=datetime.now(timezone.utc)
        )

        if reply:
            # --- --- --- --- --- --- --- --- --- --- --- ---
            # TODO - run some long running text generation here!!
            # --- --- --- --- --- --- --- --- --- --- --- ---
            messages_service.append_reply_content(
                reply=reply,
                timestamp=datetime.now(timezone.utc),
                content="testing testing"
            )

        sleep(2)

if __name__ == '__main__':
    timestamp = datetime.now(timezone.utc)

    users_service.create_user(
        user_id=config.ASSISTANT_USER_ID,
        timestamp=timestamp,
        name="Cheryl"
    )

    users_service.register_user_connection(
        user_id=config.ASSISTANT_USER_ID,
        timestamp=timestamp
    )

    main()
