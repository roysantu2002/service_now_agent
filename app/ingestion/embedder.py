"""
embedder.py

Multi-namespace embedding generator.

- create_embedder(domains, model_map, embed_fn_factory, dim) -> MultiEmbedder
- MultiEmbedder.embed_chunks(chunks) will batch-embed all chunks per domain and attach chunk.embedding_map
- Backwards-compatible: chunk.embedding gets set to the first domain's embedding (if any)
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable

from datetime import datetime

logger = logging.getLogger(__name__)

# Import provider helpers (flexible)
try:
    from app.services.providers import get_embedding_client, get_embedding_model
except Exception:
    # fallback in case of direct execution or testing
    def get_embedding_client():
        raise RuntimeError("app.services.providers.get_embedding_client not available")

    def get_embedding_model():
        return "default-embed-model"


# Wrapper to call the provider (default uses agent.providers)
# embed_fn_factory(domain, model) -> async function(texts) -> list[list[float]]
def default_embed_fn_factory(domain: str, model: str) -> Callable[[List[str]], List[List[float]]]:
    """
    Default factory uses embedding client from agent.providers. This assumes the embedding client
    supports an async `embeddings.create(model=..., input=[...])` interface similar to OpenAI's Python client.
    Adjust if your provider API differs.
    """
    embedding_client = get_embedding_client()
    model_name = model or get_embedding_model()

    async def embed_fn(texts: List[str]) -> List[List[float]]:
        # Basic input sanitation & truncation is recommended in the provider.
        # We call provider in batches; provider should accept list of texts.
        if not texts:
            return []

        # Ensure we don't accidentally pass huge entries
        processed = []
        for t in texts:
            if t is None:
                processed.append("")
            else:
                processed.append(t)

        # Call provider (assumes async compat)
        # Response object shape may vary by provider; this matches OpenAI-style response.data[*].embedding
        try:
            resp = await embedding_client.embeddings.create(model=model_name, input=processed)
            # resp.data is expected to be a list with .embedding
            embeddings = [item.embedding for item in resp.data]
            return embeddings
        except Exception as e:
            logger.exception("Embedding provider call failed for model %s: %s", model_name, e)
            # Return zero vectors as a safe fallback if provider fails (length unknown) — better to raise
            # but we prefer to return nulls so ingestion continues; callers should handle None entries.
            return [None] * len(processed)

    return embed_fn


class DomainEmbedder:
    def __init__(self, domain: str, model: str, embed_fn: Callable[[List[str]], List[List[float]]], dim: Optional[int] = None):
        self.domain = domain
        self.model = model
        self._embed_fn = embed_fn
        self.dim = dim

    async def embed_texts(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Returns list of embedding vectors or None when embedding failed.
        """
        # Ensure embed_fn is awaited properly
        return await self._embed_fn(texts)


class MultiEmbedder:
    def __init__(self, domain_embedders: List[DomainEmbedder], dim: Optional[int] = None, batch_size: int = 100):
        self.domain_embedders = domain_embedders
        self.dim = dim
        self.batch_size = batch_size

    async def embed_chunks(self, chunks: List[Any], progress_callback: Optional[Callable] = None) -> List[Any]:
        """
        Given list of DocumentChunk, compute embeddings per domain in batches and attach to chunk.embedding_map.
        Process is:
          - For each domain: in batches, embed all chunk contents, attach result to chunk.embedding_map[domain]
        """
        if not chunks:
            return chunks

        texts = [c.content for c in chunks]

        # For each domain, embed all texts in batches
        for de in self.domain_embedders:
            domain = de.domain
            model = de.model
            embed_fn = de._embed_fn
            domain_embeddings: List[Optional[List[float]]] = []

            logger.info("Embedding domain '%s' with model '%s' for %d chunks", domain, model, len(texts))

            # embed in batches to avoid provider limits
            for i in range(0, len(texts), self.batch_size):
                batch_texts = texts[i:i + self.batch_size]
                try:
                    embs = await embed_fn(batch_texts)
                    # If embed_fn returns fewer embeddings, pad with None
                    if embs is None:
                        embs = [None] * len(batch_texts)
                    domain_embeddings.extend(embs)
                except Exception as e:
                    logger.exception("Embedding failure for domain %s batch %d: %s", domain, i // self.batch_size, e)
                    # On failure, append Nones for that batch
                    domain_embeddings.extend([None] * len(batch_texts))

                if progress_callback:
                    progress_callback(domain, min(len(domain_embeddings), len(texts)), len(texts))

            # Attach embeddings to chunks
            for idx, chunk in enumerate(chunks):
                vec = domain_embeddings[idx] if idx < len(domain_embeddings) else None
                if vec:
                    if not hasattr(chunk, "embedding_map") or chunk.embedding_map is None:
                        chunk.embedding_map = {}
                    chunk.embedding_map[domain] = vec

        # Set legacy embedding to first domain if available
        if self.domain_embedders:
            first_domain = self.domain_embedders[0].domain
            for chunk in chunks:
                if getattr(chunk, "embedding_map", None) and first_domain in chunk.embedding_map:
                    chunk.embedding = chunk.embedding_map[first_domain]

        return chunks


def create_embedder(
    domains: Optional[List[str]] = None,
    model_map: Optional[Dict[str, str]] = None,
    embed_fn_factory: Optional[Callable[[str, str], Callable]] = None,
    dim: Optional[int] = None,
    batch_size: int = 100
) -> MultiEmbedder:
    """
    Create a multi-domain embedder.

    Args:
        domains: list of namespace strings (e.g. ['middleware','network'])
                 If None or empty, the returned MultiEmbedder will have no domain embedders and must be re-created/configured later.
        model_map: optional mapping domain -> model_name
        embed_fn_factory: optional function(domain, model) -> async embed_fn(texts)->list[vec]
                          If not provided, a default factory (using agent.providers) is used.
        dim: expected embedding dimension (optional)
        batch_size: provider batch size
    """
    model_map = model_map or {}
    embed_fn_factory = embed_fn_factory or default_embed_fn_factory
    domain_embedders: List[DomainEmbedder] = []

    if domains:
        for d in domains:
            model = model_map.get(d) or model_map.get("default") or None
            embed_fn = embed_fn_factory(d, model)
            domain_embedders.append(DomainEmbedder(d, model, embed_fn, dim=dim))

    return MultiEmbedder(domain_embedders, dim=dim, batch_size=batch_size)
