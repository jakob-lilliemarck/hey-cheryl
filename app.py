from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from pydantic import BaseModel, ValidationError
from typing import Optional, List
from uuid import UUID
import datetime
import psycopg
import os
from psycopg_pool import ConnectionPool

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app)

# Pydantic Models
class Message(BaseModel):
    message: str
    timestamp: datetime.datetime
    is_cheryl: bool

class Concept(BaseModel):
    id: int
    concept: str
    meaning: str

# Load DATABASE_URL from environment variables
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

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
                    SELECT message, timestamp, is_cheryl
                    FROM messages
                    WHERE conversation_id = %s AND (%s IS NULL OR timestamp >= %s)
                    ORDER BY timestamp;
                    """,
                    (str(conversation_id), timestamp, timestamp),  # Pass timestamp twice
                )
                for row in cur.fetchall():
                    try:
                        message = Message(
                            message=row[0],
                            timestamp=row[1],
                            is_cheryl=row[2]
                        )
                        messages.append(message)
                    except ValidationError as e:
                        print(f"Validation error for message: {row} - {e}")
    except psycopg.Error as e:
        print(f"Database error: {e}")
    return messages

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@socketio.on('connect')
def test_connect():
    """Handles new WebSocket connections."""
    print('Client connected')
    emit('my response', {'data': 'Hi there 👋 I\'m Cheryl!'})

@socketio.on('disconnect')
def test_disconnect():
    """Handles WebSocket disconnections."""
    print('Client disconnected')

@socketio.on('my event')
def handle_my_custom_event(json):
    """Handles incoming WebSocket messages and sends a response."""
    shiet = get_all_concepts()
    print('received json: ' + str(json))
    emit('my response', {'data': 'Server received: ' + json['data']})  # Echo the received data

if __name__ == '__main__':
    socketio.run(app, debug=True) # Set debug=False for production
