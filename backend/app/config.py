"""
RAG Configuration — all tunable parameters in one place.
Change these without touching any other file.
"""
from dataclasses import dataclass, field


@dataclass
class ChunkConfig:
    # Target size in words (≈ 500–800 tokens)
    size: int = 600
    # Overlap in words (≈ 100–150 tokens)
    overlap: int = 120
    # Never split a table — kept as one chunk regardless of size
    preserve_tables: bool = True


@dataclass
class EmbeddingConfig:
    model: str = "BAAI/bge-small-en-v1.5"
    vector_dim: int = 384
    # Cache embeddings to avoid recomputing same text
    cache_enabled: bool = True


@dataclass
class RetrievalConfig:
    # How many chunks to fetch before reranking
    initial_fetch: int = 20
    # How many chunks to send to LLM after reranking
    final_top_k: int = 5
    # Hybrid search weights — must sum to 1.0
    vector_weight: float = 0.7
    bm25_weight: float = 0.3
    # Minimum score to consider a chunk relevant (0.0 to 1.0)
    min_relevance_threshold: float = 0.3
    # Minimum chunks needed to give a confident answer
    min_supporting_chunks: int = 1


@dataclass
class RerankerConfig:
    model: str = "BAAI/bge-reranker-v2-m3"
    enabled: bool = True
    # Chunks below this reranker score are dropped
    score_threshold: float = 0.1


@dataclass
class ConfidenceConfig:
    # Score ranges for labels
    high_threshold: float = 0.80
    medium_threshold: float = 0.55
    # Below medium = Low confidence


@dataclass
class RAGConfig:
    chunking: ChunkConfig = None
    embedding: EmbeddingConfig = None
    retrieval: RetrievalConfig = None
    reranker: RerankerConfig = field(default_factory=RerankerConfig)
    confidence: ConfidenceConfig = None

    def __post_init__(self):
        if self.chunking is None:
            self.chunking = ChunkConfig()
        if self.embedding is None:
            self.embedding = EmbeddingConfig()
        if self.retrieval is None:
            self.retrieval = RetrievalConfig()
        if self.reranker is None:
            self.reranker = RerankerConfig()
        if self.confidence is None:
            self.confidence = ConfidenceConfig()


# Single global config instance — import this everywhere
config = RAGConfig()
