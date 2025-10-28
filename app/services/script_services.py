"""Script and Use Case Service Layer (complete version with auto table creation)."""

#script_services.py

import structlog
from datetime import datetime
from typing import Any, Dict, Optional

from app.utils.db_utils import initialize_database, close_database, db_pool

logger = structlog.get_logger(__name__)


class ScriptServices:
    """Handles use case and script persistence in Postgres."""

    def __init__(self):
        self._initialized = False

    # ------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------
    async def initialize(self) -> None:
        """Initialize database pool and auto-create tables if needed."""
        if self._initialized:
            return
        await initialize_database()
        await self._ensure_tables_exist()
        self._initialized = True
        logger.info("ScriptServices DB initialized")

    async def close(self) -> None:
        """Close DB pool cleanly."""
        if not self._initialized:
            return
        await close_database()
        self._initialized = False
        logger.info("ScriptServices DB closed")

    # ------------------------------------------------------------
    # Schema Setup (Auto Table Creation)
    # ------------------------------------------------------------
    async def _ensure_tables_exist(self) -> None:
        """Create required tables if they don't already exist."""
        ddl_statements = [
            """
            CREATE EXTENSION IF NOT EXISTS pgcrypto;
            """,
            """
            CREATE TABLE IF NOT EXISTS usecases (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                description TEXT,
                tech_comment TEXT,
                status TEXT DEFAULT 'submitted',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS scripts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                usecase_id UUID REFERENCES usecases(id) ON DELETE CASCADE,
                git_url TEXT,
                git_branch TEXT,
                ansible_project_id TEXT,
                ansible_template_id TEXT,
                steps_count INT DEFAULT 0,
                status TEXT DEFAULT 'completed',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """
        ]

        async with db_pool.acquire() as conn:
            async with conn.transaction():
                for ddl in ddl_statements:
                    try:
                        await conn.execute(ddl)
                    except Exception as e:
                        logger.error("Failed to execute DDL", ddl=ddl.strip(), error=str(e))
                        raise
        logger.info("Ensured required tables exist", tables=["usecases", "scripts"])

    # ------------------------------------------------------------
    # Use Case Operations
    # ------------------------------------------------------------
    async def insert_usecase(
        self, name: str, description: str, tech_comment: str
    ) -> str:
        """Insert a new use case record and return its UUID."""
        await self.initialize()
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                result = await conn.fetchrow(
                    """
                    INSERT INTO usecases (name, description, tech_comment, status, created_at)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id::text
                    """,
                    name,
                    description,
                    tech_comment,
                    "submitted",
                    datetime.utcnow(),
                )
                uid = result["id"]
                logger.info("Use case inserted", uid=uid, name=name)
                return uid

    async def get_usecase(self, uid: str) -> Optional[Dict[str, Any]]:
        """Fetch a use case by its UUID."""
        await self.initialize()
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT id::text, name, description, tech_comment, status, created_at
                FROM usecases
                WHERE id::text = $1
                """,
                uid,
            )
            if not result:
                logger.warning("Use case not found", uid=uid)
                return None
            logger.info("Use case fetched", uid=uid)
            return dict(result)

    # ------------------------------------------------------------
    # Script Record Operations
    # ------------------------------------------------------------
    async def insert_script_record(
        self,
        usecase_id: str,
        git_url: str,
        git_branch: str,
        ansible_project_id: Optional[str] = None,
        ansible_template_id: Optional[str] = None,
        steps_count: int = 0,
        status: str = "completed",
    ) -> str:
        """Insert a new script record and return its UUID."""
        await self.initialize()
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                result = await conn.fetchrow(
                    """
                    INSERT INTO scripts (
                        usecase_id, git_url, git_branch,
                        ansible_project_id, ansible_template_id,
                        steps_count, status, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id::text
                    """,
                    usecase_id,
                    git_url,
                    git_branch,
                    ansible_project_id,
                    ansible_template_id,
                    steps_count,
                    status,
                    datetime.utcnow(),
                )
                script_id = result["id"]
                logger.info(
                    "Script record inserted",
                    script_id=script_id,
                    usecase_id=usecase_id,
                    status=status,
                )
                return script_id
