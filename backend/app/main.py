"""
Production RAG Chatbot Backend

Architecture:
Upload:  PDF → parse (pdfplumber) → smart chunk → embed (BGE) → store (Qdrant + BM25)
Query:   question → expand → hybrid search (vector + BM25) → rerank → confidence → LLM
Answer:  grounded response + citations + follow-up questions + confidence score
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
import os, json, tempfile, uuid, time, hashlib
from groq import AsyncGroq
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue
)
from sentence_transformers import SentenceTransformer

from auth.database import Base, engine
from auth.router import router as auth_router
from auth.dependencies import get_current_user
from auth.models import User

# Create tables on startup (in production use Alembic migrations instead)
Base.metadata.create_all(bind=engine)


import logging

from app.config import config
from app.parser import parse_pdf
from app.chunker import smart_chunk, Chunk
from app.retrieval import BM25Index, hybrid_search
from app.reranker import RerankerService, compute_confidence
from app.query_utils import expand_query, generate_followup_questions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

load_dotenv()

# ── App ───────────────────────────────────────────────────────
app = FastAPI(title="Production RAG Chatbot")

# Register the auth router — all routes will be at /auth/signup, /auth/login, etc.
app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Clients & Models ──────────────────────────────────────────
groq_client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

qdrant = QdrantClient(":memory:")
COLLECTION = "pdf_chunks"

log.info(f"Loading embedding model: {config.embedding.model}...")
embedder = SentenceTransformer(config.embedding.model)
log.info("Embedding model loaded.")

reranker = RerankerService()

bm25_index = BM25Index()

# Embedding cache: text_hash → vector
embedding_cache: Dict[str, List[float]] = {}

# Multi-PDF sessions
pdf_sessions: Dict[str, dict] = {}

# Conversation memory: session → last retrieved chunks
conversation_context: Dict[str, dict] = {}


# ── Collection ────────────────────────────────────────────────
def ensure_collection():
    collections = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION not in collections:
        qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(
                size=config.embedding.vector_dim,
                distance=Distance.COSINE
            ),
        )
        log.info(f"Qdrant collection '{COLLECTION}' created")

ensure_collection()


# ── Embedding with cache ──────────────────────────────────────
def get_embedding(text: str) -> List[float]:
    """
    Embed text with cache.
    WHY: Same chunk text never needs re-embedding — saves time on re-uploads.
    """
    if config.embedding.cache_enabled:
        key = hashlib.md5(text.encode()).hexdigest()
        if key in embedding_cache:
            return embedding_cache[key]

    vector = embedder.encode(
        f"passage: {text}",
        normalize_embeddings=True
    ).tolist()

    if config.embedding.cache_enabled:
        embedding_cache[key] = vector

    return vector


def embed_chunks(chunks: List[Chunk], filename: str, session_id: str):
    """Embed all chunks and store in Qdrant + BM25."""
    log.info(f"Embedding {len(chunks)} chunks for '{filename}'...")
    start = time.time()

    # Batch embed for speed
    texts = [f"passage: {c.text}" for c in chunks]
    vectors = embedder.encode(texts, show_progress_bar=True, normalize_embeddings=True)

    log.info(f"Embedding done in {time.time() - start:.2f}s")

    points = []
    bm25_docs = []

    for i, chunk in enumerate(chunks):
        payload = {
            "text": chunk.text,
            "chunk_id": chunk.chunk_id,
            "chunk_index": chunk.chunk_index,
            "filename": chunk.filename,
            "session_id": session_id,
            "page_number": chunk.page_number,
            "section_title": chunk.section_title,
            "is_table": chunk.is_table,
            "word_count": chunk.word_count,
        }

        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=vectors[i].tolist(),
            payload=payload,
        ))
        bm25_docs.append(payload)

    qdrant.upsert(collection_name=COLLECTION, points=points)
    bm25_index.add_chunks(bm25_docs, session_id)

    log.info(f"Stored {len(points)} vectors — session: {session_id}")


# ── Models ────────────────────────────────────────────────────
class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    conversation_id: Optional[str] = None


# ── PDF Endpoints ─────────────────────────────────────────────
@app.post("/api/pdf/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files supported")

    for s in pdf_sessions.values():
        if s["filename"] == file.filename:
            raise HTTPException(status_code=409, detail=f"'{file.filename}' already uploaded")

    contents = await file.read()
    log.info(f"Upload received: '{file.filename}' ({len(contents)/1024:.1f} KB)")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        # Step 1: Smart parse
        doc = parse_pdf(tmp_path, file.filename)
    finally:
        os.unlink(tmp_path)

    if not doc.blocks:
        raise HTTPException(status_code=422, detail="Could not extract text from PDF")

    # Step 2: Smart chunk
    chunks = smart_chunk(doc)
    if not chunks:
        raise HTTPException(status_code=422, detail="Chunking produced no results")

    # Step 3: Embed + store
    session_id = str(uuid.uuid4())
    ensure_collection()
    embed_chunks(chunks, file.filename, session_id)

    pdf_sessions[session_id] = {
        "filename": file.filename,
        "session_id": session_id,
        "total_chunks": len(chunks),
        "total_pages": doc.total_pages,
        "total_blocks": len(doc.blocks),
    }

    log.info(f"'{file.filename}' ready — {len(pdf_sessions)} PDF(s) loaded")

    return {
        "session_id": session_id,
        "filename": file.filename,
        "total_chunks": len(chunks),
        "total_pages": doc.total_pages,
    }


@app.delete("/api/pdf/remove/{session_id}")
async def remove_pdf(session_id: str):
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    filename = pdf_sessions[session_id]["filename"]

    qdrant.delete(
        collection_name=COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="session_id", match=MatchValue(value=session_id))]
        ),
    )
    bm25_index.remove_session(session_id)
    del pdf_sessions[session_id]

    log.info(f"Removed '{filename}' — {len(pdf_sessions)} remaining")
    return {"status": "removed", "filename": filename}


@app.delete("/api/pdf/clear")
async def clear_all():
    count = len(pdf_sessions)
    pdf_sessions.clear()
    qdrant.delete_collection(COLLECTION)
    ensure_collection()
    bm25_index.session_chunks.clear()
    bm25_index._all_chunks.clear()
    bm25_index.index = None
    log.info(f"Cleared all {count} PDFs")
    return {"status": "cleared", "removed": count}


@app.get("/api/pdf/list")
async def list_pdfs():
    return {"total": len(pdf_sessions), "pdfs": list(pdf_sessions.values())}


# ── Chat ──────────────────────────────────────────────────────
RAG_SYSTEM_PROMPT = """You are a precise document analysis assistant.

