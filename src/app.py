from flask import Flask, render_template, session, request, Response
from flask_socketio import SocketIO, join_room, leave_room
from src.config.config import Config
import logging
from src.models import ReplyingTo, Concept, SystemPrompt, SystemPromptKey
from datetime import datetime, timezone
from psycopg_pool import ConnectionPool
from psycopg import Connection
from psycopg.rows import TupleRow
from src.repositories.messages import MessagesRepository
from src.repositories.concepts import ConceptsRepository
from src.services.users import UsersService
from src.services.messages import MessagesService
from src.repositories.users import UsersRepository
from uuid import UUID
from functools import wraps
import re
from typing import List, Dict

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

app = Flask(
    __name__,
    template_folder='../templates',
    static_folder='../static'
)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['SESSION_TYPE'] = config.SESSION_TYPE

io = SocketIO(app)

class ReplyWithoutBodyError(Exception):
    pass

# A lightweight polling loop to check on Cheryl
def poll_for_replies():
    while True:
        logging.info("Background: polling for messages to publish")
        timestamp = datetime.now(timezone.utc)
        reply = messages_service.get_next_reply_to_publish()

        # If there are replies waiting to publish
        if reply and reply.message:
            # Create a new message
            message = messages_service.create_assistant_message(
                content=reply.message,
                timestamp=timestamp,
            );

            # Emit the message
            io.emit(
                'message_created',
                message.model_dump(mode='json'),
                to=str(config.CONVERSATION_ID)
            )

            # Mark the reply as published
            messages_service.mark_reply_as_published(
                reply=reply,
                timestamp=timestamp
            )

            # Then tell the user we're ready for new requests
            io.emit(
                'replying_to',
                ReplyingTo(user_id=None).model_dump(mode='json'),
                to=str(config.CONVERSATION_ID)
            )

        io.sleep(2)

# Start the loop
io.start_background_task(target=poll_for_replies)

@app.route('/')
def about():
    return render_template('about.html')

def check_auth(username, password):
    return username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD

def authenticate():
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


@app.route('/manage', methods=['GET', 'POST'])
@requires_auth
def manage():
    if request.method == 'POST':
        logging.info(f"POST request received: {request.form}")

        now = datetime.now(timezone.utc)

        concept_key_pattern = re.compile(r"concept\(([\w-]+)\)-(\w+)")

        # A list of all system prompts
        prompt_ids = [SystemPromptKey.BASE.value]

        # A hash to collect system prompts
        system_prompts: List[SystemPrompt] = []

        # A hash to concepts
        concepts_data: Dict[UUID, Dict[str, str]] = {}

        for key, value in request.form.items():
            value = value.strip()
            match = concept_key_pattern.match(key)
            if match:
                concept_id = UUID(match.group(1))
                field_type = match.group(2)

                if concept_id not in concepts_data:
                    concepts_data[concept_id] = {}

                if field_type == 'key':
                    concepts_data[concept_id]['term'] = value
                elif field_type == 'value':
                    concepts_data[concept_id]['meaning'] = value
                else:
                    logging.warning(f"Unknown field_type '{field_type}' for concept key '{key}'")

            # System prompts are part of the code.
            # We only accept known prompt ids defined by the host
            if key in prompt_ids:
                system_prompts.append(SystemPrompt(
                    key=SystemPromptKey(key),
                    prompt=value
                ))

        concepts: List[Concept] = []
        for id in concepts_data:
            concepts.append(Concept(
                id=id,
                concept=concepts_data[id]['term'],
                meaning=concepts_data[id]['meaning'],
                timestamp=now
            ))

        logging.info(f"prompts: {system_prompts}")
        logging.info(f"concepts: {concepts}")

    return render_template('manage.html')

@app.route('/chat-with-cheryl')
def chat():
    """Serves the main HTML page."""
    messages = messages_repository.get_messages(conversation_id=config.CONVERSATION_ID)
    user_ids_of_conversation = messages_repository.get_user_ids_of_conversation(conversation_id=config.CONVERSATION_ID)
    user_ids = users_repository.get_connected_user_ids()
    user_ids_of_conversation.append(config.ASSISTANT_USER_ID)
    users = users_repository.get_users_by_id(user_ids_of_conversation)

    initial_messages = [msg.model_dump(mode='json') for msg in messages]
    initial_connected_user_ids = [str(id) for id in user_ids]
    initial_users_of_conversation = [u.model_dump(mode='json') for u in users]

    return render_template(
        'chat.html',
        initial_messages=initial_messages,
        initial_connected_user_ids=initial_connected_user_ids,
        initial_users_of_conversation=initial_users_of_conversation
    )


@io.on('connect')
def on_connect():
    """
    Handles new WebSocket connections
    """
    timestamp = datetime.now(timezone.utc)
    user_id = request.args.get('user_id')
    if not user_id:
        raise KeyError("Expected a user_id but none was found")
        return
    user_id = UUID(user_id)

    user = users_service.create_user(
        user_id=user_id,
        timestamp=timestamp,
        name=None
    )

    sess = users_service.register_user_connection(
        user_id=user_id,
        timestamp=timestamp
    )

    session['sid'] = sess.id

    join_room(str(config.CONVERSATION_ID))

    io.emit(
        "user_connected",
        user.model_dump(mode='json'),
        to=str(config.CONVERSATION_ID)
    )


@io.on('user_authored_message')
def on_message(user_authored_message):
    """Handles incoming WebSocket messages and sends a response."""
    timestamp = datetime.now(timezone.utc)

    message = messages_service.create_user_message(
        user_id=user_authored_message['user_id'],
        content=user_authored_message['body'],
        timestamp=timestamp
    )

    # Emit it to the room
    logging.info(f"on_message({message.id}): Emitting message to room")
    io.emit(
        'message_created',
        message.model_dump(mode='json'),
        to=str(config.CONVERSATION_ID)
    )

    # Check if there are any replies in progress
    reply = messages_service.enqueue_if_available(
        message_id=message.id,
        timestamp=timestamp
    )
    if not reply:
        logging.info(f"on_message({message.id}): Busy")
        return

    logging.info(f"on_message({message.id}): Emitting replying to user")
    io.emit(
        'replying_to',
        ReplyingTo(user_id=message.user_id).model_dump(mode='json'),
        to=str(config.CONVERSATION_ID)
    )

@io.on('disconnect')
def on_disconnect():
    """Handles WebSocket disconnections."""
    timestamp = datetime.now(timezone.utc)

    users_service.register_user_disconnection(
        sid=session['sid'],
        timestamp=timestamp
    )

    leave_room(str(config.CONVERSATION_ID))


if __name__ == '__main__':
    # Debug = True makes the background task loop very flaky
    io.run(app, debug=config.DEBUG)
