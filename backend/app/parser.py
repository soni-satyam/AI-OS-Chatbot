"""
Smart Document Parser

WHY: pypdf extracts raw text and loses all structure.
     pdfplumber preserves tables, page numbers, and layout.
     We tag each piece of text with metadata so chunks know
     which page and section they came from.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional
import pdfplumber
import logging

log = logging.getLogger(__name__)


@dataclass
class ParsedBlock:
    """
    One logical block of content from the PDF.
    Could be a heading, paragraph, or table.
    """
    text: str
    page_number: int
    block_type: str          # "heading" | "paragraph" | "table"
    section_title: str = ""  # nearest heading above this block
    is_table: bool = False


@dataclass
class ParsedDocument:
    filename: str
    blocks: List[ParsedBlock] = field(default_factory=list)
    total_pages: int = 0


def looks_like_heading(text: str) -> bool:
    """
    Heuristic to detect headings.
    Headings are typically:
    - Short (< 12 words)
    - Title-cased or ALL CAPS
    - Don't end with a period
    - May start with a number like "1." or "1.1"
    """
    text = text.strip()
    if not text:
        return False
    words = text.split()
    if len(words) > 12:
        return False
    if text.endswith('.') and len(words) > 3:
        return False
    # Numbered heading: "1. Introduction" or "Article 5"
    if re.match(r'^(\d+\.?\d*\.?\s|Article\s|Section\s|Chapter\s)', text, re.IGNORECASE):
        return True
    # ALL CAPS heading
    if text.isupper() and len(words) >= 1:
        return True
    # Title Case heading
    title_words = [w for w in words if w[0].isupper()]
    if len(title_words) / max(len(words), 1) > 0.6 and len(words) <= 8:
        return True
    return False


def table_to_markdown(table: List[List]) -> str:
    """
    Convert pdfplumber table (list of rows) to markdown table.
    WHY: Markdown tables are readable by both humans and LLMs.
    """
    if not table or not table[0]:
        return ""

    # Clean None values
    cleaned = []
    for row in table:
        cleaned.append([str(cell).strip() if cell else "" for cell in row])

    if not cleaned:
        return ""

    header = cleaned[0]
    rows = cleaned[1:]

    md = "| " + " | ".join(header) + " |\n"
    md += "| " + " | ".join(["---"] * len(header)) + " |\n"
    for row in rows:
        # Pad row if shorter than header
        while len(row) < len(header):
            row.append("")
        md += "| " + " | ".join(row[:len(header)]) + " |\n"

    return md


def parse_pdf(file_path: str, filename: str) -> ParsedDocument:
    """
    Extract text from PDF preserving structure.

    Strategy:
    1. Use pdfplumber to get page-by-page content
    2. Extract tables first (before text, to avoid double-counting)
    3. Detect headings using heuristics
    4. Tag each block with page number and current section
    """
    doc = ParsedDocument(filename=filename)
    current_section = "Introduction"

    log.info(f"Parsing '{filename}'...")

    with pdfplumber.open(file_path) as pdf:
        doc.total_pages = len(pdf.pages)

        for page_num, page in enumerate(pdf.pages, start=1):
            # --- Extract tables first ---
            tables = page.extract_tables()
            table_bboxes = []

            for table in tables:
                if not table:
                    continue
                md_table = table_to_markdown(table)
                if md_table:
                    doc.blocks.append(ParsedBlock(
                        text=md_table,
                        page_number=page_num,
                        block_type="table",
                        section_title=current_section,
                        is_table=True,
                    ))
                    log.debug(f"  Page {page_num}: extracted table ({len(table)} rows)")

            # --- Extract text (excluding table regions) ---
            # Use extract_text for simplicity; advanced impl would exclude bbox
            text = page.extract_text() or ""
            if not text.strip():
                continue

            # Split into lines and classify
            lines = text.split('\n')
            paragraph_buffer = []

            for line in lines:
                line = line.strip()
                if not line:
                    # Flush paragraph buffer
                    if paragraph_buffer:
                        para_text = " ".join(paragraph_buffer)
                        doc.blocks.append(ParsedBlock(
                            text=para_text,
                            page_number=page_num,
                            block_type="paragraph",
                            section_title=current_section,
                        ))
                        paragraph_buffer = []
                    continue

                if looks_like_heading(line):
                    # Flush existing paragraph first
                    if paragraph_buffer:
                        para_text = " ".join(paragraph_buffer)
                        doc.blocks.append(ParsedBlock(
                            text=para_text,
                            page_number=page_num,
                            block_type="paragraph",
                            section_title=current_section,
                        ))
                        paragraph_buffer = []

                    # Update current section and add heading block
                    current_section = line
                    doc.blocks.append(ParsedBlock(
                        text=line,
                        page_number=page_num,
                        block_type="heading",
                        section_title=current_section,
                    ))
                else:
                    paragraph_buffer.append(line)

            # Flush remaining paragraph
            if paragraph_buffer:
                doc.blocks.append(ParsedBlock(
                    text=" ".join(paragraph_buffer),
                    page_number=page_num,
                    block_type="paragraph",
                    section_title=current_section,
                ))

    log.info(f"Parsed '{filename}': {doc.total_pages} pages, {len(doc.blocks)} blocks")
    return doc
