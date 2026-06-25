"""
src/agents/policy_agent.py
Policy agent — retrieves relevant Dutch mortgage policy using ChromaDB RAG.
Flags low-confidence retrieval for HITL escalation.
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.agents.state import UnderwritingState
from src.rag.policy_retrieval import get_retriever, build_policy_query


def policy_agent(state: UnderwritingState) -> UnderwritingState:
    """
    Retrieve relevant policy sections using ChromaDB RAG.
    Flags low-confidence retrieval — these cases require HITL review
    regardless of other signals.
    """
    retriever = get_retriever()
    query = build_policy_query(state)
    result = retriever.retrieve(query, n_results=3)

    # Extract policy chunk summaries for the audit trail
    chunk_summaries = [
        {
            "chunk_id": c.chunk_id,
            "title": c.title,
            "confidence": c.confidence,
            "version": c.version
        }
        for c in result.chunks
    ]

    # Top chunk content for downstream agents
    policy_chunks = [c.content for c in result.chunks]

    audit_entry = {
        "agent": "policy_agent",
        "timestamp": datetime.utcnow().isoformat(),
        "query": query,
        "retrieval_method": result.retrieval_method,
        "chunks_retrieved": len(result.chunks),
        "top_confidence": result.top_confidence,
        "low_confidence_flag": result.low_confidence_flag,
        "chunks": chunk_summaries
    }

    return {
        **state,
        "policy_chunks": policy_chunks,
        "policy_confidence": result.top_confidence,
        "audit_trail": [audit_entry]
    }
