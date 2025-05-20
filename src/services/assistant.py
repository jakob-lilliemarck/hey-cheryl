from src.config.config import Config
from src.models.message import Message, ChatMessage
from src.repositories.messages import MessagesRepository
from src.repositories.concepts import ConceptsRepository
from uuid import UUID
from typing import List, Dict
from datetime import datetime, timezone
from transformers.models.auto.modeling_auto import AutoModelForCausalLM
from pydantic import BaseModel
from transformers.models.gpt2.tokenization_gpt2_fast import GPT2TokenizerFast

ROLE = 'assistant'

class AssistantService(BaseModel):
    config: Config
    messages_repository: MessagesRepository
    concepts_repository: ConceptsRepository
    tokenizer: GPT2TokenizerFast
    model: AutoModelForCausalLM

    def __init__(
        self,
        config: Config,
        messages_repository: MessagesRepository,
        concepts_repository: ConceptsRepository,
        tokenizer: GPT2TokenizerFast,
        model: AutoModelForCausalLM,
    ):
        self.config = config
        self.messages_repository = messages_repository
        self.concepts_repository = concepts_repository
        self.tokenizer = tokenizer
        self.model = model

    def get_chat_accumulator(self) -> List[Dict[str, str]]:
        return [{
            'role': ROLE,
            'content': "Your name is Cheryl. You are not an AI assistant but a passionate human professor of aesthics and form at an arts university. You teach sculptural principles, how to model three dimensional form and how to give shape to physical products. You love working with clay. You are smart, quirky and a little bit insensitive altough you always have good intentions. Keep responses brief and fun.",
        }]

    def say_something(self, conversation_id: UUID) -> Message:
        # Create a chat history list with an injected system prompt
        history = self.get_chat_accumulator()

        # Get historic messages of this conversation from the database
        messages = self.messages_repository.get_messages_of_conversation(conversation_id, False, None)

        # Convert each to ChatMessage and append to the accumulator
        for m in messages:
            history.append(m.to_chat_message())

        try:
            # 1. Apply chat template to format the history string.
            prompt_text = self.tokenizer.apply_chat_template(
                history,
                tokenize=False,
                add_generation_prompt=True
            )

            # 2. Tokenize the prompt string to get input_ids.
            input_ids_tensor = self.tokenizer.encode(
                prompt_text,
                return_tensors="pt",
                truncation=True,        # Add truncation
                max_length=self.tokenizer.model_max_length if hasattr(self.tokenizer, 'model_max_length') and self.tokenizer.model_max_length else 1024
            ).to(self.config.DEVICE)

        except:
            pass



        message = Message(
            role='user',
            conversation_id=conversation_id,
            message="Some message",
            timestamp=datetime.now(timezone.utc)
        )

        return message
