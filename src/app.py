from src.repositories.messages import MessageInsertionError
from src.repositories.users import UserSessionInsertionError
from src.repositories.users import UserSessionNotFoundError
from flask import Flask, render_template, session, request, current_app
from flask_socketio import SocketIO, emit
from src.config.config import Config
import logging
from uuid import uuid4
from src.models import Message, UserSession
from src.models import User
from datetime import datetime, timezone
import mong
from psycopg_pool import ConnectionPool
from psycopg import Connection
from psycopg.rows import TupleRow
from src.repositories.concepts import ConceptsRepository
from src.repositories.messages import MessagesRepository
from src.repositories.users import UserNotFoundError, UsersRepository
import typing
from src.services.cheryl import Cheryl
from uuid import UUID

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MyApp(Flask):
    pool: ConnectionPool[Connection[TupleRow]]
    users_repository: UsersRepository
    messages_repository: MessagesRepository
    concepts_repository: ConceptsRepository
    assistant_service: Cheryl

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

config = Config.new_from_env()
app = MyApp(__name__, template_folder='../templates')
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['SESSION_TYPE'] = config.SESSION_TYPE

pool = ConnectionPool(
    config.DATABASE_URL,
    connection_class=Connection[TupleRow]
)

app.users_repository = UsersRepository(pool)
app.messages_repository = MessagesRepository(pool)
app.concepts_repository = ConceptsRepository(pool)
app.assistant_service = Cheryl(
    user_id=config.ASSISTANT_USER_ID,
    session_id=config.ASSISTANT_SESSION_ID,
    conversation_id=config.CONVERSATION_ID,
    messages_repository=app.messages_repository,
    concepts_repository=app.concepts_repository,
    users_repository=app.users_repository,
)
socketio = SocketIO(app)

USER = 'user'

@app.route('/')
def index():
    """Serves the main HTML page."""
    messages = app.messages_repository.get_messages(conversation_id=config.CONVERSATION_ID)
    user_ids_of_conversation = app.messages_repository.get_user_ids_of_conversation(conversation_id=config.CONVERSATION_ID)
    user_ids = app.users_repository.get_connected_user_ids()
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


@socketio.on('connect')
def on_connect():
    """Handles new WebSocket connections."""
    user_id = request.args.get('user_id')
    if not user_id:
        raise KeyError("Expected a user_id but none was found")
        return

    try:
        user_id = UUID(user_id)
    except:
        raise ValueError("the provided uuid is not valid")
        return

    sid = uuid4()
    session['sid'] = sid
    app = typing.cast(MyApp, current_app)
    timestamp = datetime.now(timezone.utc)

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
        app.users_repository.create_user_session(UserSession(
            id=sid,
            user_id=user.id,
            timestamp=timestamp,
            event="connected"
        ))
    except UserSessionInsertionError:
        logging.error("Could not create user session")
        return

    emit("user_connected", user.model_dump(mode='json'))

@socketio.on('user_authored_message')
def on_message(user_authored_message):
    """Handles incoming WebSocket messages and sends a response."""
    app = typing.cast(MyApp, current_app)

    try:
        message = app.messages_repository.create_message(Message(
            id=uuid4(),
            user_id=user_authored_message['user_id'],
            role=USER,
            conversation_id=config.CONVERSATION_ID,
            message=user_authored_message['body'],
            timestamp=datetime.now(timezone.utc)
        ))
    except MessageInsertionError:
        logging.error("The message could not be created")
        return


    emit('message_created', message.model_dump(mode='json'))

    # Start a background task to generate and emit the reply
    socketio.start_background_task(generate_and_emit_reply, message)

def generate_and_emit_reply(message):
    """Generates the assistant's reply and emits it back to the client."""
    # Establish the application context for this thread
    with app.app_context():
        reply = app.assistant_service.ask_to_reply(message)
        logging.info(f"reply: {reply}")
        # FIXME: DOES NOT WORK!!!
        # Emit the message specifically to the client using their SID
        # emit('message_created', reply.model_dump(mode='json'))



@socketio.on('disconnect')
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

if __name__ == '__main__':
    socketio.run(app, debug=True) # Set debug=False for production
