"""
Reranker + Confidence Scoring

WHY reranking:
Retrieval returns top-20 chunks by similarity.
But similarity ≠ relevance. A chunk can be close in vector space
but not actually answer the question.

Reranker (cross-encoder) reads BOTH the query AND the chunk together
and scores "does this chunk answer this question?" — much more accurate.

Pipeline:
Query + 20 chunks → Reranker → scored → top 5 → LLM

WHY cross-encoders are more accurate than bi-encoders:
Bi-encoder (BGE-M3): encodes query and chunk SEPARATELY → fast but less accurate
Cross-encoder (bge-reranker): encodes query+chunk TOGETHER → slower but more accurate
We use bi-encoder for speed (20 chunks from millions) and cross-encoder for accuracy (5 from 20).
"""
from typing import List, Tuple
from sentence_transformers import CrossEncoder
import logging
from app.config import config

log = logging.getLogger(__name__)


class RerankerService:
    def __init__(self):
        cfg = config.reranker
        if cfg.enabled:
            log.info(f"Loading reranker model: {cfg.model}...")
            self.model = CrossEncoder(cfg.model)
            log.info("Reranker loaded.")
        else:
            self.model = None
            log.info("Reranker disabled in config.")

    def rerank(self, query: str, chunks: List[dict]) -> List[dict]:
        """
        Rerank chunks by relevance to query.
        Returns chunks sorted by reranker score, filtered by threshold.
        """
        cfg = config.reranker

        if not self.model or not chunks:
            return chunks

        log.info(f"Reranking {len(chunks)} chunks...")

        # Create (query, chunk_text) pairs for the cross-encoder
        pairs = [(query, c["text"]) for c in chunks]
        scores = self.model.predict(pairs)

        # Attach reranker scores
        for chunk, score in zip(chunks, scores):
            chunk["reranker_score"] = float(score)

        # Filter by threshold and sort
        filtered = [c for c in chunks if c["reranker_score"] >= cfg.score_threshold]
        filtered.sort(key=lambda x: x["reranker_score"], reverse=True)

        final = filtered[:config.retrieval.final_top_k]

        log.info(f"Reranking: {len(chunks)} → {len(filtered)} above threshold → top {len(final)} selected")
        for i, c in enumerate(final):
            log.info(f"  [{i}] reranker={c['reranker_score']:.4f} | file='{c.get('filename','?')}' p.{c.get('page_number','?')}")

        return final


def compute_confidence(chunks: List[dict]) -> Tuple[str, float]:
    """
    Compute confidence score from retrieval signals.

    Formula:
    - Average hybrid score (0-1): how relevant are chunks
    - Reranker score bonus: if reranker ran, use those scores
    - Supporting chunk count bonus: more chunks = more confident

    Returns (label, score_0_to_1)
    Example: ("High", 0.92)
    """
    cfg = config.confidence

    if not chunks:
        return ("None", 0.0)

    # Primary signal: reranker scores if available, else hybrid scores
    if "reranker_score" in chunks[0]:
        # Reranker scores are logits, normalize with sigmoid-like mapping
        import math
        raw_scores = [c["reranker_score"] for c in chunks]
        # Convert to 0-1 using sigmoid
        norm_scores = [1 / (1 + math.exp(-s)) for s in raw_scores]
    else:
        norm_scores = [c.get("hybrid_score", c.get("vector_score", 0.0)) for c in chunks]

    avg_score = sum(norm_scores) / len(norm_scores)

    # Boost for having multiple supporting chunks
    count_boost = min(len(chunks) / config.retrieval.final_top_k, 1.0) * 0.1
    final_score = min(avg_score + count_boost, 1.0)

    if final_score >= cfg.high_threshold:
        label = "High"
    elif final_score >= cfg.medium_threshold:
        label = "Medium"
    else:
        label = "Low"

    return (label, round(final_score, 4))
