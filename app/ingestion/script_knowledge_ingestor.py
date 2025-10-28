# knowledge_ingestor.py

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List

from langchain_community.document_loaders import PyMuPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, AzureOpenAIEmbeddings

from app.utils.db_utils import initialize_database, close_database, db_pool
from app.services.connectors.generic_ai_connector import AIConnectorFactory

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")


class KnowledgeIngestor:
    def __init__(self, provider_name: str = "azure", kb_path: str = "kb"):
        self.kb_path = Path(kb_path)
        self.provider_name = provider_name
        self.ai_service = AIConnectorFactory.get_connector(provider_name)
        self.embeddings = None
        self._initialized = False

    async def initialize(self):
        """Initialize DB and AI embeddings."""
        if self._initialized:
            return

        logger.info("[Init] Initializing database and AI embeddings...")
        await initialize_database()

        if self.provider_name == "azure":
            self.embeddings = AzureOpenAIEmbeddings(
                azure_deployment=os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "craftbot-dev-embed"),
                model=os.getenv("AZURE_EMBED_MODEL", "text-embedding-ada-002"),
                openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            )
        else:
            self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

        self._initialized = True
        logger.info("[Init] KnowledgeIngestor initialized successfully.")

    async def close(self):
        if self._initialized:
            await close_database()
            self._initialized = False
            logger.info("[Close] Database connection closed.")

    async def ingest_all_pdfs(self, domain: str = "default"):
        """Load and process all PDFs inside the KB folder."""
        if not self._initialized:
            await self.initialize()

        pdf_files = list(self.kb_path.glob("*.pdf"))
        if not pdf_files:
            logger.warning(f"No PDF files found in {self.kb_path}")
            return

        for pdf_file in pdf_files:
            logger.info(f"Processing: {pdf_file.name}")
            await self._process_pdf(pdf_file, domain)

    async def _process_pdf(self, pdf_path: Path, domain: str):
        """Extract, split, embed, and store a single PDF."""
        loader = PyMuPDFLoader(str(pdf_path))
        documents = loader.load()

        # Combine text
        text = "\n".join([doc.page_content for doc in documents])

        # Split into chunks
        splitter = RecursiveCharacterTextSplitter(
            separators=["\n"],
            chunk_size=500,
            chunk_overlap=50,
        )
        chunks = splitter.split_text(text)
        logger.info(f"Split {pdf_path.name} into {len(chunks)} chunks.")

        # Embed chunks
        embeddings = self.embeddings.embed_documents(chunks)
        logger.info(f"Generated {len(embeddings)} embeddings for {pdf_path.name}")

        # Save to Postgres
        await self._save_to_postgres(pdf_path.stem, str(pdf_path), text, chunks, embeddings, domain)

    async def _save_to_postgres(
        self,
        title: str,
        source: str,
        content: str,
        chunks: List[str],
        embeddings: List[List[float]],
        domain: str,
    ):
        """Persist document, chunks, and vectors in Postgres."""
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                doc_row = await conn.fetchrow(
                    """
                    INSERT INTO documents (title, source, content, metadata)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id::text
                    """,
                    title, source, content, json.dumps({"domain": domain})
                )
                document_id = doc_row["id"]

                for i, (chunk_text, vector) in enumerate(zip(chunks, embeddings)):
                    chunk_row = await conn.fetchrow(
                        """
                        INSERT INTO chunks (document_id, content, chunk_index, metadata, token_count)
                        VALUES ($1::uuid, $2, $3, $4, $5)
                        RETURNING id::text
                        """,
                        document_id, chunk_text, i, json.dumps({"domain": domain}), len(chunk_text.split())
                    )
                    chunk_id = chunk_row["id"]

                    vec_str = "[" + ",".join(map(str, vector)) + "]"
                    await conn.execute(
                        """
                        INSERT INTO vectors (chunk_id, namespace, model, embedding, metadata)
                        VALUES ($1::uuid, $2, $3, $4::vector, $5::jsonb)
                        """,
                        chunk_id, domain, "text-embedding-ada-002", vec_str, json.dumps({"source": source})
                    )

                logger.info(f"Saved document '{title}' (ID: {document_id}) to Postgres.")


# Example usage
if __name__ == "__main__":
    async def main():
        ingestor = KnowledgeIngestor(provider_name="azure", kb_path="kb")
        await ingestor.initialize()
        await ingestor.ingest_all_pdfs(domain="knowledge-base")
        await ingestor.close()

    asyncio.run(main())
