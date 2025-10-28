"""Use case data models and database schema."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

# ---------- Pydantic models (request/response) ----------

class UseCaseCreateRequest(BaseModel):
    """Request model for submitting a new automation use case."""
    name: str = Field(..., description="Name of the automation use case")
    category: Optional[str] = Field(None, description="Category of the use case")
    git_url: Optional[str] = Field(None, description="Git repository URL for the project")
    git_branch: Optional[str] = Field("main", description="Git branch name")
    description: Optional[str] = Field(None, description="Detailed description of the use case")
    owner_email: Optional[str] = Field(None, description="Email address of the requester")


class UseCaseResponse(BaseModel):
    """Response model for use case details."""
    id: str
    name: str
    category: Optional[str]
    git_url: Optional[str]
    git_branch: Optional[str]
    aap_project_id: Optional[str]
    aap_template_id: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None


# ---------- Optional: Internal ORM-like structure (for reference) ----------

USECASE_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS usecases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    category TEXT,
    git_url TEXT,
    git_branch TEXT,
    aap_project_id TEXT,
    aap_template_id TEXT,
    description TEXT,
    owner_email TEXT,
    status TEXT DEFAULT 'pending',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
"""
