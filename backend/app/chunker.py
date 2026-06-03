"""
Smart Chunker

WHY simple word-count chunking is bad:
- Splits in the middle of sentences
- Splits in the middle of tables (breaks them)
- Loses section context
- Chunks don't know what topic they're about

WHY this chunker is better:
- Groups blocks by section (heading + its paragraphs stay together)
- Never splits a table across chunks
- Adds section title to every chunk's context
- Overlaps chunks so boundary sentences appear in both neighbors
"""
from dataclasses import dataclass, field
from typing import List
import logging
from app.parser import ParsedDocument, ParsedBlock
from app.config import config

log = logging.getLogger(__name__)


@dataclass
class Chunk:
    """
    One chunk ready for embedding and storage.
    Rich metadata so every chunk knows its origin.
    """
    text: str               # The actual text sent to embedder + LLM
    chunk_id: str           # Unique ID: "{filename}_{index}"
    filename: str
    page_number: int        # Page where this chunk starts
    section_title: str      # Section heading above this chunk
    chunk_index: int        # Position in document
    is_table: bool = False
    word_count: int = 0


def word_count(text: str) -> int:
    return len(text.split())


def smart_chunk(doc: ParsedDocument) -> List[Chunk]:
    """
    Convert parsed document blocks into overlapping chunks.

    Strategy:
    1. Tables → always one chunk each (never split)
    2. Text blocks → group into chunks of ~600 words
    3. Add section title as prefix so LLM knows context
    4. Overlap: last 120 words of chunk N become first 120 words of chunk N+1
    """
    cfg = config.chunking
    chunks: List[Chunk] = []
    chunk_index = 0

    # Collect text blocks grouped by section
    # Tables become their own standalone chunks
    buffer_text = []
    buffer_pages = []
    buffer_section = ""

    def flush_buffer():
        """Turn accumulated text buffer into one or more chunks."""
        nonlocal chunk_index

        if not buffer_text:
            return

        combined = " ".join(buffer_text)
        words = combined.split()
        start = 0

        while start < len(words):
            end = min(start + cfg.size, len(words))
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)

            # Prepend section context so LLM knows what section this is from
            if buffer_section:
                full_text = f"[Section: {buffer_section}]\n{chunk_text}"
            else:
                full_text = chunk_text

            page = buffer_pages[min(start, len(buffer_pages) - 1)] if buffer_pages else 1

            chunks.append(Chunk(
                text=full_text,
                chunk_id=f"{doc.filename}_{chunk_index}",
                filename=doc.filename,
                page_number=page,
                section_title=buffer_section,
                chunk_index=chunk_index,
                is_table=False,
                word_count=len(chunk_words),
            ))
            chunk_index += 1

            if end >= len(words):
                break

            # Slide forward with overlap
            start += cfg.size - cfg.overlap

    for block in doc.blocks:
        if block.block_type == "heading":
            # Flush what we have, start new section
            flush_buffer()
            buffer_text.clear()
            buffer_pages.clear()
            buffer_section = block.text
            # Add heading text to next chunk's buffer
            buffer_text.append(block.text)
            buffer_pages.append(block.page_number)

        elif block.is_table:
            # Tables: flush current buffer, store table as standalone chunk
            flush_buffer()
            buffer_text.clear()
            buffer_pages.clear()

            table_text = f"[Section: {block.section_title}]\n[TABLE]\n{block.text}"
            chunks.append(Chunk(
                text=table_text,
                chunk_id=f"{doc.filename}_{chunk_index}",
                filename=doc.filename,
                page_number=block.page_number,
                section_title=block.section_title,
                chunk_index=chunk_index,
                is_table=True,
                word_count=word_count(block.text),
            ))
            chunk_index += 1

        else:
            # Regular paragraph — add to buffer
            buffer_text.append(block.text)
            buffer_pages.append(block.page_number)

            # Flush if buffer getting large
            if word_count(" ".join(buffer_text)) >= cfg.size:
                flush_buffer()
                # Keep overlap: last cfg.overlap words stay in buffer
                combined = " ".join(buffer_text)
                overlap_words = combined.split()[-cfg.overlap:]
                buffer_text.clear()
                buffer_pages.clear()
                buffer_text.append(" ".join(overlap_words))
                if buffer_pages:
                    buffer_pages.append(block.page_number)

    # Final flush
    flush_buffer()

    log.info(f"Smart chunking: {len(doc.blocks)} blocks → {len(chunks)} chunks")
    for i, c in enumerate(chunks[:3]):
        log.info(f"  Chunk {i}: page={c.page_number} section='{c.section_title[:40]}' words={c.word_count} table={c.is_table}")

    return chunks
