import re
from dataclasses import dataclass
from typing import List, Dict

import bs4
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_community.document_loaders import WebBaseLoader
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import PromptTemplate

from .log_parser import LogEntry  # Your log model

@dataclass
class KnowledgeBaseEntry:
    id: str
    error_pattern: str
    category: str
    solution: str
    prevention: str
    severity: str
    tags: List[str]
    created_at: str
    updated_at: str

@dataclass
class SearchResult:
    entry: LogEntry
    similarity_score: float
    match_type: str
    context: str

class LangChainRAG:
    def __init__(self, persist_dir="vector_store", model_name="gpt-4o-mini"):
        self.embeddings = OpenAIEmbeddings()
        self.vectorstore = Chroma(
            collection_name="log_entries",
            embedding_function=self.embeddings,
            persist_directory=persist_dir
        )
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
        self.llm_model_name = model_name
        print(f"[LangChainRAG] Initialized with model: {model_name}")

    def index_log_entries(self, entries: List[LogEntry]):
        docs = [
            {"page_content": f"{e.level} {e.category} {e.message}",
             "metadata": {
                 "timestamp": e.timestamp,
                 "level": e.level,
                 "category": e.category,
                 "severity_score": e.severity_score,
                 "source": e.source,
                 "line_number": e.line_number
             }}
            for e in entries
        ]
        self.vectorstore.add_documents(docs)
        self.vectorstore.persist()
        print(f"[LangChainRAG] Indexed {len(entries)} log entries.")

    def add_knowledge_entry(self, entry: KnowledgeBaseEntry):
        text = f"{entry.error_pattern} {entry.category} {entry.solution} {' '.join(entry.tags)}"
        metadata = {
            "id": entry.id,
            "category": entry.category,
            "severity": entry.severity,
            "tags": entry.tags,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at
        }
        self.vectorstore.add_documents([{"page_content": text, "metadata": metadata}])
        self.vectorstore.persist()
        print(f"[LangChainRAG] Added KB entry: {entry.id}")

    # Semantic / keyword / pattern / hybrid search
    def semantic_search(self, query: str) -> List[SearchResult]:
        docs = self.retriever.get_relevant_documents(query)
        return [
            SearchResult(
                entry=LogEntry(
                    timestamp=d["metadata"].get("timestamp", ""),
                    level=d["metadata"].get("level", ""),
                    message=d["page_content"],
                    source=d["metadata"].get("source", ""),
                    line_number=d["metadata"].get("line_number", 0),
                    raw_line=d["page_content"],
                    category=d["metadata"].get("category", ""),
                    severity_score=d["metadata"].get("severity_score", 0),
                ),
                similarity_score=1.0,
                match_type="semantic",
                context=d["page_content"]
            ) for d in docs
        ]

    def keyword_search(self, query: str, entries: List[LogEntry]) -> List[SearchResult]:
        results = []
        query_lower = query.lower()
        for e in entries:
            score = 0
            if query_lower in e.message.lower(): score += 0.6
            if query_lower in e.level.lower(): score += 0.3
            if query_lower in e.category.lower(): score += 0.4
            if score > 0:
                results.append(SearchResult(e, score, "keyword", e.message))
        return sorted(results, key=lambda x: x.similarity_score, reverse=True)

    def pattern_search(self, pattern: str, entries: List[LogEntry]) -> List[SearchResult]:
        try: regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e: 
            print(f"[LangChainRAG] Invalid regex: {e}"); return []

        results = []
        for e in entries:
            score = 0
            if regex.search(e.message): score += 0.8
            if regex.search(e.level): score += 0.3
            if regex.search(e.category): score += 0.4
            if score > 0:
                results.append(SearchResult(e, score, "pattern", e.message))
        return sorted(results, key=lambda x: x.similarity_score, reverse=True)

    def hybrid_search(self, query: str, entries: List[LogEntry]):
        results = self.semantic_search(query) + self.keyword_search(query, entries)
        return sorted(results, key=lambda x: x.similarity_score, reverse=True)[:5]

    # AI Suggestions without hub
    def get_ai_suggestions(self, query: str) -> str:
        llm = ChatOpenAI(model_name=self.llm_model_name, temperature=0)

        # Manual RAG prompt template
        prompt = PromptTemplate(
            input_variables=["context", "question"],
            template=(
                "Answer the question based on the context below.\n"
                "Context:\n{context}\n"
                "Question:\n{question}\n"
                "Answer concisely in 3 sentences max."
            )
        )

        def format_docs(docs):
            return "\n\n".join(d["page_content"] for d in docs)

        rag_chain = (
            {"context": self.retriever | format_docs, "question": RunnablePassthrough()} 
            | prompt
            | llm
            | StrOutputParser()
        )

        return rag_chain.invoke(query)

    # Web QA helpers
    @staticmethod
    def load_web_documents(urls: List[str]):
        loader = WebBaseLoader(web_paths=urls)
        docs = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        return splitter.split_documents(docs)

    @staticmethod
    def build_web_rag_chain(documents, llm_model="gpt-3.5-turbo"):
        vectorstore = Chroma.from_documents(documents, embedding=OpenAIEmbeddings())
        retriever = vectorstore.as_retriever()
        llm = ChatOpenAI(model_name=llm_model, temperature=0)

        def format_docs(docs):
            return "\n\n".join(doc["page_content"] for doc in docs)

        return (
            {"context": retriever | format_docs, "question": RunnablePassthrough()} 
            | PromptTemplate(
                input_variables=["context","question"],
                template="Answer concisely based on context:\n{context}\nQuestion: {question}"
              )
            | llm
            | StrOutputParser()
        )
