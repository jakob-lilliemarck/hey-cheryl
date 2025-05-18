from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit
from pydantic import BaseModel, ValidationError
from typing import Optional, List
from uuid import UUID, uuid4
import datetime
import psycopg
import os
from psycopg_pool import ConnectionPool
from flask_socketio import Namespace
from transformers.pipelines import pipeline

pipe = pipeline("text-generation", model="Qwen/Qwen3-0.6B")

# Load DATABASE_URL from environment variables
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable not set")

SESSION_TYPE = os.environ.get("SESSION_TYPE")
if not SESSION_TYPE:
    raise ValueError("SESSION_TYPE environment variable not set")

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SESSION_TYPE'] = SESSION_TYPE
socketio = SocketIO(app)

# Pydantic Models
class Message(BaseModel):
    message: str
    timestamp: datetime.datetime
    role: str
    conversation_id: UUID

class Concept(BaseModel):
    id: int
    concept: str
    meaning: str

class SidConversationID(BaseModel):
    sid: UUID
    conversation_id: UUID
    timestamp: datetime.datetime

# Create a connection pool (psycopg_pool)
pool = ConnectionPool(DATABASE_URL)

# Helper function to get a database connection from the pool
def get_db_connection():
    try:
        return pool.connection()
    except psycopg.Error as e:
        print(f"Database connection error: {e}")
        raise

# --- Load data at startup ---
# Use a list of Concepts, because that is what you want to load
all_concepts: List[Concept] = []  # Initialize as an empty list

def load_concepts_at_startup():
    """Loads concepts from the database at application startup."""
    global all_concepts
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, concept, meaning FROM concepts;")
                for row in cur.fetchall():
                    try:
                        concept = Concept(id=row[0], concept=row[1], meaning=row[2])
                        all_concepts.append(concept)
                    except ValidationError as e:
                        print(f"Validation error for concept: {row} - {e}")
    except psycopg.Error as e:
        print(f"Database error during startup: {e}")

# Call the loading function at startup
with app.app_context():  # Use app context to access app config
    load_concepts_at_startup()

# --- Use the cached data ---
def get_all_concepts() -> List[Concept]:
    """
    Returns all concepts from the in-memory cache.
    """
    return all_concepts

# Method to get messages of a conversation with an optional timestamp
def get_messages_of_conversation(conversation_id: UUID, timestamp: Optional[datetime.datetime] = None) -> list[Message]:
    """
    Retrieves messages for a given conversation ID, optionally filtering by timestamp.
    """
    messages: list[Message] = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT message, timestamp, role, conversation_id
                    FROM messages
                    WHERE conversation_id = %s AND (%s::timestamptz IS NULL OR timestamp >= %s::timestamptz)
                    ORDER BY timestamp
                    LIMIT 50;
                    """,
                    (str(conversation_id), timestamp, timestamp),  # Pass timestamp twice
                )
                for row in cur.fetchall():
                    try:
                        message = Message(
                            message=row[0],
                            timestamp=row[1],
                            role=row[2],
                            conversation_id=row[3]
                        )
                        messages.append(message)
                    except ValidationError as e:
                        print(f"Validation error for message: {row} - {e}")
    except psycopg.Error as e:
        print(f"Database error: {e}")
    return messages

def set_sid_conversation_id(sid_conversation_id: SidConversationID):
    """
    Inserts a sid_conversation_id record
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sid_conversation_ids (conversation_id, sid, "timestamp")
                    VALUES (%s, %s, %s)
                    ON CONFLICT (sid) DO UPDATE SET
                        conversation_id = EXCLUDED.conversation_id,
                        "timestamp" = EXCLUDED."timestamp";
                    """,
                    (
                        str(sid_conversation_id.conversation_id),
                        sid_conversation_id.sid,
                        sid_conversation_id.timestamp  # Use the timestamp from the model
                    )
                )
                conn.commit()
    except psycopg.Error as e:
        print(f"Database error: {e}")

def set_message(message: Message):
    """
    Inserts a message record.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO messages (conversation_id, timestamp, message, role) VALUES (%s, %s, %s, %s)",
                    (str(message.conversation_id), message.timestamp, message.message, message.role),
                )
                conn.commit()
    except psycopg.Error as e:
        print(f"Database error: {e}")

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@socketio.on('connect')
def test_connect():
    """Handles new WebSocket connections."""
    sid = uuid4()
    session['sid'] = str(sid)
    print(f"Client connected: {sid}")

    emit('cheryl_replies', {
        'role': 'cheryl',
        'message': 'Hi there 👋 I\'m Cheryl!'
    })

@socketio.on('disconnect')
def test_disconnect():
    """Handles WebSocket disconnections."""
    print(f"Client disconnected: {session['sid']}")

