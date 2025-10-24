"""
chunker.py

Semantic + simple chunker rewritten to be robust and compatible with multi-domain embedding.
DocumentChunk includes `embedding_map` (namespace -> vector) and preserves `embedding` for backward compatibility.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class ChunkingConfig:
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_chunk_size: int = 2000
    min_chunk_size: int = 100
    use_semantic_splitting: bool = True
    preserve_structure: bool = True

    def __post_init__(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        if self.min_chunk_size <= 0:
            raise ValueError("min_chunk_size must be positive")


@dataclass
class DocumentChunk:
    content: str
    index: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    token_count: Optional[int] = None

    # Embedding compatibility
    embedding: Optional[List[float]] = None                  # legacy single vector
    embedding_map: Dict[str, List[float]] = field(default_factory=dict)  # namespace -> vector

    def __post_init__(self):
        if self.token_count is None:
            # rough estimate: 4 characters ~ 1 token
            self.token_count = max(1, len(self.content) // 4)


class BaseChunker:
    def __init__(self, config: ChunkingConfig, llm_split_fn: Optional[Callable] = None):
        """
        llm_split_fn: optional async function (text, target_size, max_size) -> List[str].
        If provided, it's used to split long sections semantically.
        """
        self.config = config
        self.llm_split_fn = llm_split_fn

    async def chunk_document(self, content: str, title: str, source: str, metadata: Optional[Dict[str, Any]] = None) -> List[DocumentChunk]:
        raise NotImplementedError


class SemanticChunker(BaseChunker):
    """
    Semantic chunker: uses structural heuristics + optional LLM for splitting very long sections.
    Falls back to simple splitting when necessary.
    """

    def __init__(self, config: ChunkingConfig, llm_split_fn: Optional[Callable] = None):
        super().__init__(config, llm_split_fn)

    async def chunk_document(self, content: str, title: str, source: str, metadata: Optional[Dict[str, Any]] = None) -> List[DocumentChunk]:
        if not content or not content.strip():
            return []

        base_meta = {
            "title": title,
            "source": source,
            **(metadata or {})
        }

        # If content is small, return single chunk
        if len(content) <= self.config.chunk_size:
            return self._to_chunk_objects([content], content, base_meta)

        # Split by structure
        sections = self._split_on_structure(content)

        chunks_texts: List[str] = []
        current = ""

        for sec in sections:
            sec = sec.strip()
            if not sec:
                continue

            candidate = (current + "\n\n" + sec).strip() if current else sec

            if len(candidate) <= self.config.chunk_size:
                current = candidate
                continue

            # Candidate too big — flush current if exists
            if current:
                chunks_texts.append(current.strip())
                current = ""

            # Now deal with sec (which may be very large)
            if len(sec) > self.config.max_chunk_size:
                # Try LLM split if available, otherwise simple split
                if self.llm_split_fn:
                    try:
                        sub_chunks = await self.llm_split_fn(sec, self.config.chunk_size, self.config.max_chunk_size)
                    except Exception as e:
                        logger.warning("LLM splitting failed: %s. Falling back to simple split.", e)
                        sub_chunks = self._simple_split(sec)
                else:
                    sub_chunks = self._simple_split(sec)

                for sc in sub_chunks:
                    if len(sc.strip()) >= self.config.min_chunk_size:
                        chunks_texts.append(sc.strip())
            else:
                # fits within max chunk size — use as chunk
                chunks_texts.append(sec)

        if current:
            chunks_texts.append(current.strip())

        # Filter tiny chunks
        chunks_texts = [c for c in chunks_texts if len(c.strip()) >= self.config.min_chunk_size]

        if not chunks_texts:
            chunks_texts = self._simple_split(content)

        return self._to_chunk_objects(chunks_texts, content, base_meta)

    def _split_on_structure(self, content: str) -> List[str]:
        # Split on markdown headers, code fences, paragraphs, lists, and tables heuristically
        patterns = [
            r'^\s*#{1,6}\s+.*$',     # markdown headers
            r'^```.*?^```',           # code fences (multiline)
            r'\n\s*\n',               # paragraph breaks
            r'^[\-\*\+]\s+.*$',       # bullet list items
            r'^\d+\.\s+.*$',          # numbered lists
        ]

        sections = [content]
        for pat in patterns:
            new_sections: List[str] = []
            for s in sections:
                parts = re.split(f'({pat})', s, flags=re.MULTILINE | re.DOTALL)
                parts = [p for p in parts if p and p.strip()]
                new_sections.extend(parts)
            sections = new_sections
        return sections

    def _simple_split(self, text: str) -> List[str]:
        texts: List[str] = []
        start = 0
        L = len(text)

        while start < L:
            end = min(L, start + self.config.chunk_size)
            if end == L:
                texts.append(text[start:end])
                break

            # Try to backtrack to sentence boundary within a reasonable window
            cut = None
            back_limit = max(start + self.config.min_chunk_size, end - 200)
            for i in range(end, back_limit - 1, -1):
                if text[i - 1] in ".!?\n":
                    cut = i
                    break
            if not cut:
                cut = end

            texts.append(text[start:cut])
            start = max(0, cut - self.config.chunk_overlap)

        return texts

    def _to_chunk_objects(self, chunks_texts: List[str], original_content: str, base_meta: Dict[str, Any]) -> List[DocumentChunk]:
        out: List[DocumentChunk] = []
        current_pos = 0
        total = len(chunks_texts)

        for idx, chunk_text in enumerate(chunks_texts):
            # Best-effort position
            start = original_content.find(chunk_text, current_pos)
            if start == -1:
                start = current_pos
            end = start + len(chunk_text)
            meta = {**base_meta, "chunk_method": "semantic", "total_chunks": total}
            dc = DocumentChunk(
                content=chunk_text.strip(),
                index=idx,
                start_char=start,
                end_char=end,
                metadata=meta
            )
            out.append(dc)
            current_pos = end

        return out


class SimpleChunker(BaseChunker):
    def __init__(self, config: ChunkingConfig, llm_split_fn: Optional[Callable] = None):
        super().__init__(config, llm_split_fn)

    async def chunk_document(self, content: str, title: str, source: str, metadata: Optional[Dict[str, Any]] = None) -> List[DocumentChunk]:
        if not content or not content.strip():
            return []

        base_meta = {
            "title": title,
            "source": source,
            "chunk_method": "simple",
            **(metadata or {})
        }

        paragraphs = re.split(r'\n\s*\n', content)
        texts: List[str] = []
        current = ""

        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            candidate = (current + "\n\n" + p).strip() if current else p
            if len(candidate) <= self.config.chunk_size:
                current = candidate
                continue
            if current:
                texts.append(current)
            current = p

        if current:
            texts.append(current)

        if not texts:
            # fallback sliding window
            texts = [content[i:i + self.config.chunk_size] for i in range(0, len(content), self.config.chunk_size)]

        out: List[DocumentChunk] = []
        cur_pos = 0
        total = len(texts)
        for idx, txt in enumerate(texts):
            start = content.find(txt, cur_pos)
            if start == -1:
                start = cur_pos
            end = start + len(txt)
            meta = {**base_meta, "total_chunks": total}
            out.append(DocumentChunk(content=txt.strip(), index=idx, start_char=start, end_char=end, metadata=meta))
            cur_pos = end

        return out


def create_chunker(config: ChunkingConfig, use_semantic: Optional[bool] = None, llm_split_fn: Optional[Callable] = None):
    """
    Factory to create chunker. Defaults to semantic if config.use_semantic_splitting is True.
    """
    cfg = config
    use_sem = cfg.use_semantic_splitting if use_semantic is None else use_semantic
    if use_sem:
        return SemanticChunker(cfg, llm_split_fn=llm_split_fn)
    return SimpleChunker(cfg, llm_split_fn=llm_split_fn)
