"""
Main Pydantic AI agent for agentic RAG with knowledge graph (safe fallback).
"""

import os
import re   # <-- Add this
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from dotenv import load_dotenv

from app.tools.tools import (
    vector_search_tool,
    hybrid_search_tool,
    get_document_tool,
    list_documents_tool,
    perform_comprehensive_search,
    VectorSearchInput,
    HybridSearchInput,
    DocumentInput,
    DocumentListInput
)
from app.prompts.ragprompts import SYSTEM_PROMPT
from app.services.providers import get_llm_model

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class AgentDependencies:
    """Dependencies for the agent."""
    session_id: str
    user_id: Optional[str] = None
    search_preferences: Dict[str, Any] = None

    def __post_init__(self):
        if self.search_preferences is None:
            self.search_preferences = {
                "use_vector": True,
                "use_graph": True,
                "default_limit": 10
            }


# Initialize the RAG agent
rag_agent = Agent(
    get_llm_model(),
    deps_type=AgentDependencies,
    system_prompt=SYSTEM_PROMPT
)


# -----------------------
# Agent Tools
# -----------------------

@rag_agent.tool
async def vector_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Perform vector similarity search."""
    try:
        return [
            {
                "content": r.content,
                "score": r.score,
                "document_title": r.document_title,
                "document_source": r.document_source,
                "chunk_id": r.chunk_id
            }
            for r in await vector_search_tool(VectorSearchInput(query=query, limit=limit))
        ]
    except Exception as e:
        logger.error(f"Vector search tool error: {e}")
        return []


@rag_agent.tool
async def hybrid_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    limit: int = 10,
    text_weight: float = 0.3
) -> List[Dict[str, Any]]:
    """Perform hybrid vector + keyword search."""
    try:
        return [
            {
                "content": r.content,
                "score": r.score,
                "document_title": r.document_title,
                "document_source": r.document_source,
                "chunk_id": r.chunk_id
            }
            for r in await hybrid_search_tool(HybridSearchInput(query=query, limit=limit, text_weight=text_weight))
        ]
    except Exception as e:
        logger.error(f"Hybrid search tool error: {e}")
        return []


@rag_agent.tool
async def get_document(
    ctx: RunContext[AgentDependencies],
    document_id: str
) -> Optional[Dict[str, Any]]:
    """Retrieve full document."""
    try:
        return await get_document_tool(DocumentInput(document_id=document_id))
    except Exception as e:
        logger.error(f"Get document tool error: {e}")
        return None


@rag_agent.tool
async def list_documents(
    ctx: RunContext[AgentDependencies],
    limit: int = 20,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """List available documents."""
    try:
        docs = await list_documents_tool(DocumentListInput(limit=limit, offset=offset))
        return [doc.dict() for doc in docs]
    except Exception as e:
        logger.error(f"List documents tool error: {e}")
        return []


@rag_agent.tool
async def comprehensive_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Perform vector + graph (if available) search safely.
    Uses perform_comprehensive_search internally.
    """
    try:
        deps = ctx.deps
        use_vector = deps.search_preferences.get("use_vector", True)
        use_graph = deps.search_preferences.get("use_graph", False)  # Graph may not be implemented
        return await perform_comprehensive_search(query=query, use_vector=use_vector, use_graph=use_graph, limit=limit)
    except Exception as e:
        logger.error(f"Comprehensive search tool error: {e}")
        return {
            "query": query,
            "vector_results": [],
            "graph_results": [],
            "total_results": 0
        }
