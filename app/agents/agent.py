import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

from app.prompts.ragprompts import SYSTEM_PROMPT
from app.services.providers import get_llm_model
from app.tools.tools import (
    vector_search_tool,
    hybrid_search_tool,
    VectorSearchInput,
    HybridSearchInput,
    detect_domain_from_query
)

logger = logging.getLogger(__name__)

@dataclass
class AgentDependencies:
    session_id: str
    user_id: Optional[str] = None
    search_preferences: Dict[str, Any] = None

    def __post_init__(self):
        if self.search_preferences is None:
            self.search_preferences = {"use_vector": True, "use_graph": False, "default_limit": 10}

# Initialize the RAG agent
rag_agent = Agent(get_llm_model(), deps_type=AgentDependencies, system_prompt=SYSTEM_PROMPT)


# -----------------------
# KB Retrieval Tool
# -----------------------
@rag_agent.tool
async def retrieve_relevant_kb(ctx: RunContext[AgentDependencies], query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Domain-aware KB retrieval using hybrid + vector fallback.
    """
    domain = detect_domain_from_query(query)

    results = await hybrid_search_tool(HybridSearchInput(query=query, limit=limit, domain=domain))
    if not results:
        results = await vector_search_tool(VectorSearchInput(query=query, limit=limit, domain=domain))

    return [
        {
            "content": r.content,
            "document_title": r.document_title,
            "document_source": r.document_source,
            "chunk_id": r.chunk_id,
            "metadata": r.metadata
        }
        for r in results
    ]
