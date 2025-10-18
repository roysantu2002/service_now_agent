"""
Database utilities for PostgreSQL connection and operations with asyncpg.
"""

import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from uuid import UUID

import asyncpg
from asyncpg.pool import Pool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)


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


# Global database pool instance
db_pool = DatabasePool()


async def initialize_database():
    await db_pool.initialize()


async def close_database():
    await db_pool.close()


# -------------------------
# Session Management
# -------------------------
async def create_session(
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    timeout_minutes: int = 60
) -> str:
    """Create a new session."""
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
    """Retrieve session by ID."""
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


async def update_session(session_id: str, metadata: Dict[str, Any]) -> bool:
    """Update session metadata by merging JSON."""
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE sessions
            SET metadata = metadata || $2::jsonb
            WHERE id = $1::uuid
              AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """,
            session_id,
            json.dumps(metadata)
        )
        return int(result.split()[-1]) > 0


# -------------------------
# Message Management
# -------------------------
async def add_message(
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Add a message to a session."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO messages (session_id, role, content, metadata)
            VALUES ($1::uuid, $2, $3, $4)
            RETURNING id::text
            """,
            session_id,
            role,
            content,
            json.dumps(metadata or {})
        )
        return row["id"]


async def get_session_messages(
    session_id: str,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Get messages for a session."""
    async with db_pool.acquire() as conn:
        query = """
            SELECT id::text, role, content, metadata, created_at
            FROM messages
            WHERE session_id = $1::uuid
            ORDER BY created_at
        """
        if limit:
            query += f" LIMIT {limit}"
        rows = await conn.fetch(query, session_id)
        return [
            {
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "metadata": json.loads(r["metadata"]),
                "created_at": r["created_at"].isoformat()
            }
            for r in rows
        ]

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


# -------------------------
# Utility
# -------------------------
async def execute_query(query: str, *params) -> List[Dict[str, Any]]:
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]


async def test_connection() -> bool:
    """Check if database connection works."""
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False
