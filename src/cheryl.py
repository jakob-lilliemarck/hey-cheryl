from time import sleep
import logging
from src.repositories.concepts import ConceptsRepository
from src.repositories.messages import MessagesRepository
from src.repositories.users import UserNotFoundError, UsersRepository
from src.config.config import Config
from src.models import Reply, User
from psycopg_pool import ConnectionPool
from psycopg.rows import TupleRow
from psycopg import Connection
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

config = Config.new_from_env()

pool = ConnectionPool(
    config.DATABASE_URL,
    connection_class=Connection[TupleRow]
)

users_repository = UsersRepository(pool)
messages_repository = MessagesRepository(pool)
concepts_repository = ConceptsRepository(pool)

def register_cheryl():
    try:
        logging.info("Checking if Cheryl is a registered user")
        users_repository.get_user(config.ASSISTANT_USER_ID)
    except UserNotFoundError:
        logging.info("Registering Cheryl")
        users_repository.create_user(User(
            id=config.ASSISTANT_USER_ID,
            name='Cheryl',
            timestamp=datetime.now(timezone.utc)
        ))

if __name__ == '__main__':
    logging.info("Waking up Cheryl")

    while True:
        register_cheryl()
        logging.info("polling for messages to reply to")
        replies_to_publish = messages_repository.get_replies(
            acknowledged=False,
            completed=False,
            published=False,
            message_id=None, # None omits this filter
            limit=1
        );

        for reply in replies_to_publish:
            logging.info(f"replying to message with id {reply.id}")
            messages_repository.create_reply(Reply(
                 id=reply.id,
                 timestamp=datetime.now(timezone.utc),
                 message_id=reply.message_id,
                 acknowledged=True,
                 published=reply.published,
                 message="Testing testing",
            ));

        sleep(2)
