from time import sleep
import logging
from numpy._core.numeric import ndarray
from src.repositories.concepts import ConceptsRepository
from src.repositories.messages import MessagesRepository
from src.repositories.users import UsersRepository
from src.config.config import Config
from psycopg_pool import ConnectionPool
from psycopg.rows import TupleRow
from psycopg import Connection
from datetime import datetime, timezone
from src.services.messages import MessagesService
from src.services.users import UsersService
from transformers.models.auto.tokenization_auto import AutoTokenizer
from transformers.models.auto.modeling_auto import AutoModelForCausalLM
from src.models import ChatTemplate, ChatTemplateRecord, Role, SystemPromptKey, Concept
import abc
from typing import Any, List
import torch
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from src.repositories.system_prompts import SystemPromptsRepository

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

class AbstractAssistant(abc.ABC):
    @abc.abstractmethod
    def formulate(self, message: str) -> str:
        pass

class AbstractContextualizer(abc.ABC):
    @abc.abstractmethod
    def get_contextualized_system_prompt(self, message: str) -> str:
        pass

class MockedAssistant(AbstractAssistant):
    def formulate(self, message: str) -> str:
        return "mocked"

class Contextualizer(AbstractContextualizer):
    concepts_repository: ConceptsRepository
    system_prompts_repository: SystemPromptsRepository
    model: SentenceTransformer

    def __init__(
        self, *,
        concepts_repository: ConceptsRepository,
        system_prompts_repository: SystemPromptsRepository,
    ):
        self.model = SentenceTransformer("thenlper/gte-small")
        self.concepts_repository = concepts_repository
        self.system_prompts_repository = system_prompts_repository

    def get_related_concepts(self, message: str, n: int) -> list[Concept]:
        concepts = self.concepts_repository.get_concepts()
        embeddings: ndarray = self.model.encode([c.meaning for c in concepts])

        if not concepts:
            return []

        input = self.model.encode([message])[0]

        scores = cosine_similarity([input], embeddings)[0]

        sorted = np.argsort(scores)[::-1]

        concepts_to_use = [concepts[i] for i in sorted[:n + 1]]
        logging.info(f"most relevant concepts{[{ 'concept': concepts[i], 'score': scores[i] } for i in sorted[:n + 1]]}")

        return concepts_to_use

    @staticmethod
    def template_concepts(concepts: List[Concept]) -> str:
        buf = "\n-- Key Concepts --\n"
        for c in concepts:
            buf += f"- **{c.concept}:** {c.meaning}\n"
        buf += "\n-- Key Concepts --\n"
        return buf

    def get_contextualized_system_prompt(self, message: str) -> str:
        """
        Retrieves related concepts and formats them into a prompt string.
        """
        base_prompt = self.system_prompts_repository.get_system_prompt(SystemPromptKey.BASE.value)
        concepts = self.get_related_concepts(message, 3)
        if not concepts:
            # If nothing were retrieved, just return the base prompt
            return base_prompt.prompt

        related_concepts_prompt = self.system_prompts_repository.get_system_prompt(SystemPromptKey.RELATED_CONCEPTS.value)

        # If we got some similar content, build up
        prompt = ""
        prompt += f"{base_prompt.prompt}\n"
        prompt += f"{related_concepts_prompt.prompt}\n"
        prompt += Contextualizer.template_concepts(concepts)
        return prompt

class Assistant(AbstractAssistant):
    contextualizer: AbstractContextualizer
    tokenizer: Any
    model: Any

    def __init__(
        self,
        tokenizer: Any,
        model: Any,
        contextualizer: AbstractContextualizer
    ):
        self.contextualizer = contextualizer
        self.tokenizer = tokenizer
        self.model = model

    def formulate(self, message: str) -> str:
        system_prompt = self.contextualizer.get_contextualized_system_prompt(message)
        logging.info(f"Using prompt\n\n{system_prompt}")

        templated = Assistant.template_one_off(
            user=message,
            system=system_prompt
        ).model_dump(mode='json')

        logging.info(f"Generating with template:\n{templated}")
        prompt = self.tokenizer.apply_chat_template(
            templated,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False
        )

        input = self.tokenizer.encode(
            prompt,
            return_tensors="pt",
            padding=True,
        ).to(config.DEVICE)

        input_token_length = input.shape[1]

        with torch.no_grad(): # Important for inference
            output = self.model.generate(
                input,
                max_new_tokens=100,
                temperature=0.5,
                top_p=0.95,
                top_k=50,
                do_sample=True,
                repetition_penalty=2.0,
                eos_token_id=self.tokenizer.eos_token_id
            )

        reply_tokens = output[0][input_token_length:]

        reply: str = self.tokenizer.decode(
            reply_tokens,
            skip_special_tokens=True
        ).strip()

        return reply

    @staticmethod
    def template_one_off(
        *,
        user: str,
        system: str
    ) -> ChatTemplate:
        return ChatTemplate([
            ChatTemplateRecord(
                role=Role.SYSTEM,
                content=system
            ),
            ChatTemplateRecord(
                role=Role.USER,
                content=user
            )
        ])

class AssistantService:
    messages_repository: MessagesRepository
    concepts_repository: ConceptsRepository
    messages_service: MessagesService
    assistant: AbstractAssistant

    def __init__(
        self, *,
        messages_repository: MessagesRepository,
        concepts_repository: ConceptsRepository,
        messages_service: MessagesService,
        assistant: AbstractAssistant
        ):
        self.messages_repository = messages_repository
        self.concepts_repository = concepts_repository
        self.messages_service = messages_service
        self.assistant = assistant

    def poll(self):
        logging.info("AssistantService.poll")
        reply = self.messages_service.get_next_enqueued_reply(
            timestamp=datetime.now(timezone.utc)
        )

        if reply:
            # Get the associated message
            message = messages_repository.get_message(message_id=reply.message_id)

            # Ask cheryl to respond to it
            response = self.assistant.formulate(message.message)

            # Update the reply with Cheryls response
            messages_service.append_reply_content(
                reply=reply,
                timestamp=datetime.now(timezone.utc),
                content=response
            )

def main():
    if config.WITH_MOCKED_ASSISTANT:
        logging.info("Mocking tokenizer and model")
        assistant = MockedAssistant()
    else:
        tokenizer = AutoTokenizer.from_pretrained(config.MODEL_NAME)
        model = AutoModelForCausalLM.from_pretrained(config.MODEL_NAME)
        contextualizer = Contextualizer(
            concepts_repository=concepts_repository,
            system_prompts_repository=system_prompts_repository,
        )
        assistant = Assistant(
            contextualizer=contextualizer,
            tokenizer=tokenizer,
            model=model
        )

    assistant_service = AssistantService(
        messages_repository=messages_repository,
        concepts_repository=concepts_repository,
        messages_service=messages_service,
        assistant=assistant
    )

    while True:
        assistant_service.poll()
        sleep(2)


if __name__ == '__main__':
    # HuggingFaceTB/SmolLM2-360M-Instruct
    # Qwen/Qwen3-0.6B
    now = datetime.now(timezone.utc)
    # seed_concepts(now)
    users_service.create_user(
        user_id=config.ASSISTANT_USER_ID,
        timestamp=now,
        name="Cheryl"
    )

    users_service.register_user_connection(
        user_id=config.ASSISTANT_USER_ID,
        timestamp=now
    )

    main()
