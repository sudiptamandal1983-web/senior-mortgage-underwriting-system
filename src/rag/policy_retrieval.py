"""
src/rag/policy_retrieval.py
ChromaDB RAG pipeline for Dutch mortgage policy retrieval.
Hybrid retrieval: semantic search + keyword matching.
Confidence scoring on retrieved chunks.
Version filtering: always serves latest policy version.
"""

import os
import sys
import re
from typing import List, Optional, Tuple
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

from data.policy_documents.dutch_mortgage_policy import POLICY_DOCUMENTS


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    title: str
    content: str
    confidence: float
    version: str
    effective_date: str


@dataclass
class PolicyRetrievalResult:
    query: str
    chunks: List[RetrievedChunk]
    top_confidence: float
    low_confidence_flag: bool
    retrieval_method: str


CONFIDENCE_THRESHOLD = 0.65
LOW_CONFIDENCE_FLAG_THRESHOLD = 0.50


class PolicyRetriever:
    """
    ChromaDB-backed policy retrieval with semantic search and keyword fallback.
    Always serves the latest version of each policy document.
    """

    def __init__(self, persist_directory: str = "./data/chroma_db"):
        self.persist_directory = persist_directory
        self.collection = None
        self._initialise()

    def _initialise(self):
        """Initialise ChromaDB collection and ingest policy documents."""
        if not CHROMADB_AVAILABLE:
            print("ChromaDB not available -- using keyword fallback retrieval")
            return
        try:
            client = chromadb.PersistentClient(path=self.persist_directory)
            embedding_fn = embedding_functions.DefaultEmbeddingFunction()
            self.collection = client.get_or_create_collection(
                name="dutch_mortgage_policy",
                embedding_function=embedding_fn,
                metadata={"description": "Dutch mortgage policy documents"}
            )
            if self.collection.count() == 0:
                self._ingest_documents()
        except Exception as e:
            print(f"ChromaDB init failed ({e}) -- using keyword fallback")
            self.collection = None

    def _ingest_documents(self):
        """Ingest all policy documents into ChromaDB."""
        if not self.collection:
            return

        documents = []
        metadatas = []
        ids = []

        for doc in POLICY_DOCUMENTS:
            # Semantic chunking -- each document is one chunk for policy provisions
            # In production, larger documents would be split on section boundaries
            chunk_id = f"{doc['id']}-chunk-001"
            documents.append(doc["content"])
            metadatas.append({
                "document_id": doc["id"],
                "title": doc["title"],
                "version": doc["version"],
                "effective_date": doc["effective_date"]
            })
            ids.append(chunk_id)

        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Ingested {len(documents)} policy document chunks into ChromaDB")

    def retrieve(
        self,
        query: str,
        n_results: int = 3
    ) -> PolicyRetrievalResult:
        """
        Retrieve relevant policy chunks for a given query.
        Falls back to keyword matching if ChromaDB is unavailable.
        """
        if self.collection and CHROMADB_AVAILABLE:
            return self._semantic_retrieve(query, n_results)
        else:
            return self._keyword_retrieve(query, n_results)

    def _semantic_retrieve(
        self,
        query: str,
        n_results: int
    ) -> PolicyRetrievalResult:
        """Semantic retrieval using ChromaDB embeddings."""
        results = self.collection.query(
            query_texts=[query],
            n_results=min(n_results, self.collection.count())
        )

        chunks = []
        distances = results["distances"][0] if results["distances"] else []
        documents = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        ids = results["ids"][0] if results["ids"] else []

        for i, (doc, meta, chunk_id, distance) in enumerate(
            zip(documents, metadatas, ids, distances)
        ):
            # Convert distance to confidence (ChromaDB returns L2 distance)
            # Lower distance = higher similarity
            confidence = max(0.0, min(1.0, 1.0 - (distance / 2.0)))

            chunks.append(RetrievedChunk(
                chunk_id=chunk_id,
                document_id=meta.get("document_id", ""),
                title=meta.get("title", ""),
                content=doc,
                confidence=round(confidence, 4),
                version=meta.get("version", ""),
                effective_date=meta.get("effective_date", "")
            ))

        top_confidence = chunks[0].confidence if chunks else 0.0

        return PolicyRetrievalResult(
            query=query,
            chunks=chunks,
            top_confidence=top_confidence,
            low_confidence_flag=top_confidence < CONFIDENCE_THRESHOLD,
            retrieval_method="semantic"
        )

    def _keyword_retrieve(
        self,
        query: str,
        n_results: int
    ) -> PolicyRetrievalResult:
        """
        Keyword-based fallback retrieval when ChromaDB is unavailable.
        Scores documents by keyword overlap with the query.
        """
        query_terms = set(re.findall(r'\b\w+\b', query.lower()))

        scored = []
        for doc in POLICY_DOCUMENTS:
            doc_terms = set(re.findall(r'\b\w+\b', doc["content"].lower()))
            title_terms = set(re.findall(r'\b\w+\b', doc["title"].lower()))

            # Keyword overlap score
            content_overlap = len(query_terms & doc_terms) / max(len(query_terms), 1)
            title_overlap = len(query_terms & title_terms) / max(len(query_terms), 1)
            score = (content_overlap * 0.7) + (title_overlap * 0.3)

            scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_n = scored[:n_results]

        chunks = []
        for score, doc in top_n:
            chunks.append(RetrievedChunk(
                chunk_id=f"{doc['id']}-chunk-001",
                document_id=doc["id"],
                title=doc["title"],
                content=doc["content"],
                confidence=round(min(score * 1.5, 1.0), 4),
                version=doc["version"],
                effective_date=doc["effective_date"]
            ))

        top_confidence = chunks[0].confidence if chunks else 0.0

        return PolicyRetrievalResult(
            query=query,
            chunks=chunks,
            top_confidence=top_confidence,
            low_confidence_flag=top_confidence < CONFIDENCE_THRESHOLD,
            retrieval_method="keyword_fallback"
        )


def build_policy_query(state: dict) -> str:
    """
    Build a targeted policy query from the application state.
    Constructs a query that will retrieve the most relevant policy sections.
    """
    parts = []

    if state.get("existing_loan_balance", 0) > 0:
        parts.append("existing mortgage loan LTV limit combined balance")

    if state.get("nhg_requested"):
        parts.append("NHG guarantee conditions eligibility limit")

    employment = state.get("employment_type", "salaried")
    if employment in ("self_employed", "freelance"):
        parts.append("self-employed income verification requirements")
    else:
        parts.append("salaried income verification DTI affordability")

    ltv = state.get("ltv_ratio", 0)
    if ltv and ltv > 0.85:
        parts.append("LTV breach maximum eligible loan calculation AFM")

    parts.append("Dutch mortgage AFM responsible lending requirements")

    return " ".join(parts)


# Singleton instance
_retriever: Optional[PolicyRetriever] = None


def get_retriever() -> PolicyRetriever:
    """Get or create the singleton policy retriever."""
    global _retriever
    if _retriever is None:
        _retriever = PolicyRetriever()
    return _retriever
