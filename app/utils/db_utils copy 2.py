"""
Database utilities for PostgreSQL connection and operations with asyncpg.
"""

# db_utils.py

import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager

import asyncpg
from asyncpg.pool import Pool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)


# ---------------------------------------------------
# Database Pool
# ---------------------------------------------------
class DatabasePool:
    """Manages PostgreSQL connection pool."""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not set")
        self.pool: Optional[Pool] = None
    
    async def initialize(self):
        """Create connection pool if not already initialized."""
        if self.pool:
            return
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=5,
            max_size=20,
            max_inactive_connection_lifetime=300,
            command_timeout=60
        )
        logger.info("Database connection pool initialized")
    
    async def close(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database connection pool closed")
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool."""
        if not self.pool:
            await self.initialize()
        async with self.pool.acquire() as conn:
            yield conn


# Global pool instance
db_pool = DatabasePool()


# ---------------------------------------------------
# Lifecycle Management
# ---------------------------------------------------
async def initialize_database():
    await db_pool.initialize()


async def close_database():
    await db_pool.close()


@asynccontextmanager
async def get_db_connection():
    """Context manager for database connections."""
    if not db_pool.pool:
        await db_pool.initialize()
    async with db_pool.acquire() as connection:
        try:
            yield connection
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            raise


# ---------------------------------------------------
# Query Helpers
# ---------------------------------------------------
async def execute_query(query: str, *params, return_value: bool = False):
    """
    Execute a SQL query and optionally return a single value.
    If `return_value=True`, fetch a single scalar value (for RETURNING clauses).
    Otherwise:
      - For SELECT → returns list[dict]
      - For non-SELECT → executes and returns None
    """
    try:
        async with get_db_connection() as conn:
            sql = query.strip().lower()

            if sql.startswith("select"):
                rows = await conn.fetch(query, *params)
                return [dict(r) for r in rows]

            elif return_value:
                # Support RETURNING id::text or similar cases
                row = await conn.fetchrow(query, *params)
                if not row:
                    return None
                # Return first column value if it's a single value
                if len(row.keys()) == 1:
                    return list(row.values())[0]
                return dict(row)

            else:
                await conn.execute(query, *params)
                return None

    except Exception as e:
        logger.error(
            "Database operation failed",
            extra={"error": str(e), "query": query, "params": params},
        )
        raise

# ---------------------------------------------------
# Fetch Helpers

async def fetch_one(query: str, *args) -> Optional[dict]:
    async with get_db_connection() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def fetch_many(query: str, *args) -> list[dict]:
    async with get_db_connection() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(row) for row in rows]


async def fetch_value(query: str, *args):
    async with get_db_connection() as conn:
        return await conn.fetchval(query, *args)


async def test_connection() -> bool:
    try:
        async with get_db_connection() as conn:
            await conn.fetchval("SELECT 1")
        logger.info("Database connection test passed ✅")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


# ---------------------------------------------------
# Session Management
# ---------------------------------------------------
async def create_session(
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    timeout_minutes: int = 60
) -> str:
    async with db_pool.acquire() as conn:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)
        row = await conn.fetchrow(
            """
            INSERT INTO sessions (user_id, metadata, expires_at)
            VALUES ($1, $2, $3)
            RETURNING id::text
            """,
            user_id,
            json.dumps(metadata or {}),
            expires_at
        )
        return row["id"]


async def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id::text, user_id, metadata, created_at, updated_at, expires_at
            FROM sessions
            WHERE id = $1::uuid
              AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """,
            session_id
        )
        if not row:
            return None
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "metadata": json.loads(row["metadata"]),
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
            "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None
        }


# ---------------------------------------------------
# Vector / Hybrid Search
# ---------------------------------------------------
async def vector_search(embedding: List[float], limit: int = 10) -> List[Dict[str, Any]]:
    """
    Performs vector similarity search using PostgreSQL function match_chunks().
    """
    async with db_pool.acquire() as conn:
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"
        rows = await conn.fetch("SELECT * FROM match_chunks($1::vector, $2)", embedding_str, limit)
        return [
            {
                "chunk_id": r["chunk_id"],
                "document_id": r["document_id"],
                "content": r["content"],
                "similarity": r["similarity"],
                "metadata": json.loads(r["metadata"]),
                "document_title": r["document_title"],
                "document_source": r["document_source"]
            }
            for r in rows
        ]