STRICT RULES:
1. Answer ONLY using the provided document excerpts below.
2. ALWAYS cite your sources: mention the document name and page number.
3. For tables, preserve the data accurately.
4. If multiple documents contain relevant information, synthesize and cite all of them.


FORMAT:
- Answer the question directly
- End with: Sources: [filename] (Page X), [filename] (Page Y)
- Confidence will be added separately
"""


async def stream_rag_response(messages: List[Message], context_chunks: List[dict],
                               query: str, conversation_id: str):
    """
    Stream response with citations and follow-up questions.
    """
    filenames = list({c.get("filename", "") for c in context_chunks})

    # Build context string with rich metadata
    context_parts = []
    for i, chunk in enumerate(context_chunks):
        fname = chunk.get("filename", "Unknown")
        page = chunk.get("page_number", "?")
        section = chunk.get("section_title", "")
        is_table = chunk.get("is_table", False)

        header = f"[Source {i+1}: {fname}, Page {page}"
        if section:
            header += f", Section: {section}"
        if is_table:
            header += ", TABLE"
        header += "]"

        context_parts.append(f"{header}\n{chunk['text']}")

    context = "\n\n---\n\n".join(context_parts)

    # Inject context into system message
    system_with_context = RAG_SYSTEM_PROMPT + f"\n\nDOCUMENT EXCERPTS:\n{context}"

    llm_messages = [{"role": "system", "content": system_with_context}]
    for m in messages:
        if m.role != "system":
            llm_messages.append({"role": m.role, "content": m.content})

    full_response = ""

    try:
        response = await groq_client.chat.completions.create(
            model=MODEL,
            messages=llm_messages,
            max_tokens=1500,
            stream=True,
            temperature=0.1,  # Low temperature = more grounded, less creative
        )

        async for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                full_response += content
                yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

        # Generate follow-up questions (non-blocking)
        followups = await generate_followup_questions(
            query, full_response, filenames, groq_client
        )

        # Compute confidence
        conf_label, conf_score = compute_confidence(context_chunks)

        # Send metadata after streaming
        yield f"data: {json.dumps({'type': 'metadata', 'confidence_label': conf_label, 'confidence_score': conf_score, 'followup_questions': followups})}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        log.error(f"Streaming error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages cannot be empty")

    messages = list(request.messages)
    conv_id = request.conversation_id or "default"

    # No PDFs loaded — regular chat
    if not pdf_sessions:
        async def plain_stream():
            try:
                response = await groq_client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": m.role, "content": m.content} for m in messages],
                    max_tokens=1024,
                    stream=True,
                )
                async for chunk in response:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(plain_stream(), media_type="text/event-stream",
                                  headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # Get last user message
    last_user_msg = next(
        (m.content for m in reversed(messages) if m.role == "user"), None
    )
    if not last_user_msg:
        raise HTTPException(status_code=400, detail="No user message found")

    # Step 1: Query expansion
    expanded_query = await expand_query(last_user_msg, groq_client)

    # Step 2: Embed expanded query
    query_vector = embedder.encode(
        f"query: {expanded_query}",
        normalize_embeddings=True
    ).tolist()

    # Step 3: Hybrid retrieval
    session_ids = list(pdf_sessions.keys())
    raw_chunks = hybrid_search(
        query_vector=query_vector,
        query=expanded_query,
        session_ids=session_ids,
        qdrant_client=qdrant,
        bm25_index=bm25_index,
        top_k=config.retrieval.initial_fetch,
    )

    # Step 4: Rerank
    reranked = reranker.rerank(last_user_msg, raw_chunks)

    # Step 5: Validate — do we have enough context?
    if not reranked:
        async def no_context_stream():
            msg = "I could not find relevant information in the uploaded documents for your question."
            yield f"data: {json.dumps({'type': 'token', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'metadata', 'confidence_label': 'None', 'confidence_score': 0.0, 'followup_questions': []})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(no_context_stream(), media_type="text/event-stream",
                                  headers={"Cache-Control": "no-cache"})

    # Step 6: Save context for conversational memory
    conversation_context[conv_id] = {
        "last_query": last_user_msg,
        "last_chunks": reranked,
    }

    return StreamingResponse(
        stream_rag_response(messages, reranked, last_user_msg, conv_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Transfer-Encoding": "chunked",
        },
    )


# ── Health & Debug ────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "model": MODEL,
        "embedding": config.embedding.model,
        "reranker": config.reranker.model if config.reranker.enabled else "disabled",
        "pdfs_loaded": len(pdf_sessions),
        "cached_embeddings": len(embedding_cache),
    }


@app.get("/api/pdf/list")
async def list_pdfs_():
    return {"total": len(pdf_sessions), "pdfs": list(pdf_sessions.values())}


@app.get("/api/debug/chunks")
async def debug_chunks():
    if not pdf_sessions:
        return {"error": "No PDFs loaded"}

    all_chunks = []
    for session_id in pdf_sessions:
        results = qdrant.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(
                must=[FieldCondition(key="session_id", match=MatchValue(value=session_id))]
            ),
            limit=200,
            with_payload=True,
            with_vectors=False,
        )
        for r in results[0]:
            all_chunks.append({
                "filename": r.payload.get("filename"),
                "chunk_index": r.payload.get("chunk_index"),
                "page_number": r.payload.get("page_number"),
                "section_title": r.payload.get("section_title"),
                "is_table": r.payload.get("is_table"),
                "word_count": r.payload.get("word_count"),
                "preview": r.payload.get("text", "")[:120] + "...",
            })

    return {
        "total_pdfs": len(pdf_sessions),
        "total_chunks": len(all_chunks),
        "chunks": sorted(all_chunks, key=lambda x: (x["filename"], x["chunk_index"]))
    }


@app.get("/api/debug/retrieve")
async def debug_retrieve(query: str, top_k: int = 5):
    if not pdf_sessions:
        return {"error": "No PDFs loaded"}

    start = time.time()
    expanded = await expand_query(query, groq_client)

    query_vector = embedder.encode(f"query: {expanded}", normalize_embeddings=True).tolist()
    session_ids = list(pdf_sessions.keys())

    raw = hybrid_search(query_vector, expanded, session_ids, qdrant, bm25_index, top_k=20)
    reranked = reranker.rerank(query, raw)[:top_k]

    conf_label, conf_score = compute_confidence(reranked)

    return {
        "original_query": query,
        "expanded_query": expanded,
        "retrieval_ms": round((time.time() - start) * 1000, 2),
        "confidence": f"{conf_label} ({conf_score*100:.0f}%)",
        "results": [
            {
                "rank": i + 1,
                "filename": c.get("filename"),
                "page": c.get("page_number"),
                "section": c.get("section_title"),
                "is_table": c.get("is_table"),
                "vector_score": round(c.get("vector_score", 0), 4),
                "bm25_score": round(c.get("bm25_score", 0), 4),
                "hybrid_score": round(c.get("hybrid_score", 0), 4),
                "reranker_score": round(c.get("reranker_score", 0), 4),
                "text_preview": c.get("text", "")[:200],
            }
            for i, c in enumerate(reranked)
        ]
    }


@app.post("/chat")
async def chat(request: ChatRequest, current_user: User = Depends(get_current_user)):
    # current_user is automatically populated from the JWT
    # If no valid token → FastAPI returns 401 automatically
    ...