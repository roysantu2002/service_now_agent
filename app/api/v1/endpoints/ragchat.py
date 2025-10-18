"""
RAG Chat endpoints with lazy dependency injection and structured responses.
"""

import logging
from datetime import datetime
from typing import Optional, List
import uuid

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse

from app.models.rag import (
    ChatRequest,
    ChatResponse,
    SearchRequest,
    SearchResponse,
    HealthStatus,
    ToolCall
)

logger = logging.getLogger(__name__)
router = APIRouter()


# -------------------------
# Lazy dependency
# -------------------------
def get_rag_agent(provider: Optional[str] = Query(None)):
    """
    Lazily import the RAG agent to avoid circular dependencies.
    Optionally allow switching AI provider at runtime.
    """
    from app.agents.agent import rag_agent, AgentDependencies
    return {"rag_agent": rag_agent, "AgentDependencies": AgentDependencies}


# -------------------------
# Health Check
# -------------------------
@router.get("/health", response_model=HealthStatus)
async def health_check(agent=Depends(get_rag_agent)):
    """Health check endpoint."""
    try:
        return HealthStatus(
            status="healthy",
            database=True,
            graph_database=True,
            llm_connection=True,
            version="0.1.0",
            timestamp=datetime.now()
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    
# # -------------------------
# # Chat endpoint
# # -------------------------
# @router.post("/chat", response_model=ChatResponse)
# async def chat_endpoint(
#     request: ChatRequest,
#     agent=Depends(get_rag_agent)
# ):
#     """Non-streaming chat endpoint."""
#     import uuid

#     try:
#         rag_agent = agent["rag_agent"]
#         AgentDependencies = agent["AgentDependencies"]

#         session_id = request.session_id or str(uuid.uuid4())
#         deps = AgentDependencies(session_id=session_id, user_id=request.user_id)

#         # Run the agent
#         result = await rag_agent.run(request.message, deps=deps)

#         # --- Extract only the text output ---
#         if hasattr(result, "output"):
#             response_text = str(result.output)
#         elif hasattr(result, "data") and hasattr(result.data, "output"):
#             response_text = str(result.data.output)
#         else:
#             response_text = str(result)

#         # Tools used (empty list for now)
#         tools_used: List[ToolCall] = []

#         return ChatResponse(
#             message=response_text,
#             session_id=session_id,
#             tools_used=tools_used,
#             metadata={"search_type": str(request.search_type)}
#         )

#     except Exception as e:
#         logger.error(f"Chat endpoint failed: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail=f"Chat endpoint error: {str(e)}")

# @router.post("/chat", response_model=ChatResponse)
# async def chat_endpoint(
#     request: ChatRequest,
#     agent=Depends(get_rag_agent)
# ):
#     """Non-streaming chat endpoint with correct message formatting and tools_used."""
#     try:
#         rag_agent = agent["rag_agent"]
#         AgentDependencies = agent["AgentDependencies"]

#         session_id = request.session_id or str(uuid.uuid4())
#         deps = AgentDependencies(session_id=session_id, user_id=request.user_id)

#         # Run the agent
#         result = await rag_agent.run(request.message, deps=deps)

#         # Extract just the output string (instead of str(result))
#         if hasattr(result, "output"):
#             response_text = result.output
#         elif hasattr(result, "data"):
#             response_text = result.data
#         else:
#             response_text = str(result)

#         # Extract tools used if available
#         tools_used: List[ToolCall] = getattr(result, "tools_used", [])
#         if tools_used:
#             tools_used = [
#                 ToolCall(
#                     name=t.name,
#                     input=t.input,
#                     output=t.output
#                 ) if not isinstance(t, ToolCall) else t
#                 for t in tools_used
#             ]

#         return ChatResponse(
#             message=response_text,
#             session_id=session_id,
#             tools_used=tools_used,
#             metadata={"search_type": str(request.search_type)}
#         )

#     except Exception as e:
#         logger.error(f"Chat endpoint failed: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    agent=Depends(get_rag_agent)
):
    """Non-streaming chat endpoint with proper tools_used extraction."""
    try:
        rag_agent = agent["rag_agent"]
        AgentDependencies = agent["AgentDependencies"]

        session_id = request.session_id or str(uuid.uuid4())
        deps = AgentDependencies(session_id=session_id, user_id=request.user_id)

        # Run the agent
        result = await rag_agent.run(request.message, deps=deps)

        # Extract assistant text
        if hasattr(result, "output"):
            response_text = result.output
        elif hasattr(result, "data"):
            response_text = result.data
        else:
            response_text = str(result)

        # --- Extract tools used properly ---
        tools_used: List[ToolCall] = []
        try:
            messages = result.all_messages()
            for msg in messages:
                if hasattr(msg, "parts"):
                    for part in msg.parts:
                        if part.__class__.__name__ == "ToolCallPart":
                            tool_name = getattr(part, "tool_name", "unknown")
                            tool_call_id = getattr(part, "tool_call_id", None)
                            tool_args = {}
                            if hasattr(part, "args") and part.args is not None:
                                import json
                                if isinstance(part.args, str):
                                    try:
                                        tool_args = json.loads(part.args)
                                    except json.JSONDecodeError:
                                        tool_args = {}
                                elif isinstance(part.args, dict):
                                    tool_args = part.args
                            # Fallback to args_as_dict
                            if hasattr(part, "args_as_dict"):
                                try:
                                    tool_args = part.args_as_dict()
                                except Exception:
                                    pass
                            tools_used.append(ToolCall(
                                tool_name=tool_name,
                                args=tool_args,
                                tool_call_id=tool_call_id
                            ))
        except Exception as e:
            logger.warning(f"Failed to extract tools_used: {e}")

        return ChatResponse(
            message=response_text,
            session_id=session_id,
            tools_used=tools_used,
            metadata={"search_type": str(request.search_type)}
        )

    except Exception as e:
        logger.error(f"Chat endpoint failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Streaming Chat
# -------------------------
@router.post("/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    agent=Depends(get_rag_agent)
):
    """Streaming chat endpoint."""
    try:
        rag_agent = agent["rag_agent"]
        AgentDependencies = agent["AgentDependencies"]

        session_id = request.session_id or str(uuid.uuid4())
        deps = AgentDependencies(session_id=session_id, user_id=request.user_id)

        async def generate_stream():
            try:
                yield f"data: {JSONResponse({'type': 'session', 'session_id': session_id}).body.decode()}\n\n"
                async with rag_agent.iter(request.message, deps=deps) as run:
                    async for node in run:
                        content = getattr(node, "content", "")
                        if content:
                            yield f"data: {JSONResponse({'type': 'text', 'content': content}).body.decode()}\n\n"
                yield f"data: {JSONResponse({'type': 'end'}).body.decode()}\n\n"
            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield f"data: {JSONResponse({'type': 'error', 'content': str(e)}).body.decode()}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )

    except Exception as e:
        logger.error(f"Streaming chat endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Search Endpoints
# -------------------------
@router.post("/search/vector", response_model=SearchResponse)
async def vector_search_endpoint(request: SearchRequest, agent=Depends(get_rag_agent)):
    """Vector search endpoint."""
    try:
        from app.tools.tools import vector_search_tool, VectorSearchInput
        input_data = VectorSearchInput(query=request.query, limit=request.limit)
        results = await vector_search_tool(input_data)
        return SearchResponse(results=results, total_results=len(results), search_type="vector", query_time_ms=0)
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/graph", response_model=SearchResponse)
async def graph_search_endpoint(request: SearchRequest, agent=Depends(get_rag_agent)):
    """Graph search endpoint (safe fallback)."""
    try:
        try:
            from app.tools.tools import graph_search_tool, GraphSearchInput
        except ImportError:
            # Safe dummy if graph not implemented
            async def graph_search_tool(*args, **kwargs):
                return []

        input_data = GraphSearchInput(query=request.query) if "GraphSearchInput" in locals() else None
        results = await graph_search_tool(input_data) if input_data else []
        return SearchResponse(graph_results=results, total_results=len(results), search_type="graph", query_time_ms=0)
    except Exception as e:
        logger.error(f"Graph search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/hybrid", response_model=SearchResponse)
async def hybrid_search_endpoint(request: SearchRequest, agent=Depends(get_rag_agent)):
    """Hybrid search endpoint."""
    try:
        from app.tools.tools import hybrid_search_tool, HybridSearchInput
        input_data = HybridSearchInput(query=request.query, limit=request.limit)
        results = await hybrid_search_tool(input_data)
        return SearchResponse(results=results, total_results=len(results), search_type="hybrid", query_time_ms=0)
    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Documents endpoint
# -------------------------
@router.get("/documents")
async def list_documents_endpoint(limit: int = 20, offset: int = 0, agent=Depends(get_rag_agent)):
    """List documents endpoint."""
    try:
        from app.tools.tools import list_documents_tool, DocumentListInput
        input_data = DocumentListInput(limit=limit, offset=offset)
        documents = await list_documents_tool(input_data)
        return {"documents": documents, "total": len(documents), "limit": limit, "offset": offset}
    except Exception as e:
        logger.error(f"Document listing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Session endpoint
# -------------------------
@router.get("/sessions/{session_id}")
async def get_session_endpoint(session_id: str, agent=Depends(get_rag_agent)):
    """Get session info."""
    try:
        from app.utils.db_utils import get_session
        session = await get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
    except Exception as e:
        logger.error(f"Session retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Debug print for routes
# -------------------------
logger.info(f"[DEBUG] Final RAGChat router routes count: {len(router.routes)}")
for r in router.routes:
    logger.info(f"[DEBUG] Route: {r.path} -> {r.methods}")