async def hybrid_search(
    embedding: List[float],
    query_text: str,
    limit: int = 10,
    text_weight: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Hybrid search combining vector similarity and text search using hybrid_search().
    """
    async with db_pool.acquire() as conn:
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"
        rows = await conn.fetch(
            """
            SELECT 
                chunk_id,
                document_id,
                content,
                metadata,
                document_title,
                document_source,
                vector_similarity::double precision,
                text_similarity::double precision,
                combined_score::double precision
            FROM hybrid_search($1::vector, $2, $3, $4)
            """,
            embedding_str,
            query_text,
            limit,
            text_weight
        )
        return [
            {
                "chunk_id": r["chunk_id"],
                "document_id": r["document_id"],
                "content": r["content"],
                "combined_score": r["combined_score"],
                "vector_similarity": r["vector_similarity"],
                "text_similarity": r["text_similarity"],
                "metadata": json.loads(r["metadata"]),
                "document_title": r["document_title"],
                "document_source": r["document_source"]
            }
            for r in rows
        ]


# ---------------------------------------------------
# Webhook & Incident Tables
# ---------------------------------------------------
async def upsert_webhook_event(
    incident_id: str,
    sys_id: str,
    action_type: str,
    payload: Dict[str, Any],
    incident_data: Optional[Dict[str, Any]] = None,
    status: str = "received"
) -> str:
    """Insert or update webhook event and return its UUID."""
    async with get_db_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO webhook_events (
                incident_id, sys_id, action_type, payload, incident_data, status, updated_at
            )
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6, NOW())
            ON CONFLICT (incident_id)
            DO UPDATE SET
                sys_id = EXCLUDED.sys_id,
                action_type = EXCLUDED.action_type,
                payload = EXCLUDED.payload,
                incident_data = EXCLUDED.incident_data,
                status = EXCLUDED.status,
                updated_at = NOW()
            RETURNING id::text;
            """,
            incident_id,
            sys_id,
            action_type,
            json.dumps(payload),
            json.dumps(incident_data or {}),
            status
        )
        return row["id"]


