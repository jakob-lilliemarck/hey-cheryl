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


ASSISTANT = 'assistant'
SYSTEM = 'system'
USER = 'user'

logging.info(f"Starting to load Hugging Face tokenizer: {config.MODEL_NAME}")
tokenizer = AutoTokenizer.from_pretrained(config.MODEL_NAME)
logging.info(f"Hugging Face tokenizer '{config.MODEL_NAME}' loaded successfully.")

logging.info(f"Starting to load Hugging Face model: {config.MODEL_NAME}. This may take a while...")
model = AutoModelForCausalLM.from_pretrained(config.MODEL_NAME)
logging.info(f"Hugging Face model '{config.MODEL_NAME}' loaded successfully and is available.")



def get_all_concepts() -> List[Concept]:
    """
    Returns all concepts from the in-memory cache.
    """
    return all_concepts

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
    repository.create_message(Message(
        role='user',
        conversation_id=conversation_id,
        message=json_data['data'],
        timestamp=datetime.datetime.now(datetime.timezone.utc) # Use timezone-aware UTC
    ))

    # Create a reply message
    reply_message = say_something(conversation_id)

    repository.create_message(reply_message)

    # Emit the reply to the client
    emit('cheryl_replies', reply_message.model_dump(mode='json'))
