"""
ingest.py

Main ingestion pipeline integrating:
 - dynamic domain (namespace) discovery from subfolders under knowledge-base
 - file discovery for markdown (.md/.markdown/.txt), csv (.csv) and pdf (.pdf)
 - chunking (semantic/simple), multi-domain embeddings, and persistence to Postgres (chunks + vectors)
"""

import os
import asyncio
import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import argparse

from dotenv import load_dotenv

# Asyncpg (DB connection pool)
try:
    from app.utils.db_utils import initialize_database, close_database, db_pool
    from app.models.rag import IngestionConfig, IngestionResult
    from app.services.providers import get_text_extractor  # optional provider for PDFs etc.
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.utils.db_utils import initialize_database, close_database, db_pool
    from app.models.rag import IngestionConfig, IngestionResult

# Local modules
from .chunker import ChunkingConfig, create_chunker, DocumentChunk
from .embedder import create_embedder

# Optional dependencies
try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    import pandas as pd
except Exception:
    pd = None

load_dotenv()
logger = logging.getLogger(__name__)


class DocumentIngestionPipeline:
    def __init__(
        self,
        config: IngestionConfig,
        documents_folder: str = "knowledge-base",
        clean_before_ingest: bool = False,
        explicit_domains: Optional[List[str]] = None
    ):
        self.config = config
        self.documents_folder = documents_folder
        self.clean_before_ingest = clean_before_ingest
        self.explicit_domains = explicit_domains

        # chunker config
        self.chunker_config = ChunkingConfig(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            max_chunk_size=getattr(config, "max_chunk_size", 2000),
            min_chunk_size=getattr(config, "min_chunk_size", 100),
            use_semantic_splitting=config.use_semantic_chunking
        )

        llm_split_fn = getattr(config, "llm_split_fn", None)
        self.chunker = create_chunker(self.chunker_config, use_semantic=None, llm_split_fn=llm_split_fn)

        self.domains = self._discover_domains()
        logger.info("Discovered domains: %s", self.domains)

        domain_model_map = getattr(config, "domain_model_map", None) or {}
        embed_fn_factory = getattr(config, "embed_fn_factory", None)
        embedding_dim = getattr(config, "embedding_dim", None)
        batch_size = getattr(config, "embedding_batch_size", 100)
        self.embedder = create_embedder(domains=self.domains, model_map=domain_model_map, embed_fn_factory=embed_fn_factory, dim=embedding_dim, batch_size=batch_size)

        self._initialized = False

    def _discover_domains(self) -> List[str]:
        """
        Discover domains dynamically from subfolders:
        e.g., knowledge-base/middleware/auth -> domain: middleware/auth
        """
        if self.explicit_domains:
            return sorted(self.explicit_domains)

        base_path = Path(self.documents_folder)
        if not base_path.exists():
            return ["global"]

        domains = []
        for main_cat in ["middleware", "network", "database"]:
            cat_path = base_path / main_cat
            if cat_path.exists() and cat_path.is_dir():
                subdirs = [d.name for d in cat_path.iterdir() if d.is_dir()]
                if subdirs:
                    for sub in subdirs:
                        domains.append(f"{main_cat}/{sub}")
                else:
                    domains.append(main_cat)

        if not domains:
            return ["global"]
        return sorted(domains)

    def _extract_domain_from_path(self, file_path: str) -> str:
        """
        Map file path to domain for vector storage:
        knowledge-base/middleware/auth/file.md -> domain: middleware/auth
        """
        try:
            p = Path(file_path).resolve()
            base = Path(self.documents_folder).resolve()
            rel = p.relative_to(base)
            parts = rel.parts
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}"
            elif len(parts) == 1:
                return parts[0]
            else:
                return "global"
        except Exception:
            return "global"

    async def initialize(self):
        if self._initialized:
            return
        logger.info("Initializing pipeline (DB)...")
        await initialize_database()
        self._initialized = True
        logger.info("Initialization complete")

    async def close(self):
        if not self._initialized:
            return
        await close_database()
        self._initialized = False

    def _find_files(self) -> List[str]:
        patterns = ["**/*.md", "**/*.markdown", "**/*.txt", "**/*.csv", "**/*.pdf"]
        files: List[str] = []
        for pat in patterns:
            files.extend(sorted([str(p) for p in Path(self.documents_folder).glob(pat)]))
        return sorted(files)

    def _read_document(self, file_path: str) -> str:
        ext = file_path.lower().split(".")[-1]
        try:
            if ext in {"md", "markdown", "txt"}:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            elif ext == "csv":
                if pd is None:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        return f.read()
                else:
                    try:
                        df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
                        lines = [" | ".join(map(str, row.tolist())) for _, row in df.iterrows()]
                        return "\n".join(lines)
                    except Exception as e:
                        logger.warning("CSV parse failed %s: %s", file_path, e)
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            return f.read()
            elif ext == "pdf":
                if pdfplumber is None:
                    logger.warning("pdfplumber not installed; returning empty text for PDF %s", file_path)
                    return ""
                try:
                    text_parts = []
                    with pdfplumber.open(file_path) as pdf:
                        for page in pdf.pages:
                            page_text = page.extract_text() or ""
                            if page_text:
                                text_parts.append(page_text)
                    return "\n\n".join(text_parts)
                except Exception as e:
                    logger.warning("PDF parse failed %s: %s", file_path, e)
                    return ""
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="latin-1", errors="ignore") as f:
                return f.read()
        except FileNotFoundError:
            logger.error("File not found: %s", file_path)
            return ""
        except Exception as e:
            logger.exception("Unexpected error reading file %s: %s", file_path, e)
            return ""

    def _extract_title(self, content: str, file_path: str) -> str:
        for line in content.splitlines()[:10]:
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return os.path.splitext(os.path.basename(file_path))[0]

    def _extract_document_metadata(self, content: str, file_path: str) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "file_path": file_path,
            "file_size": len(content),
            "ingestion_date": datetime.now(timezone.utc).isoformat(),
            "line_count": len(content.splitlines()),
            "word_count": len(content.split())
        }
        if content.startswith("---"):
            try:
                import yaml
                end_marker = content.find("\n---\n", 4)
                if end_marker != -1:
                    frontmatter = content[4:end_marker]
                    yaml_metadata = yaml.safe_load(frontmatter)
                    if isinstance(yaml_metadata, dict):
                        metadata.update(yaml_metadata)
            except Exception:
                pass
        return metadata

    async def ingest_documents(self, progress_callback: Optional[callable] = None) -> List[IngestionResult]:
        if not self._initialized:
            await self.initialize()

        if self.clean_before_ingest:
            await self._clean_databases()

        files = self._find_files()
        if not files:
            logger.warning("No files found under %s", self.documents_folder)
            return []

        logger.info("Found %d files to process", len(files))

        results: List[IngestionResult] = []
        for i, file_path in enumerate(files):
            try:
                logger.info("Processing file %d/%d: %s", i + 1, len(files), file_path)
                res = await self._ingest_single_document(file_path)
                results.append(res)
                if progress_callback:
                    progress_callback(i + 1, len(files))
            except Exception as e:
                logger.exception("Failed processing %s: %s", file_path, e)
                results.append(IngestionResult(
                    document_id="",
                    title=os.path.basename(file_path),
                    chunks_created=0,
                    entities_extracted=0,
                    relationships_created=0,
                    processing_time_ms=0.0,
                    errors=[str(e)]
                ))

        total_chunks = sum(r.chunks_created for r in results)
        total_errors = sum(len(r.errors) for r in results)
        logger.info("Ingestion complete: %d files, %d chunks, %d errors", len(results), total_chunks, total_errors)
        return results

    async def _ingest_single_document(self, file_path: str) -> IngestionResult:
        start = datetime.now(timezone.utc)
        content = self._read_document(file_path)
        title = self._extract_title(content, file_path)
        domain = self._extract_domain_from_path(file_path)
        doc_meta = self._extract_document_metadata(content, file_path)
        source = os.path.relpath(file_path, self.documents_folder)

        logger.info("Ingesting document '%s' (domain=%s)", title, domain)

        chunks = await self.chunker.chunk_document(content=content, title=title, source=source, metadata=doc_meta)
        if not chunks:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000.0
            logger.warning("No chunks created for %s", file_path)
            return IngestionResult(document_id="", title=title, chunks_created=0, entities_extracted=0, relationships_created=0, processing_time_ms=elapsed, errors=["No chunks created"])

        logger.info("Created %d chunks for %s", len(chunks), file_path)

        try:
            def _progress_cb(domain, processed, total):
                logger.debug("Embedding progress domain=%s: %d/%d", domain, processed, total)
            chunks = await self.embedder.embed_chunks(chunks, progress_callback=_progress_cb)
            logger.info("Embeddings generated for %d chunks", len(chunks))
        except Exception as e:
            logger.exception("Embedding stage failed for %s: %s", file_path, e)
            for ch in chunks:
                ch.metadata["embedding_error"] = str(e)

        try:
            document_id = await self._save_to_postgres(title, source, content, chunks, doc_meta, domain)
            logger.info("Saved document %s with id %s", title, document_id)
        except Exception as e:
            logger.exception("Failed to persist document %s: %s", file_path, e)
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000.0
            return IngestionResult(document_id="", title=title, chunks_created=len(chunks), entities_extracted=0, relationships_created=0, processing_time_ms=elapsed, errors=[str(e)])

        elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000.0
        return IngestionResult(document_id=document_id, title=title, chunks_created=len(chunks), entities_extracted=0, relationships_created=0, processing_time_ms=elapsed, errors=[])

    async def _save_to_postgres(self, title: str, source: str, content: str, chunks: List[DocumentChunk], metadata: Dict[str, Any], domain: str) -> str:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                doc_row = await conn.fetchrow(
                    """
                    INSERT INTO documents (title, source, content, metadata)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id::text
                    """,
                    title, source, content, json.dumps(metadata)
                )
                document_id = doc_row["id"]

                for ch in chunks:
                    chunk_row = await conn.fetchrow(
                        """
                        INSERT INTO chunks (document_id, content, chunk_index, metadata, token_count)
                        VALUES ($1::uuid, $2, $3, $4, $5)
                        RETURNING id::text
                        """,
                        document_id, ch.content, ch.index, json.dumps(ch.metadata), ch.token_count
                    )
                    chunk_id = chunk_row["id"]

                    emap: Dict[str, Any] = getattr(ch, "embedding_map", {}) or {}
                    if emap:
                        for namespace, vec in emap.items():
                            if not vec:
                                continue
                            vec_str = "[" + ",".join(map(str, vec)) + "]"
                            model_name = None
                            if getattr(self.config, "domain_model_map", None):
                                model_name = self.config.domain_model_map.get(namespace)
                            await conn.execute(
                                """
                                INSERT INTO vectors (chunk_id, namespace, model, embedding, metadata)
                                VALUES ($1::uuid, $2, $3, $4::vector, $5::jsonb)
                                """,
                                chunk_id, namespace, model_name, vec_str, json.dumps({"source": source})
                            )
                    else:
                        if getattr(ch, "embedding", None):
                            vec_str = "[" + ",".join(map(str, ch.embedding)) + "]"
                            await conn.execute(
                                """
                                INSERT INTO vectors (chunk_id, namespace, model, embedding, metadata)
                                VALUES ($1::uuid, $2, $3, $4::vector, $5::jsonb)
                                """,
                                chunk_id, domain, None, vec_str, json.dumps({"source": source})
                            )

                return document_id

    async def _clean_databases(self):
        logger.warning("Cleaning existing data from Postgres (messages, sessions, vectors, chunks, documents)")
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM messages")
                await conn.execute("DELETE FROM sessions")
                await conn.execute("DELETE FROM vectors")
                await conn.execute("DELETE FROM chunks")
                await conn.execute("DELETE FROM documents")
        logger.info("Databases cleaned")


