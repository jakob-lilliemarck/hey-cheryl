from src.repositories.users import UserSessionInsertionError
from src.repositories.users import UserSessionNotFoundError
from flask import Flask, render_template, session, request, current_app
from flask_socketio import SocketIO, join_room, leave_room
from src.config.config import Config
import logging
from uuid import uuid4
from src.models import Message, UserSession, ReplyingTo, Reply, User
from datetime import datetime, timezone
import mong
from psycopg_pool import ConnectionPool
from psycopg import Connection
from psycopg.rows import TupleRow
from src.repositories.messages import MessagesRepository
from src.repositories.users import UserNotFoundError, UsersRepository
import typing
from uuid import UUID
from threading import Thread
from time import sleep


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class MyApp(Flask):
    pool: ConnectionPool[Connection[TupleRow]]
    users_repository: UsersRepository
    messages_repository: MessagesRepository

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


config = Config.new_from_env()


pool = ConnectionPool(
    config.DATABASE_URL,
    connection_class=Connection[TupleRow]
)


app = MyApp(__name__, template_folder='../templates')
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['SESSION_TYPE'] = config.SESSION_TYPE
app.users_repository = UsersRepository(pool)
app.messages_repository = MessagesRepository(pool)


io = SocketIO(app)


class ReplyWithoutBodyError(Exception):
    pass


# A lightweight polling loop to check on Cheryl
def poll_for_replies():
    while True:
        replies_to_publish = app.messages_repository.get_replies(
            acknowledged=True,
            completed=True,
            published=False,
            message_id=None, # None omits this filter
            limit=1
        );

        # If there are replies waiting to publish
        if replies_to_publish:
            # Pick out the first (and only) reply.
            reply = replies_to_publish[0]

            if not reply.message:
                raise ReplyWithoutBodyError(f"reply with id {reply.id} is missing a message body")

            # Persist the message to the database
            message = app.messages_repository.create_message(Message(
                 id=uuid4(),
                 conversation_id=config.CONVERSATION_ID,
                 user_id=config.ASSISTANT_USER_ID,
                 role='assistant',
                 timestamp=datetime.now(timezone.utc),
                 message=reply.message,
            ));

            # Emit it to the room
            io.emit(
                'message_created',
                message.model_dump(mode='json'),
                to=str(config.CONVERSATION_ID)
            )

            # And mark the reply as published
            app.messages_repository.create_reply(Reply(
                 id=reply.id,
                 timestamp=datetime.now(timezone.utc),
                 message_id=reply.message_id,
                 acknowledged=reply.acknowledged,
                 published=True,
                 message=reply.message,
            ));

            # Then tell the user we're ready for new requests
            io.emit(
                'replying_to',
                ReplyingTo(user_id=None).model_dump(mode='json'),
                to=str(config.CONVERSATION_ID)
            )

        sleep(2)


# Start the loop
Thread(target=poll_for_replies, daemon=True).start()


@app.route('/')
def index():
    """Serves the main HTML page."""
    messages = app.messages_repository.get_messages(conversation_id=config.CONVERSATION_ID)
    user_ids_of_conversation = app.messages_repository.get_user_ids_of_conversation(conversation_id=config.CONVERSATION_ID)
    user_ids = app.users_repository.get_connected_user_ids()
    user_ids_of_conversation.append(config.ASSISTANT_USER_ID)
    users = app.users_repository.get_users_by_id(user_ids_of_conversation)

    initial_messages = [msg.model_dump(mode='json') for msg in messages]
    initial_connected_user_ids = [str(id) for id in user_ids]
    initial_users_of_conversation = [u.model_dump(mode='json') for u in users]

    return render_template(
        'index.html',
        initial_messages=initial_messages,
        initial_connected_user_ids=initial_connected_user_ids,
        initial_users_of_conversation=initial_users_of_conversation
    )


@io.on('connect')
def on_connect():
    """Handles new WebSocket connections."""
    user_id = request.args.get('user_id')
    if not user_id:
        raise KeyError("Expected a user_id but none was found")
        return

    sid = uuid4()
    session['sid'] = sid
    user_id = UUID(user_id)
    timestamp = datetime.now(timezone.utc)
    app = typing.cast(MyApp, current_app)

    try:
        user = app.users_repository.get_user(user_id)
    except UserNotFoundError:
        user = app.users_repository.create_user(User(
            id=user_id,
            name=mong.get_random_name(),
            timestamp=timestamp
        ))
        if not user:
            logging.error("Could not create user")
            return

    try:
        app.users_repository.get_latest_user_session(user_id)
    except UserSessionNotFoundError:
        app.users_repository.create_user_session(UserSession(
            id=sid,
            user_id=user.id,
            timestamp=timestamp,
            event="connected"
        ))

    join_room(str(config.CONVERSATION_ID))

    io.emit(
        "user_connected",
        user.model_dump(mode='json'),
        to=str(config.CONVERSATION_ID)
    )


@io.on('user_authored_message')
def on_message(user_authored_message):
    """Handles incoming WebSocket messages and sends a response."""
    app = typing.cast(MyApp, current_app)
    message_id = uuid4()

    # Insert the message in the database
    logging.info(f"on_message({message_id}): Storing message")
    message = app.messages_repository.create_message(Message(
        id=uuid4(),
        user_id=user_authored_message['user_id'],
        role='user',
        conversation_id=config.CONVERSATION_ID,
        message=user_authored_message['body'],
        timestamp=datetime.now(timezone.utc)
    ))

    # Emit it to the room
    logging.info(f"on_message({message_id}): Emitting message to room")
    io.emit(
        'message_created',
        message.model_dump(mode='json'),
        to=str(config.CONVERSATION_ID)
    )

    # Check if there are any replies in progress
    logging.info(f"on_message({message_id}): Checking Cheryls availability")
    replies_in_progress = app.messages_repository.get_replies(
        acknowledged=True,
        completed=False,
        published=False,
        message_id=None,
        limit=1
    );

    # if there are work in progress we just return
    if replies_in_progress:
        logging.info(f"on_message({message_id}): Cheryl is busy, skipping request for reply")
        return

    # If not we request a reply
    logging.info(f"on_message({message_id}): Cheryl is available, requesting a reply")
    app.messages_repository.create_reply(Reply(
        id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        message_id=message.id,
        acknowledged=False,
        published=False,
        message=None,
    ));

    # and then inform the user we're working on it
    logging.info(f"on_message({message_id}): Emitting replying to user")
    io.emit(
        'replying_to',
        ReplyingTo(user_id=message.user_id).model_dump(mode='json'),
        to=str(config.CONVERSATION_ID)
    )


@io.on('disconnect')
def on_disconnect():
    """Handles WebSocket disconnections."""
    try:
        user_session = app.users_repository.get_user_session(session['sid'])
    except UserSessionNotFoundError:
        logging.error("The user session could not be found")
        return

    try:
        app.users_repository.create_user_session(UserSession(
            id=user_session.id,
            user_id=user_session.user_id,
            timestamp=datetime.now(timezone.utc),
            event="disconnected"
        ))
    except UserSessionInsertionError:
        logging.error("Could not create a user session event with the database")
        return

    leave_room(str(config.CONVERSATION_ID))


if __name__ == '__main__':
    io.run(app, debug=False) # Set debug=False for production
