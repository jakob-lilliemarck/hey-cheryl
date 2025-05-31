from src.repositories.concepts import ConceptsRepository
from src.config.config import Config
from src.models import Concept, SystemPrompt, SystemPromptKey
from uuid import UUID
from typing import Dict, List, Tuple
from datetime import datetime
from src.repositories.system_prompts import SystemPromptsRepository


class ConceptsService():
    config: Config
    concepts_repository: ConceptsRepository
    system_prompts_repository: SystemPromptsRepository

    def __init__(self, *,
        config: Config,
        concepts_repository: ConceptsRepository,
        system_prompts_repository: SystemPromptsRepository
    ):
        self.config = config
        self.concepts_repository = concepts_repository
        self.system_prompts_repository = system_prompts_repository

    def sync_concepts(
        self, *,
        timestamp: datetime,
        concepts: List[Tuple[UUID, str, str]]
    ) -> List[Concept]:
        """
        Sync concepts to those present in the list. This will:
            1. Create concepts that do not yet exists
            2. Insert a new record of concepts that do exist
            3. Insert a new record with an "inactivated" flag for
            any existing concept not present in the provided list.
        """
        existing = self.concepts_repository.get_concepts()

        to_upsert: Dict[UUID, Concept] = {}

        for c in existing:
            # Default to inactivate all existing concepts
            to_upsert[c.id] = Concept(
                id=c.id,
                timestamp=timestamp,
                concept=c.concept,
                meaning=c.meaning,
                deleted=True
            )

        for id, concept, meaning in concepts:
            # Then overwrite with the new ones
            to_upsert[id] = Concept(
                id=id,
                timestamp=timestamp,
                concept=concept,
                meaning=meaning,
                deleted=True
            )

        return self.concepts_repository.upsert_concepts(list(to_upsert.values()))

    def update_system_prompts(
        self, *,
        prompts: List[Tuple[str, str]],
        timestamp: datetime
    ) -> List[SystemPrompt]:
        system_prompts: List[SystemPrompt] = []
        for key, prompt in prompts:
            system_prompts.append(SystemPrompt(
                key=SystemPromptKey(key),
                prompt=prompt,
                timestamp=timestamp
            ))
        return self.system_prompts_repository.upsert_system_prompts(system_prompts=system_prompts)
