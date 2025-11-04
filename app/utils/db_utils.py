"""
Database utilities for PostgreSQL connection and operations with asyncpg.
"""

# db_utils.py
"""
Database utilities for PostgreSQL connection and operations with asyncpg.
"""

import os
import json
import logging
from turtle import get_poly
from typing import List, Dict, Any, Optional
from datetime import datetime
from contextlib import asynccontextmanager

import asyncpg
from asyncpg.pool import Pool
from dotenv import load_dotenv

# ---------------------------------------------------
# Setup
# ---------------------------------------------------
load_dotenv()
logger = logging.getLogger(__name__)

SQL_DIR = os.path.join(os.path.dirname(__file__), "sql")

print(f"[DB UTIL] SQL Directory: {SQL_DIR}")

def parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        # Strip Z if included
        return datetime.fromisoformat(value.replace("Z", ""))
    except:
        return None
    
async def _execute_sql_file(path: str) -> None:
    if not os.path.exists(path):
        logger.warning(f"SQL file not found: {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()

    try:
        await execute_query(sql)
        logger.info(f"Executed SQL file: {path}")
    except Exception as e:
        logger.error(f"Failed to execute sql file {path}: {e}")
        raise

# ---------------------------------------------------
# Database Pool Manager
# ---------------------------------------------------
class DatabasePool:
    """Manages PostgreSQL connection pool."""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not set")
        self.pool: Optional[Pool] = None
    
    async def initialize(self):
        """Create asyncpg pool if not initialized."""
        if self.pool:
            print("[DB READY ✅] Connection pool already initialized")
            return
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=2,
            max_size=10,
            max_inactive_connection_lifetime=300,
            command_timeout=60
        )
        print("[DB READY ✅] Connection pool created")
        logger.info("✅ Database connection pool initialized")

    async def close(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("🛑 Database pool closed")

    @asynccontextmanager
    async def acquire(self):
        """Context manager for pooled connection."""
        if not self.pool:
            await self.initialize()
        async with self.pool.acquire() as conn:
            yield conn


# Global pool instance
db_pool = DatabasePool()


# ---------------------------------------------------
# Lifecycle
# ---------------------------------------------------
async def initialize_database():
    await db_pool.initialize()


async def close_database():
    await db_pool.close()


@asynccontextmanager
async def get_db_connection():
    """Get pooled database connection."""
    if not db_pool.pool:
        await db_pool.initialize()
    async with db_pool.acquire() as connection:
        yield connection


# ---------------------------------------------------
# Query Execution Helper
# ---------------------------------------------------
async def execute_query(query: str, *params, return_value: bool = False):
    """
    Execute any SQL query safely with detailed debug output.
    """
    if len(params) == 1 and isinstance(params[0], (tuple, list)):
        params = tuple(params[0])

    try:
        if not db_pool.pool:
            raise RuntimeError("❌ Database connection pool not initialized")

        async with db_pool.acquire() as conn:
            q_clean = query.strip().replace("\n", " ")
            print(f"\n[DB DEBUG] Executing:\n{q_clean}\nParams: {params}\n")

            if q_clean.lower().startswith("select"):
                rows = await conn.fetch(query, *params)
                return [dict(r) for r in rows]

            if return_value:
                row = await conn.fetchrow(query, *params)
                if not row:
                    print("⚠️ No rows returned.")
                    return None
                result = dict(row)
                if len(result) == 1:
                    return list(result.values())[0]
                return result

            result = await conn.execute(query, *params)
            return result

    except Exception as e:
        print(f"\n[❌ DB ERROR] {e}\nQUERY:\n{query}\nPARAMS: {params}\n")
        logger.error(f"❌ DB Query failed: {e}")
        raise


# ---------------------------------------------------
# Fetch Helpers
# ---------------------------------------------------
async def fetch_one(query: str, *args) -> Optional[dict]:
    async with get_db_connection() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def fetch_many(query: str, *args) -> List[dict]:
    async with get_db_connection() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]


async def fetch_value(query: str, *args):
    async with get_db_connection() as conn:
        return await conn.fetchval(query, *args)


async def test_connection() -> bool:
    try:
        async with get_db_connection() as conn:
            await conn.fetchval("SELECT 1")
        print("[✅] Database connection test passed")
        logger.info("✅ Database connection test passed")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection test failed: {e}")
        return False


