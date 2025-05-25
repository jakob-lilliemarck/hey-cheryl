from psycopg_pool import ConnectionPool
import psycopg
from src.models import Concept
from pydantic import ValidationError
from psycopg.rows import TupleRow

GET_CONCEPTS = """
    SELECT id, concept, meaning FROM concepts;
"""

class ConceptsRepository:
    pool: ConnectionPool[psycopg.Connection[TupleRow]]

    def __init__(self, pool: ConnectionPool[psycopg.Connection[TupleRow]]):
        self.pool = pool

    def get_concepts(self) -> list[Concept]:
        """
        Retrieves messages for a given conversation ID, optionally filtering by timestamp.
        """

        concepts: list[Concept] = []
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(GET_CONCEPTS)
                    for row in cur.fetchall():
                        try:
                            concept = Concept(id=row[0], concept=row[1], meaning=row[2])
                            concepts.append(concept)
                        except ValidationError as e:
                            print(f"Validation error for concept: {row} - {e}")
        except psycopg.Error as e:
            print(f"Database error during startup: {e}")
        return concepts