# hey-cheryl/app.py#L157-L180
@socketio.on('new_message')
def handle_message(json_data): # Renamed 'json' to 'json_data'
    """Handles incoming WebSocket messages and sends a response."""
    global pipe # Explicitly state we are using the global 'pipe'

    set_message(Message(
        role='user',
        conversation_id=UUID(session['conversation_id']), # Ensure conversation_id is UUID
        message=json_data['data'],
        timestamp=datetime.datetime.now()
    ))

    messages_from_db = get_messages_of_conversation(UUID(session['conversation_id']), None) # Ensure UUID
    chat_history_for_model = [{ 'role': m.role, 'content': m.message} for m in messages_from_db]
    print(f"pipeline input: {chat_history_for_model}")

    # Use the initialized 'pipe' object
    raw_model_response = pipe(
        chat_history_for_model,
        max_new_tokens=64,
        repetition_penalty=1.2,
        do_sample=True,
        temperature=1.5,
        top_k=50
    )
    print(f"Raw model response: {raw_model_response}")

    # It's highly recommended to print this during development to understand its structure:
    # print(f"Raw model response: {raw_model_response}")

    assistant_reply_content = ""
    if raw_model_response and isinstance(raw_model_response, list) and raw_model_response[0]:
        generated_output = raw_model_response[0].get("generated_text")

        if isinstance(generated_output, list) and generated_output:
            # Assumes the last message in the list is the assistant's new reply
            last_message_in_chat = generated_output[-1]
            if isinstance(last_message_in_chat, dict) and last_message_in_chat.get("role") == "assistant":
                assistant_reply_content = last_message_in_chat.get("content", "")
            elif isinstance(last_message_in_chat, dict) and "content" in last_message_in_chat :
                # If role is not 'assistant' or not present, but content is, maybe it's still the reply?
                # This part might need adjustment based on Qwen's specific output for your setup.
                # For now, we'll assume if it's the last dict with content, it's the reply.
                assistant_reply_content = last_message_in_chat.get("content", "")
                print(f"Warning: Last message in generated_text list did not have role 'assistant': {last_message_in_chat}")
            else:
                # If the last item is not a dict or doesn't have 'content',
                # this could happen if Qwen returns the entire chat including the user's message last.
                # You might need to iterate backwards to find the *actual* last assistant message.
                # For now, this is a simplified extraction.
                # A robust way: find the last message in generated_output that wasn't in chat_history_for_model
                assistant_reply_content = str(last_message_in_chat) # Fallback to string conversion
                print(f"Warning: Could not extract content cleanly from last message dict: {last_message_in_chat}")


        elif isinstance(generated_output, str): # If generated_text is just the new string
            assistant_reply_content = generated_output
        else:
            print(f"Unexpected structure or empty generated_text: {generated_output}")
            assistant_reply_content = "Error: Model generated an unexpected response format."
    else:
        print(f"Unexpected raw model response structure or empty response: {raw_model_response}")
        assistant_reply_content = "Error: Model did not return a valid response."

    reply = Message(
        role='cheryl', # This is your application-specific role for the AI
        conversation_id=UUID(session['conversation_id']), # Ensure UUID
        message=assistant_reply_content,
        timestamp=datetime.datetime.now()
    )

    set_message(reply)

    emit('cheryl_replies', reply.model_dump(mode='json'))


@socketio.on('authenticate')
def handle_authentication(json):
    """Emitted by the client at connection. Provides a conversation_id that can be associated with the sid"""
    try:
        # Ensure conversation_id is a UUID
        conversation_id_str = json.get('conversation_id')
        if not conversation_id_str:
            emit('authentication_failed', {'error': 'conversation_id missing'})
            return

        conversation_id_uuid = UUID(conversation_id_str)

        # Associate sid with conversation_id
        set_sid_conversation_id(SidConversationID(
            sid=session['sid'],
            conversation_id=conversation_id_uuid,
            timestamp=datetime.datetime.now()
        ))

        # Store conversation_id in session
        session['conversation_id'] = str(conversation_id_uuid)

        # Retrieve messages for this conversation
        messages_list = get_messages_of_conversation(conversation_id_uuid, None)

        # Serialize messages for sending, ensuring datetime objects are converted to strings
        serialized_messages = [msg.model_dump(mode='json') for msg in messages_list]

        # Emit the messages back to the client
        emit('authentication_successful', {'conversation_id': str(conversation_id_uuid), 'messages': serialized_messages})
        print(f"Authentication successful for conversation_id: {conversation_id_uuid}, sid: {session['sid']}. Sent {len(serialized_messages)} messages.")

    except ValueError:
        emit('authentication_failed', {'error': 'Invalid conversation_id format'})
        print(f"Authentication failed: Invalid conversation_id format - {json.get('conversation_id')}")
    except Exception as e:
        emit('authentication_failed', {'error': 'An internal error occurred'})
        # It's good to log the actual exception for debugging
        print(f"Error during authentication for sid {session['sid']}: {e}")
        import traceback
        traceback.print_exc() # This will print the full traceback


if __name__ == '__main__':
    socketio.run(app, debug=True) # Set debug=False for production
