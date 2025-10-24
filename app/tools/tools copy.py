"""
Tools for the Pydantic AI RAG agent.
"""


import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

from pydantic import BaseModel, Field
from dotenv import load_dotenv

from app.utils.db_utils import (
    vector_search,
    hybrid_search,
    get_document,
    list_documents,
    get_document_chunks
)
from app.models.rag import ChunkResult, DocumentMetadata
from app.services.providers import get_embedding_client, get_embedding_model

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)

# Initialize embedding client
embedding_client = get_embedding_client()
EMBEDDING_MODEL = get_embedding_model()


# -----------------------
# Embedding Generation
# -----------------------
async def generate_embedding(text: str) -> List[float]:
    try:
        response = await embedding_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        raise


# -----------------------
# Tool Input Models
# -----------------------
class VectorSearchInput(BaseModel):
    query: str
    limit: int = 10


class HybridSearchInput(BaseModel):
    query: str
    limit: int = 10
    text_weight: float = 0.3


class DocumentInput(BaseModel):
    document_id: str


class DocumentListInput(BaseModel):
    limit: int = 20
    offset: int = 0


# -----------------------
# Tool Implementations
# -----------------------
async def vector_search_tool(input_data: VectorSearchInput) -> List[ChunkResult]:
    try:
        embedding = await generate_embedding(input_data.query)
        results = await vector_search(embedding=embedding, limit=input_data.limit)
        return [
            ChunkResult(
                chunk_id=str(r["chunk_id"]),
                document_id=str(r["document_id"]),
                content=r["content"],
                score=r["similarity"],
                metadata=r.get("metadata", {}),
                document_title=r.get("document_title", ""),
                document_source=r.get("document_source", "")
            )
            for r in results
        ]
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return []


async def hybrid_search_tool(input_data: HybridSearchInput) -> List[ChunkResult]:
    try:
        embedding = await generate_embedding(input_data.query)
        results = await hybrid_search(
            embedding=embedding,
            query_text=input_data.query,
            limit=input_data.limit,
            text_weight=input_data.text_weight
        )
        return [
            ChunkResult(
                chunk_id=str(r["chunk_id"]),
                document_id=str(r["document_id"]),
                content=r["content"],
                score=r["combined_score"],
                metadata=r.get("metadata", {}),
                document_title=r.get("document_title", ""),
                document_source=r.get("document_source", "")
            )
            for r in results
        ]
    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        return []


async def get_document_tool(input_data: DocumentInput) -> Optional[Dict[str, Any]]:
    try:
        document = await get_document(input_data.document_id)
        if document:
            chunks = await get_document_chunks(input_data.document_id)
            document["chunks"] = chunks
        return document
    except Exception as e:
        logger.error(f"Document retrieval failed: {e}")
        return None


async def list_documents_tool(input_data: DocumentListInput) -> List[DocumentMetadata]:
    try:
        docs = await list_documents(limit=input_data.limit, offset=input_data.offset)
        return [
            DocumentMetadata(
                id=d["id"],
                title=d.get("title", ""),
                source=d.get("source", ""),
                metadata=d.get("metadata", {}),
                created_at=datetime.fromisoformat(d["created_at"]),
                updated_at=datetime.fromisoformat(d["updated_at"]),
                chunk_count=d.get("chunk_count", 0)
            )
            for d in docs
        ]
    except Exception as e:
        logger.error(f"Document listing failed: {e}")
        return []


# -----------------------
# Safe Graph Search Fallback
# -----------------------
async def graph_search_tool(query: str) -> List[Dict[str, Any]]:
    """
    Placeholder for graph search. Returns empty list if not implemented.
    """
    logger.warning("Graph search tool not implemented, returning empty results.")
    return []


# -----------------------
# Combined Search Utility
# -----------------------
async def perform_comprehensive_search(
    query: str,
    use_vector: bool = True,
    use_graph: bool = True,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Perform vector + graph searches safely.
    """
    results = {
        "query": query,
        "vector_results": [],
        "graph_results": [],
        "total_results": 0
    }

    tasks = []

    if use_vector:
        tasks.append(vector_search_tool(VectorSearchInput(query=query, limit=limit)))
    if use_graph:
        tasks.append(graph_search_tool(query=query))

    if tasks:
        search_results = await asyncio.gather(*tasks, return_exceptions=True)
        if use_vector:
            if not isinstance(search_results[0], Exception):
                results["vector_results"] = search_results[0]
        if use_graph:
            idx = 1 if use_vector else 0
            if not isinstance(search_results[idx], Exception):
                results["graph_results"] = search_results[idx]

    results["total_results"] = len(results["vector_results"]) + len(results["graph_results"])
    return results
