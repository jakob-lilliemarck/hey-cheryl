from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit
from pydantic import ValidationError
from typing import List
from uuid import UUID, uuid4
import datetime
import psycopg
from psycopg_pool import ConnectionPool
from src.models.message import Message
from src.models.concept import Concept
from src.models.conversation import Conversation
from src.repositories.messages import MessagesRepository
from src.repositories.conversations import ConversationsRepository
from src.repositories.concepts import ConceptsRepository
from src.config.config import config
from psycopg import Connection
# --- BEGIN: Import Hugging Face AutoClasses and torch ---
from transformers.models.auto.tokenization_auto import AutoTokenizer
from transformers.models.auto.modeling_auto import AutoModelForCausalLM
import torch
from psycopg.rows import TupleRow
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

ASSISTANT = 'assistant'
SYSTEM = 'system'
USER = 'user'

logging.info(f"Starting to load Hugging Face tokenizer: {config.MODEL_NAME}")
tokenizer = AutoTokenizer.from_pretrained(config.MODEL_NAME)
logging.info(f"Hugging Face tokenizer '{config.MODEL_NAME}' loaded successfully.")

logging.info(f"Starting to load Hugging Face model: {config.MODEL_NAME}. This may take a while...")
model = AutoModelForCausalLM.from_pretrained(config.MODEL_NAME)
logging.info(f"Hugging Face model '{config.MODEL_NAME}' loaded successfully and is available.")

app = Flask(__name__, template_folder='../templates')
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['SESSION_TYPE'] = config.SESSION_TYPE
socketio = SocketIO(app)


# Create a connection pool (psycopg_pool)
pool = ConnectionPool(
    config.DATABASE_URL,
    connection_class=Connection[TupleRow]
)


# --- Load data at startup ---
all_concepts: List[Concept] = []
def load_concepts_at_startup():
    """Loads concepts from the database at application startup."""
    global all_concepts
    concepts_repository = ConceptsRepository(pool)
    all_concepts = concepts_repository.get_concepts()


# Call the loading function at startup
with app.app_context():
    load_concepts_at_startup()


# --- Use the cached data ---
def get_all_concepts() -> List[Concept]:
    """
    Returns all concepts from the in-memory cache.
    """
    return all_concepts


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


@socketio.on('disconnect')
def test_disconnect():
    """Handles WebSocket disconnections."""
    print(f"Client disconnected: {session['sid']}")


