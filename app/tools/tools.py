"""
Tools for the Pydantic AI RAG agent with domain-aware search.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

from pydantic import BaseModel
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
# Input Models
# -----------------------
class VectorSearchInput(BaseModel):
    query: str
    limit: int = 10
    domain: Optional[str] = None


class HybridSearchInput(BaseModel):
    query: str
    limit: int = 10
    text_weight: float = 0.3
    domain: Optional[str] = None


class DocumentInput(BaseModel):
    document_id: str


class DocumentListInput(BaseModel):
    limit: int = 20
    offset: int = 0


# -----------------------
# Domain-aware Search Tools
# -----------------------
async def vector_search_tool(input_data: VectorSearchInput) -> List[ChunkResult]:
    try:
        embedding = await generate_embedding(input_data.query)
        results = await vector_search(
            embedding=embedding,
            limit=input_data.limit,
            domain=input_data.domain
        )
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
            text_weight=input_data.text_weight,
            domain=input_data.domain
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
# Domain Detection Helper
# -----------------------
def detect_domain_from_query(query: str) -> str:
    q = query.lower()
    if any(k in q for k in ["integration", "service error", "middleware", "auth"]):
        return "middleware"
    elif any(k in q for k in ["latency", "dns", "packet loss", "network", "firewall", "osi"]):
        return "network"
    elif any(k in q for k in ["query timeout", "replication", "database", "db", "sql"]):
        return "database"
    return "general"