async def initialize_tables() -> None:
    """Initialize webhook and AI incident tables."""
    try:
        # Webhook Events
        await execute_query("""
            CREATE TABLE IF NOT EXISTS webhook_events (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                incident_id VARCHAR(100) UNIQUE NOT NULL,
                sys_id VARCHAR(100) NOT NULL,
                action_type VARCHAR(50) NOT NULL,
                payload JSONB NOT NULL,
                incident_data JSONB,
                status VARCHAR(20) DEFAULT 'received',
                ai_processed BOOLEAN DEFAULT FALSE,
                ai_analysis_results JSONB,
                processing_started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                processing_completed_at TIMESTAMP WITH TIME ZONE,
                error_message TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        await execute_query("""
            CREATE INDEX IF NOT EXISTS idx_webhook_events_incident_id ON webhook_events(incident_id);
        """)
        await execute_query("""
            CREATE INDEX IF NOT EXISTS idx_webhook_events_status ON webhook_events(status);
        """)

        # Incident Analysis
        await execute_query("""
            CREATE TABLE IF NOT EXISTS incident_analysis (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                webhook_event_id UUID REFERENCES webhook_events(id) ON DELETE CASCADE,
                incident_id VARCHAR(100) NOT NULL,
                sys_id VARCHAR(100) NOT NULL,
                category VARCHAR(100),
                severity VARCHAR(50),
                confidence DECIMAL(5,4),
                reasoning TEXT,
                supporting_evidence JSONB,
                suggested_priority INTEGER,
                recommended_actions JSONB,
                related_incidents JSONB,
                metadata JSONB,
                ai_model_used VARCHAR(100),
                processing_time_ms INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        logger.info("✅ Database tables initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize tables: {e}")
        raise


# -------------------------
# Document Chunks
# -------------------------
async def get_document_chunks(document_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all chunks for a document.

    Args:
        document_id: UUID of the document

    Returns:
        List of chunks with content, index, and metadata
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT chunk_id::text, content, chunk_index, metadata
            FROM chunks
            WHERE document_id = $1::uuid
            ORDER BY chunk_index ASC
            """,
            document_id
        )
        return [
            {
                "chunk_id": r["chunk_id"],
                "content": r["content"],
                "chunk_index": r["chunk_index"],
                "metadata": json.loads(r["metadata"])
            }
            for r in rows
        ]


# -------------------------
# Document Management
# -------------------------
async def get_document(document_id: str) -> Optional[Dict[str, Any]]:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id::text, title, source, content, metadata, created_at, updated_at
            FROM documents
            WHERE id = $1::uuid
            """,
            document_id
        )
        if not row:
            return None
        return {
            "id": row["id"],
            "title": row["title"],
            "source": row["source"],
            "content": row["content"],
            "metadata": json.loads(row["metadata"]),
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat()
        }


async def list_documents(
    limit: int = 100,
    offset: int = 0,
    metadata_filter: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    async with db_pool.acquire() as conn:
        query = """
            SELECT d.id::text, d.title, d.source, d.metadata, d.created_at, d.updated_at, COUNT(c.id) AS chunk_count
            FROM documents d
            LEFT JOIN chunks c ON d.id = c.document_id
        """
        params = []
        if metadata_filter:
            query += f" WHERE d.metadata @> ${len(params)+1}::jsonb"
            params.append(json.dumps(metadata_filter))
        query += """
            GROUP BY d.id, d.title, d.source, d.metadata, d.created_at, d.updated_at
            ORDER BY d.created_at DESC
            LIMIT ${%d} OFFSET ${%d}
        """ % (len(params)+1, len(params)+2)
        params.extend([limit, offset])
        rows = await conn.fetch(query, *params)
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "source": r["source"],
                "metadata": json.loads(r["metadata"]),
                "created_at": r["created_at"].isoformat(),
                "updated_at": r["updated_at"].isoformat(),
                "chunk_count": r["chunk_count"]
            }
            for r in rows
        ]


# -------------------------
# Vector / Hybrid Search
# -------------------------
async def vector_search(embedding: List[float], limit: int = 10) -> List[Dict[str, Any]]:
    async with db_pool.acquire() as conn:
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"
        rows = await conn.fetch("SELECT * FROM match_chunks($1::vector, $2)", embedding_str, limit)
        return [
            {
                "chunk_id": r["chunk_id"],
                "document_id": r["document_id"],
                "content": r["content"],
                "similarity": r["similarity"],
                "metadata": json.loads(r["metadata"]),
                "document_title": r["document_title"],
                "document_source": r["document_source"]
            }
            for r in rows
        ]


async def hybrid_search(
    embedding: List[float],
    query_text: str,
    limit: int = 10,
    text_weight: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Hybrid search combining vector similarity and keyword search.
    Ensures PostgreSQL types match function definition.
    """
    async with db_pool.acquire() as conn:
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"
        rows = await conn.fetch(
            """
            SELECT 
                chunk_id,
                document_id,
                content,
                metadata,
                document_title,
                document_source,
                vector_similarity::double precision,
                text_similarity::double precision,
                combined_score::double precision
            FROM hybrid_search($1::vector, $2, $3, $4)
            """,
            embedding_str,
            query_text,
            limit,
            text_weight
        )
        return [
            {
                "chunk_id": r["chunk_id"],
                "document_id": r["document_id"],
                "content": r["content"],
                "combined_score": r["combined_score"],
                "vector_similarity": r["vector_similarity"],
                "text_similarity": r["text_similarity"],
                "metadata": json.loads(r["metadata"]),
                "document_title": r["document_title"],
                "document_source": r["document_source"]
            }
            for r in rows
        ]

