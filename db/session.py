"""
Database Session
================

Database connection helpers with a configurable backend.

Set ``DB_BACKEND=postgres`` (the default) to use Postgres + PgVector:
- Agent storage (sessions, memory, metrics, evals, knowledge, schedules) → Postgres
- Vector storage (RAG knowledge bases) → PgVector (hybrid search)
- Postgres runs in-container (installed in the workspace image), data at
  ``/app/data/pgdata`` on the persistent volume.

Set ``DB_BACKEND=sqlite`` for zero-server, file-based storage (fallback):
- Agent storage → SQLite
- Vector storage → ChromaDB

``get_db()`` returns the agent-storage database for the active backend.
``create_knowledge()`` returns a Knowledge base wired to the active backend's
vector database.
"""

from os import getenv
from pathlib import Path

from agno.db.postgres import PostgresDb
from agno.db.sqlite import SqliteDb
from agno.knowledge import Knowledge
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.vectordb.chroma import ChromaDb
from agno.vectordb.pgvector import PgVector
from agno.vectordb.search import SearchType

from db.url import db_url

DB_ID = "agentos-db"

# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------
DB_BACKEND = getenv("DB_BACKEND", "postgres").lower()

# SQLite + ChromaDB file locations (only used when DB_BACKEND=sqlite)
DATA_DIR = Path(getenv("DATA_DIR", "data")).resolve()
SQLITE_DB_FILE = str(DATA_DIR / "agents.db")
CHROMA_DB_PATH = str(DATA_DIR / "chromadb")


def get_db(contents_table: str | None = None) -> PostgresDb | SqliteDb:
    """Create a database instance for the active backend.

    Pass ``contents_table`` only when this database is the ``contents_db``
    of a Knowledge base — it tells agno where to persist document contents.
    For plain agent persistence (sessions, memory) leave it unset.
    """
    if DB_BACKEND == "postgres":
        if contents_table is not None:
            return PostgresDb(id=DB_ID, db_url=db_url, knowledge_table=contents_table)
        return PostgresDb(id=DB_ID, db_url=db_url)

    # SQLite (fallback)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if contents_table is not None:
        return SqliteDb(
            id=DB_ID, db_file=SQLITE_DB_FILE, knowledge_table=contents_table
        )
    return SqliteDb(id=DB_ID, db_file=SQLITE_DB_FILE)


def create_knowledge(name: str, table_name: str) -> Knowledge:
    """Knowledge base with hybrid search, backed by the active backend.

    Plug into an Agent's ``knowledge=`` to give it a RAG surface.
    Vectors land in ``table_name``; document contents in ``{table_name}_contents``.
    """
    if DB_BACKEND == "postgres":
        return Knowledge(
            name=name,
            vector_db=PgVector(
                db_url=db_url,
                table_name=table_name,
                search_type=SearchType.hybrid,
                embedder=OpenAIEmbedder(id="text-embedding-3-small"),
            ),
            contents_db=get_db(contents_table=f"{table_name}_contents"),
        )

    # ChromaDB (fallback)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return Knowledge(
        name=name,
        vector_db=ChromaDb(
            collection=table_name,
            path=CHROMA_DB_PATH,
            persistent_client=True,
            search_type=SearchType.hybrid,
            embedder=OpenAIEmbedder(id="text-embedding-3-small"),
        ),
        contents_db=get_db(contents_table=f"{table_name}_contents"),
    )


# Backward-compatible alias — existing code that calls get_postgres_db()
# will get the active backend (sqlite or postgres) transparently.
get_postgres_db = get_db