def say_something(conversation_id: UUID, max_new_tokens: int = 128) -> Message:
    messages_repository = MessagesRepository(pool)
    messages_from_db = messages_repository.get_messages_of_conversation(conversation_id, False, None)

    # Prepare chat history for the model
    # Map your application-specific roles to what the model/template expects (e.g., 'user', 'assistant')
    chat_history_for_model = [{
        'role': SYSTEM,
        'content': "Your name is Cheryl. You are not an AI assistant but a passionate human professor of aesthics and form at an arts university. You teach sculptural principles, how to model three dimensional form and how to give shape to physical products. You love working with clay. You are smart, quirky and a little bit insensitive altough you always have good intentions. Keep responses brief and fun."
    }]
    for m in messages_from_db:
        role_for_model = 'assistant' if m.role == ASSISTANT else m.role
        chat_history_for_model.append({'role': role_for_model, 'content': m.message})

    for m in chat_history_for_model:
        print(m)

    try:
        # 1. Apply chat template to format the history string.
        #    add_generation_prompt=True is crucial for chat models.
        prompt_text = tokenizer.apply_chat_template(
            chat_history_for_model,
            tokenize=False, # We get the string representation first
            add_generation_prompt=True # Important: Signals the model to generate assistant's reply
        )
        # print(f"Formatted prompt text for model: {prompt_text}")

        # 2. Tokenize the prompt string to get input_ids.
        #    Ensure tensors are moved to the same device as the model.
        input_ids_tensor = tokenizer.encode(
            prompt_text,
            return_tensors="pt",
            truncation=True,        # Add truncation
            max_length=tokenizer.model_max_length if hasattr(tokenizer, 'model_max_length') and tokenizer.model_max_length else 1024 # Or a sensible default
        ).to(config.DEVICE)

        # Store the length of the input prompt tokens
        input_token_length = input_ids_tensor.shape[1]
        # print(f"Input token length: {input_token_length}")

        # 3. Generate response from the model
        #    Make sure pad_token_id is set if your model needs it for generation.
        #    Often, tokenizer.eos_token_id can be used if tokenizer.pad_token_id is None.
        pad_token_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id

        with torch.no_grad(): # Important for inference
            outputs = model.generate(
                input_ids_tensor,
                max_new_tokens=max_new_tokens,
                temperature=0.7,
                top_p=0.95,
                top_k=50,
                do_sample=True,
                repetition_penalty=1.2,
                pad_token_id=pad_token_id
            )

        # 4. Isolate and decode only the newly generated tokens
        #    outputs[0] contains the full sequence (prompt + new tokens).
        #    Slice it to get only the new tokens.
        newly_generated_token_ids = outputs[0][input_token_length:]

        # Decode these new tokens, skipping special formatting tokens
        reply = tokenizer.decode(
            newly_generated_token_ids,
            skip_special_tokens=True
        ).strip()

        return Message(
            role=ASSISTANT,
            conversation_id=conversation_id,
            message=reply,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

    except Exception as e:
        print(f"Error during model inference or decoding: {e}")
        import traceback
        traceback.print_exc()
        return Message(
            role=ASSISTANT,
            conversation_id=conversation_id,
            message="I'm sorry, I had a little trouble thinking of a reply.",
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

@socketio.on('new_message')
def handle_message(json_data):
    """Handles incoming WebSocket messages and sends a response."""
    # Ensure global tokenizer and model are used if they are defined globally
    global tokenizer, model # Assuming these are your globally loaded tokenizer and model

    conversation_id_str = session.get('conversation_id')
    conversation_id = UUID(conversation_id_str)

    if not conversation_id_str:
        print("Error: conversation_id not found in session for new_message.")
        emit('cheryl_replies', {
            'role': ASSISTANT,
            'message': "I'm sorry, but I can't seem to find our conversation. Could you try reconnecting?"
        })
        return

    # Save user's message
    repository = MessagesRepository(pool)
    repository.set_message(Message(
        role='user',
        conversation_id=conversation_id,
        message=json_data['data'],
        timestamp=datetime.datetime.now(datetime.timezone.utc) # Use timezone-aware UTC
    ))

    # Create a reply message
    reply_message = say_something(conversation_id)

    repository.set_message(reply_message)

    # Emit the reply to the client
    emit('cheryl_replies', reply_message.model_dump(mode='json'))


@socketio.on('authenticate')
def handle_authentication(json):
    """Emitted by the client at connection. Provides a conversation_id that can be associated with the sid"""
    try:
        # Ensure conversation_id is a UUID
        conversation_id_str = json.get('conversation_id')
        if not conversation_id_str:
            emit('authentication_failed', {'error': 'conversation_id missing'})
            return

        conversation_id = UUID(conversation_id_str)

        repository = ConversationsRepository(pool)
        # Associate sid with conversation_id
        repository.set_conversation(Conversation(
            sid=session['sid'],
            conversation_id=conversation_id,
            timestamp=datetime.datetime.now()
        ))

        # Store conversation_id in session
        session['conversation_id'] = str(conversation_id)

        reply_message = say_something(conversation_id, 64)

        messages_repository = MessagesRepository(pool)
        messages_repository.set_message(reply_message)

        # Retrieve messages for this conversation
        repository = MessagesRepository(pool)
        messages_list = repository.get_messages_of_conversation(conversation_id, True, None)

        # Serialize messages for sending, ensuring datetime objects are converted to strings
        serialized_messages = [msg.model_dump(mode='json') for msg in messages_list]

        # Emit the messages back to the client
        emit('authentication_successful', {'conversation_id': str(conversation_id), 'messages': serialized_messages})
        print(f"Authentication successful for conversation_id: {conversation_id}, sid: {session['sid']}. Sent {len(serialized_messages)} messages.")

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
