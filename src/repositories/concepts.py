from psycopg_pool import ConnectionPool
import psycopg
from src.models import Concept
from psycopg.rows import TupleRow,class_row

SELECT_CONCEPTS = """
 SELECT
    id,
    timestamp,
    concept,
    meaning
FROM concepts;
"""

INSERT_CONCEPT = """
INSERT INTO concepts (
    id,
    timestamp,
    concept,
    meaning
) VALUES (%s, %s, %s, %s)
RETURNING *;
"""

class ConceptInsertionError(Exception):
    pass


class ConceptsRepository:
    pool: ConnectionPool[psycopg.Connection[TupleRow]]

    def __init__(self, pool: ConnectionPool[psycopg.Connection[TupleRow]]):
        self.pool = pool

    def get_concepts(self) -> list[Concept]:
        """
        Retrieves messages for a given conversation ID, optionally filtering by timestamp.
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(Concept)) as cur:
                cur.execute(SELECT_CONCEPTS)
                return cur.fetchall()

    def create_concept(self, concept: Concept) -> Concept:
        """
        Create a new concept record
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=class_row(Concept)) as cur:
                cur.execute(
                    INSERT_CONCEPT,
                    (
                        str(concept.id),
                        concept.timestamp,
                        concept.concept,
                        concept.meaning,
                    ),
                )

                new_reply = cur.fetchone()
                if not new_reply:
                    raise ConceptInsertionError("Failed to insert reply")
                return new_reply
