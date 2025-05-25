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
from uuid import UUID

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MyApp(Flask):
    pool: ConnectionPool[Connection[TupleRow]]
    users_repository: UsersRepository
    messages_repository: MessagesRepository
    concepts_repository: ConceptsRepository

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

socketio = SocketIO(app)


USER = 'user'

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

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
            id=uuid4(),
            name=mong.get_random_name(),
            timestamp=timestamp
        ))
        if not user:
            logging.error("Could not create user")
            emit("user_creation_error", user_id)
            return

    try:
        app.users_repository.create_user_session(UserSession(
            id=sid,
            user_id=user.id,
            timestamp=timestamp
        ))
    except:
        logging.error("Could not create user session")
        emit("user_creation_error", user_id)
        return

    emit("user_connected", user.model_dump(mode='json'))


@socketio.on('disconnect')
def on_disconnect():
    """Handles WebSocket disconnections."""
    sid = request.args.get('user_id')
    print(f"Client disconnected: {sid}")


@socketio.on('new_message')
def on_message(json_data):
    """Handles incoming WebSocket messages and sends a response."""

    message = Message(
        id=uuid4(),
        user_id=uuid4(), # FIXME
        role=USER,
        conversation_id=config.CONVERSATION_ID,
        message="Mocked message",
        timestamp=datetime.now(timezone.utc)
    )

    emit('message', message.model_dump(mode='json'))


if __name__ == '__main__':
    socketio.run(app, debug=True) # Set debug=False for production
