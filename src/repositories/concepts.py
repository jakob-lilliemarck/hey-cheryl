from psycopg_pool import ConnectionPool
import psycopg
from src.models import Concept
from psycopg.rows import TupleRow,class_row
from typing import List
from uuid import UUID
from datetime import datetime

SELECT_CONCEPTS = """
 SELECT
    id,
    timestamp,
    concept,
    meaning,
    deleted
FROM latest_concepts;
"""

BATCH_INSERT_CONCEPTS = """
WITH inserted_records AS (
    INSERT INTO concepts (
        id,
        timestamp,
        concept,
        meaning,
        deleted
    )
    SELECT
        *
    FROM UNNEST(
    	%s::UUID[],
    	%s::TIMESTAMPTZ[],
    	%s::TEXT[],
    	%s::TEXT[],
    	%s::BOOLEAN[]
    )
    RETURNING *
)
SELECT * from inserted_records
WHERE deleted = FALSE;
"""


class ConceptInsertionError(Exception):
    pass


class ConceptsRepository:
    pool: ConnectionPool[psycopg.Connection[TupleRow]]

    def __init__(self, pool: ConnectionPool[psycopg.Connection[TupleRow]]):
        self.pool = pool

    def get_concepts(self) -> list[Concept]:
        """
        Get all active concepts in the database
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(Concept)) as cur:
                cur.execute(SELECT_CONCEPTS)
                return cur.fetchall()

    def upsert_concepts(self, concepts: List[Concept]) -> List[Concept]:
        """
        Batch insert new concept records using UNNEST for efficiency.
        This performs an insert-only operation for all provided concepts.
        """
        if not concepts:
            return []

        ids: List[UUID] = []
        timestamps: List[datetime] = []
        concept_texts: List[str] = []
        meanings: List[str] = []
        deleted: List[bool] = []
        for c in concepts:
            ids.append(c.id)
            timestamps.append(c.timestamp)
            concept_texts.append(c.concept)
            meanings.append(c.meaning)
            deleted.append(c.deleted)

        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(Concept)) as cur:
                params_tuple = (
                    ids,
                    timestamps,
                    concept_texts,
                    meanings,
                    deleted
                )
                cur.execute(
                    BATCH_INSERT_CONCEPTS,
                    params_tuple
                )
                return cur.fetchall()