# ---------------------------------------------------
# Webhook Events Table
# ---------------------------------------------------
async def upsert_webhook_event(
    incident_id: str,
    sys_id: str,
    action_type: str,
    payload: Dict[str, Any],
    incident_data: Optional[Dict[str, Any]] = None,
    status: str = "received"
) -> str:
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

# ---------------------------------------------------
# Initialize Tables
# ---------------------------------------------------
async def initialize_tables() -> None:
    try:
        async with get_db_connection() as conn:

            # Drop and recreate incident_analysis table with UNIQUE(sys_id)
            await conn.execute("""
                DROP TABLE IF EXISTS incident_analysis CASCADE;
            """)

            # Ensure webhook_events exists first (because of FK)
            await conn.execute("""
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

            # Recreate incident_analysis properly
            await conn.execute("""
                CREATE TABLE incident_analysis (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    webhook_event_id UUID REFERENCES webhook_events(id) ON DELETE CASCADE,
                    incident_id VARCHAR(100) NOT NULL,
                    sys_id VARCHAR(100) NOT NULL UNIQUE,
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
                    analysis_level VARCHAR(10),
                    processing_time_ms INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)

            # (Optional) add index for faster retrieval
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_incident_analysis_sys_id
                ON incident_analysis(sys_id);
            """)

        print("[✅] Database tables dropped and recreated successfully")
        logger.info("✅ Database tables dropped and recreated successfully")
        
         # Execute files (deterministic order)
        sql_files = [
            os.path.join(SQL_DIR, f) for f in sorted(os.listdir(SQL_DIR))
            if f.endswith(".sql")
        ]
        for fp in sql_files:
            await _execute_sql_file(fp)

        logger.info(f"✅ Database tables verified/created from SQL directory: {SQL_DIR}")

    except Exception as e:
        print(f"[❌ TABLE INIT ERROR] {e}")
        logger.error(f"❌ Failed to initialize tables: {e}")
        raise

# ---------------------------------------------------
# Incident Analysis Insert / Update
# ---------------------------------------------------
async def store_incident_analysis(
    webhook_event_id: str,
    incident_id: str,
    sys_id: str,
    analysis_results: Dict[str, Any],
    ai_model_used: str = "unknown",
    analysis_level: Optional[str] = None
) -> str:
    query = """
        INSERT INTO incident_analysis (
            webhook_event_id,
            incident_id,
            sys_id,
            category,
            severity,
            confidence,
            reasoning,
            supporting_evidence,
            suggested_priority,
            recommended_actions,
            related_incidents,
            metadata,
            ai_model_used,
            analysis_level,
            created_at
        )
        VALUES (
            $1::uuid, $2, $3, $4, $5, $6, $7,
            $8::jsonb, $9, $10::jsonb, $11::jsonb,
            $12::jsonb, $13, $14, NOW()
        )
        ON CONFLICT (sys_id)
        DO UPDATE SET
            category = EXCLUDED.category,
            severity = EXCLUDED.severity,
            confidence = EXCLUDED.confidence,
            reasoning = EXCLUDED.reasoning,
            supporting_evidence = EXCLUDED.supporting_evidence,
            suggested_priority = EXCLUDED.suggested_priority,
            recommended_actions = EXCLUDED.recommended_actions,
            related_incidents = EXCLUDED.related_incidents,
            metadata = EXCLUDED.metadata,
            ai_model_used = EXCLUDED.ai_model_used,
            analysis_level = EXCLUDED.analysis_level,
            updated_at = NOW()
        RETURNING id::text;
    """

    params = (
        webhook_event_id,
        incident_id,
        sys_id,
        analysis_results.get("category", "unknown"),
        analysis_results.get("severity", "medium"),
        float(analysis_results.get("confidence", 0.0)),
        analysis_results.get("reasoning", "No reasoning provided"),
        json.dumps(analysis_results.get("supporting_evidence", [])),
        analysis_results.get("suggested_priority", 3),
        json.dumps(analysis_results.get("recommended_actions", [])),
        json.dumps(analysis_results.get("related_incidents", [])),
        json.dumps(analysis_results.get("metadata", {})),
        ai_model_used,
        analysis_level or analysis_results.get("analysis_level", "L3")
    )

    record_id = await execute_query(query, params, return_value=True)
    logger.info(f"✅ Incident analysis stored for {incident_id} ({analysis_level})")
    return record_id


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


# add somewhere in app/utils/db_utils.py (near other store helpers)

async def store_incident_resolution(
    payload: Dict[str, Any]
) -> str:
    """
    Persist analysis payload into incident_resolution table.
    - webhook_event_id may be None (we still store)
    - payload is the exact JSON structure returned from analyze_incident_only
    Returns: inserted/updated record id (text)
    """
    # Normalize top-level fields and nested `data`
    data = payload.get("data") or {}
    # data.id may be a UUID-like string; keep as text
    query = """
        INSERT INTO incident_resolution (
            success,
            sys_id,
            analysis_type,
            ai_model,
            usage,
            data_id,
            issue,
            issue_category,
            category,
            level,
            description,
            steps_to_resolve,
            technical_details,
            complete_description,
            analyzed_at,
            confidence_score,
            pdf_path,
            json_path,
            md_path,
            raw_ai_output_path,
            parsing_error,
            validation_error,
            metadata,
            created_at
        )
        VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8, $9, $10,
            $11, $12::jsonb, $13, $14, $15, $16,
            $17, $18, $19, $20,
            $21, $22, $23::jsonb, NOW()
        )
        ON CONFLICT (sys_id)
        DO UPDATE SET
            success = EXCLUDED.success,
            analysis_type = EXCLUDED.analysis_type,
            ai_model = EXCLUDED.ai_model,
            usage = EXCLUDED.usage,
            data_id = EXCLUDED.data_id,
            issue = EXCLUDED.issue,
            issue_category = EXCLUDED.issue_category,
            category = EXCLUDED.category,
            level = EXCLUDED.level,
            description = EXCLUDED.description,
            steps_to_resolve = EXCLUDED.steps_to_resolve,
            technical_details = EXCLUDED.technical_details,
            complete_description = EXCLUDED.complete_description,
            analyzed_at = EXCLUDED.analyzed_at,
            confidence_score = EXCLUDED.confidence_score,
            pdf_path = EXCLUDED.pdf_path,
            json_path = EXCLUDED.json_path,
            md_path = EXCLUDED.md_path,
            raw_ai_output_path = EXCLUDED.raw_ai_output_path,
            parsing_error = EXCLUDED.parsing_error,
            validation_error = EXCLUDED.validation_error,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING id::text;
    """

    params = (
        bool(payload.get("success", False)),
        payload.get("sys_id"),
        payload.get("analysis_type"),
        payload.get("ai_model"),
        json.dumps(payload.get("usage")) if payload.get("usage") is not None else None,
        data.get("id"),
        data.get("issue"),
        data.get("issue_category"),
        data.get("category"),
        data.get("level"),
        data.get("description"),
        json.dumps(data.get("steps_to_resolve", [])),
        data.get("technical_details"),
        data.get("complete_description"),
        # analyzed_at could be string; pass as-is (Postgres TIMESTAMPTZ accepts ISO)
        parse_dt(data.get("analyzed_at")),
        # confidence_score may be null; cast to float or None
        (float(data.get("confidence_score")) if data.get("confidence_score") is not None else None),
        payload.get("pdf_path"),
        payload.get("json_path"),
        payload.get("md_path"),
        payload.get("raw_ai_output_path"),
        payload.get("parsing_error"),
        payload.get("validation_error"),
        json.dumps(payload.get("data") or {}),
    )

    # Execute and return the id
    record_id = await execute_query(query, params, return_value=True)
    logger.info(f"✅ Incident resolution stored for sys_id={payload.get('sys_id')}, record_id={record_id}")
    return record_id


async def fetch_incident_resolutions(
    limit: int = 100,
    offset: int = 0,
    sys_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    where_clause = ""
    params = []

    if sys_id:
        where_clause = "WHERE sys_id = $3"
        params = [limit, offset, sys_id]
    else:
        params = [limit, offset]

    query = f"""
        SELECT 
            id,
            success,
            sys_id,
            analysis_type,
            ai_model,
            usage,
            data_id,
            issue,
            issue_category,
            category,
            level,
            description,
            steps_to_resolve,
            technical_details,
            complete_description,
            analyzed_at,
            confidence_score,
            pdf_path,
            json_path,
            md_path,
            raw_ai_output_path,
            parsing_error,
            validation_error,
            created_at,
            updated_at,
            metadata
        FROM incident_resolution
        {where_clause}
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
    """

    async with get_db_connection() as conn:
        records = await conn.fetch(query, *params)
        return [dict(r) for r in records]
