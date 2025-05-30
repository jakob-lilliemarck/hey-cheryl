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
from src.models import ChatTemplate, ChatTemplateRecord, Role, Concept
import abc
from typing import Any
import torch
from sentence_transformers import SentenceTransformer
from uuid import uuid4
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import textwrap

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
    concepts: list[Concept]
    embeddings: ndarray

    def __init__(
        self, *,
        concepts_repository: ConceptsRepository
    ):
        self.model = SentenceTransformer("thenlper/gte-small")
        self.concepts = concepts_repository.get_concepts()
        self.embeddings = self.model.encode([c.meaning for c in self.concepts])

    def get_related_concepts(self, message: str, n: int) -> list[Concept]:
        if not self.concepts:
            return []

        input = self.model.encode([message])[0]

        scores = cosine_similarity([input], self.embeddings)[0]

        sorted = np.argsort(scores)[::-1]

        concepts_to_use = [self.concepts[i] for i in sorted[:n + 1]]
        logging.info(f"most relevant concepts{[{ 'concept': self.concepts[i], 'score': scores[i] } for i in sorted[:n + 1]]}")

        return concepts_to_use

    def get_contextualized_system_prompt(self, message: str) -> str:
        """
        Retrieves related concepts and formats them into a prompt string.
        """
        concepts = self.get_related_concepts(message, 3)
        prompt_section = textwrap.dedent("""\
            You are Cheryl, professor of aesthetics at Konstfack, University of Arts, Crafts and Design.\n
            """)
        if not concepts:
            return prompt_section

        prompt_section += textwrap.dedent("""\
            Here are some key terms and phrases that are part of my (Cheryl's) unique vocabulary and way
            of thinking. When responding, please consider using these terms where appropriate, ensuring
            you use them in a way that reflects the specific meaning I (Cheryl) assign to them below:

            -- My Key Concepts --
        """)
        for concept in concepts:
            prompt_section += f"Term: {concept.concept}\n"
            prompt_section += f"Meaning: {concept.meaning}\n\n" # Add extra newline for separation

        prompt_section += "-- End Key Concepts --\n"

        return prompt_section

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
        logging.info(f"Using system prompt\n\n{system_prompt}")

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
                max_new_tokens=50,
                temperature=0.7,
                top_p=0.95,
                top_k=50,
                do_sample=True,
                repetition_penalty=2.0,
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
        contextualizer = Contextualizer(concepts_repository=concepts_repository)
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


def seed_concepts(timestamp: datetime):
    seed_concepts = [
        Concept(
            id=uuid4(),
            timestamp=timestamp,
            concept="Nice weather",
            meaning="The sun is out, the sky is clear from clouds. Its no rain, but maybe it rained during the night. There is not much wind altough there can be some."
        ),
        Concept(
            id=uuid4(),
            timestamp=timestamp,
            concept="Embodies studies",
            meaning="A pedagogical method thats based on using the bodys senses to aesthically explore, experience and to learn about something in a 'tacit' way."
        ),
        Concept(
            id=uuid4(),
            timestamp=timestamp,
            concept="Hantverksproblem",
            meaning="An unfortunate predicament some art-and-design students exhibit after prolonged exposure to too much theoretical education and too little embodied studies and concrete physical work."
        ),
        Concept(
            id=uuid4(),
            timestamp=timestamp,
            concept="Radical",
            meaning="Going to the root of a problem, being in the outskirts of normative behaviour and knowledge."
        )
    ]

    for concept in seed_concepts:
        concepts_repository.create_concept(concept)

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