async def main():
    parser = argparse.ArgumentParser(description="Ingest documents into vector DB")
    parser.add_argument("--documents", "-d", default="knowledge-base", help="Documents folder path")
    parser.add_argument("--clean", "-c", action="store_true", help="Clean existing data before ingestion")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Chunk size for splitting documents")
    parser.add_argument("--chunk-overlap", type=int, default=200, help="Chunk overlap size")
    parser.add_argument("--no-semantic", action="store_true", help="Disable semantic chunking")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--domains", nargs="*", help="Optional explicit domains (overrides auto-discovery)")

    args = parser.parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    config = IngestionConfig(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        use_semantic_chunking=not args.no_semantic,
        extract_entities=False,
        skip_graph_building=True
    )

    pipeline = DocumentIngestionPipeline(
        config=config,
        documents_folder=args.documents,
        clean_before_ingest=args.clean,
        explicit_domains=args.domains
    )

    def progress_callback(current: int, total: int):
        print(f"Progress: {current}/{total} files processed")

    try:
        start = datetime.now(timezone.utc)
        results = await pipeline.ingest_documents(progress_callback)
        end = datetime.now(timezone.utc)
        total_time = (end - start).total_seconds()

        print("\n" + "=" * 50)
        print("INGESTION SUMMARY")
        print("=" * 50)
        print(f"Files processed: {len(results)}")
        print(f"Total chunks created: {sum(r.chunks_created for r in results)}")
        print(f"Total errors: {sum(len(r.errors) for r in results)}")
        print(f"Total processing time: {total_time:.2f} seconds\n")

        for r in results:
            status = "✓" if not r.errors else "✗"
            print(f"{status} {r.title}: {r.chunks_created} chunks")
            if r.errors:
                for err in r.errors:
                    print(f"  Error: {err}")

    except KeyboardInterrupt:
        print("\nIngestion interrupted by user")
    except Exception as e:
        logger.exception("Ingestion failed: %s", e)
        raise
    finally:
        await pipeline.close()


if __name__ == "__main__":
    asyncio.run(main())
