from flask import Flask, render_template, session, request, Response
from flask_socketio import SocketIO, join_room, leave_room
from src.config.config import Config
import logging
from src.models import ReplyingTo, SystemPromptKey
from datetime import datetime, timezone
from psycopg_pool import ConnectionPool
from psycopg import Connection
from psycopg.rows import TupleRow
from src.repositories.users import UsersRepository
from src.repositories.messages import MessagesRepository
from src.repositories.concepts import ConceptsRepository
from src.repositories.system_prompts import SystemPromptsRepository
from src.services.users import UsersService
from src.services.messages import MessagesService
from src.services.concepts import ConceptsService
from uuid import UUID
from functools import wraps
import re
from typing import List, Dict, Tuple, Optional, Iterable

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
system_prompts_repository = SystemPromptsRepository(pool)

# Services
users_service = UsersService(
    config=config,
    users_repository=users_repository
)
messages_service = MessagesService(
    config=config,
    messages_repository=messages_repository
)
concepts_service = ConceptsService(
    config=config,
    concepts_repository=concepts_repository,
    system_prompts_repository=system_prompts_repository
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

CONCEPT_KEY_PATTERN = re.compile(r"concept\(([\w-]+)\)-(\w+)")
PROMPT_KEYS = [spk.value for spk in SystemPromptKey]

def parse_concept_key(key: str) -> Optional[Tuple[UUID, str]]:
    m = CONCEPT_KEY_PATTERN.match(key)
    if not m:
        return None

    field = m.group(2)
    if field not in ["term", "meaning"]:
        raise ValueError(f"invalid concept field type '{field}' in key '{key}'. Expected 'term' or 'meaning'")

    id = UUID(m.group(1))

    return id, field

def parse_prompt_key(key: str) -> Optional[str]:
    if key in PROMPT_KEYS:
        return key

    return None

def parse_form(
    data: Iterable[Tuple[str, str]]
) -> Tuple[List[Tuple[str, str]], List[Tuple[UUID, str, str]]]:
    prompts: List[Tuple[str, str]] = []
    concepts_data: Dict[UUID, Dict[str, str]] = {}

    for key, value in data:
        value = value.strip()

        concept = parse_concept_key(key)
        if concept:
            id, field = concept
            if id not in concepts_data:
                concepts_data[id] = {}

            concepts_data[id][field] = value
            continue

        prompt_key = parse_prompt_key(key)
        if prompt_key:
            prompts.append((key, value))

    concepts: List[Tuple[UUID, str, str]] = []
    for id, fields in concepts_data.items():
        term = fields.get('term')
        if term is None:
            raise ValueError("term may not be None")

        meaning = fields.get('meaning')
        if meaning is None:
            raise ValueError("meaning may not be None")

        concepts.append((id, term, meaning))

    return prompts, concepts


@app.route('/manage', methods=['GET', 'POST'])
@requires_auth
def manage():
    if request.method == 'POST':
        now = datetime.now(timezone.utc)
        prompt_args, concept_args = parse_form(request.form.items())

        system_prompts = concepts_service.update_system_prompts(
            timestamp=now,
            prompts=prompt_args,
        )
        concepts = concepts_service.sync_concepts(
            timestamp=now,
            concepts=concept_args,
        )
    else:
        system_prompts = system_prompts_repository.get_system_prompts()
        concepts = concepts_repository.get_concepts()

    return render_template(
        'manage.html',
        system_prompts=[sp.model_dump(mode='json') for sp in system_prompts],
        concepts=[c.model_dump(mode='json') for c in concepts]
    )


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
        initial_users_of_conversation=initial_users_of_conversation,
        assistant_user_id=config.ASSISTANT_USER_ID
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
