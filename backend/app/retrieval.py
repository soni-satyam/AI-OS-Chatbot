"""
Hybrid Retrieval

WHY dense-only retrieval fails:
- "What is Article 21?" → BGE-M3 might return chunks about "rights" generally
  instead of the exact Article 21 chunk, because semantically similar ≠ exact match

WHY BM25 alone fails:
- "What protects citizens from arbitrary arrest?" → BM25 needs exact words like
  "arbitrary arrest" to score high. BGE-M3 understands the meaning.

WHY hybrid is better:
- Vector search finds semantically relevant chunks
- BM25 finds exact keyword matches
- Combined: best of both worlds

Final score = 0.7 * vector_score + 0.3 * bm25_score
"""
from typing import List, Dict, Tuple
from rank_bm25 import BM25Okapi
import numpy as np
import logging
from backend.app.config import config

log = logging.getLogger(__name__)


class BM25Index:
    """
    Keyword search index using BM25 algorithm.
    BM25 is what search engines used before neural embeddings.
    It scores documents by term frequency and inverse document frequency.
    """
    def __init__(self):
        self.index: BM25Okapi = None
        self.session_chunks: Dict[str, List[dict]] = {}  # session_id → chunks
        self._all_chunks: List[dict] = []  # flat list for indexing

    def add_chunks(self, chunks: List[dict], session_id: str):
        """Add chunks from a new PDF to the BM25 index."""
        self.session_chunks[session_id] = chunks
        self._rebuild_index()
        log.info(f"BM25 index rebuilt — {len(self._all_chunks)} total chunks across {len(self.session_chunks)} sessions")

    def remove_session(self, session_id: str):
        """Remove all chunks for a PDF (when user deletes it)."""
        if session_id in self.session_chunks:
            del self.session_chunks[session_id]
            self._rebuild_index()
            log.info(f"BM25: removed session {session_id}, rebuilt index")

    def _rebuild_index(self):
        """Rebuild index from all current chunks."""
        self._all_chunks = []
        for chunks in self.session_chunks.values():
            self._all_chunks.extend(chunks)

        if not self._all_chunks:
            self.index = None
            return

        # Tokenize: lowercase, split on whitespace
        tokenized = [c["text"].lower().split() for c in self._all_chunks]
        self.index = BM25Okapi(tokenized)

    def search(self, query: str, session_ids: List[str], top_k: int = 20) -> List[Tuple[dict, float]]:
        """
        Search by keywords, filter to active sessions.
        Returns list of (chunk, normalized_score).
        """
        if not self.index or not self._all_chunks:
            return []

        # Get BM25 scores for all chunks
        tokens = query.lower().split()
        scores = self.index.get_scores(tokens)

        # Normalize to 0-1 range
        max_score = max(scores) if max(scores) > 0 else 1.0
        normalized = scores / max_score

        # Filter to active sessions and sort
        active_session_set = set(session_ids)
        results = []
        for i, chunk in enumerate(self._all_chunks):
            if chunk.get("session_id") in active_session_set:
                results.append((chunk, float(normalized[i])))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


def hybrid_search(
    query_vector: List[float],
    query: str,
    session_ids: List[str],
    qdrant_client,
    bm25_index: BM25Index,
    top_k: int = 20,
) -> List[dict]:
    """
    Combine dense vector search and BM25 keyword search.

    Steps:
    1. Run both searches independently (top_k each)
    2. Normalize scores to same scale (0-1)
    3. Combine: final = 0.7*vector + 0.3*bm25
    4. Sort by final score, return top_k
    """
    cfg = config.retrieval
    COLLECTION = "pdf_chunks"

    from qdrant_client.models import Filter, FieldCondition, MatchValue

    # --- Dense retrieval ---
    vector_results = qdrant_client.search(
        collection_name=COLLECTION,
        query_vector=query_vector,
        query_filter=Filter(
            should=[
                FieldCondition(key="session_id", match=MatchValue(value=sid))
                for sid in session_ids
            ]
        ),
        limit=top_k,
        with_payload=True,
    )

    # Build dict: chunk_id → (payload, vector_score)
    vector_map: Dict[str, Tuple[dict, float]] = {}
    for r in vector_results:
        chunk_id = r.payload.get("chunk_id", r.payload.get("chunk_index", str(r.id)))
        vector_map[str(chunk_id)] = (r.payload, r.score)

    # --- BM25 keyword retrieval ---
    bm25_results = bm25_index.search(query, session_ids, top_k=top_k)

    bm25_map: Dict[str, Tuple[dict, float]] = {}
    for chunk, score in bm25_results:
        chunk_id = chunk.get("chunk_id", chunk.get("chunk_index", ""))
        bm25_map[str(chunk_id)] = (chunk, score)

    # --- Merge scores ---
    all_ids = set(vector_map.keys()) | set(bm25_map.keys())
    merged = []

    for cid in all_ids:
        v_payload, v_score = vector_map.get(cid, (None, 0.0))
        b_payload, b_score = bm25_map.get(cid, (None, 0.0))

        payload = v_payload or b_payload
        if not payload:
            continue

        # Apply threshold — skip irrelevant chunks
        if v_score < cfg.min_relevance_threshold and b_score < cfg.min_relevance_threshold:
            continue

        final_score = cfg.vector_weight * v_score + cfg.bm25_weight * b_score

        merged.append({
            **payload,
            "vector_score": v_score,
            "bm25_score": b_score,
            "hybrid_score": final_score,
        })

    merged.sort(key=lambda x: x["hybrid_score"], reverse=True)

    log.info(f"Hybrid search: {len(vector_results)} vector + {len(bm25_results)} BM25 → {len(merged)} merged")
    return merged[:top_k]
