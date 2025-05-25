# Create a connection pool (psycopg_pool)
from psycopg_pool import ConnectionPool
from psycopg import Connection



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


class Provider:
    pass
