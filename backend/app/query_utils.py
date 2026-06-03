"""
Query Expansion

WHY:
User types: "refund policy"
BM25 and vector search look for exactly those words.
But the document might say "return and refund terms" or "reimbursement conditions".

Query expansion generates MULTIPLE search terms from one question,
dramatically improving recall (finding all relevant chunks).

We use the Groq LLM itself to expand queries — fast, free, already available.
"""
from groq import AsyncGroq
import os
import logging

log = logging.getLogger(__name__)


async def expand_query(query: str, client: AsyncGroq) -> str:
    """
    Use LLM to generate expanded search terms.
    Returns original query + expanded terms as one search string.

    Example:
    Input:  "What is the right to education?"
    Output: "right to education Article 21A fundamental rights children
             free compulsory education age six fourteen"
    """
    try:
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",  # fast small model for this task
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a search query expansion assistant. "
                        "Given a question, output ONLY a space-separated list of "
                        "relevant search terms and synonyms that would help find "
                        "the answer in a document. "
                        "No explanations. No sentences. Just keywords. Max 20 words."
                    ),
                },
                {"role": "user", "content": query},
            ],
            max_tokens=60,
            temperature=0.3,
        )

        expanded_terms = response.choices[0].message.content.strip()
        # Combine original + expanded for maximum recall
        combined = f"{query} {expanded_terms}"
        log.info(f"Query expanded: '{query}' → '{combined[:100]}'")
        return combined

    except Exception as e:
        log.warning(f"Query expansion failed ({e}), using original query")
        return query  # fallback to original


async def generate_followup_questions(
    query: str,
    answer: str,
    filenames: list,
    client: AsyncGroq,
) -> list:
    """
    Generate 3 relevant follow-up questions after an answer.
    Makes the chatbot feel more interactive and guides exploration.
    """
    try:
        files_str = ", ".join(filenames)
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate exactly 3 short follow-up questions a user might ask "
                        "after this Q&A. Output ONLY a JSON array of 3 strings. "
                        'Example: ["Question 1?", "Question 2?", "Question 3?"]'
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Documents: {files_str}\n"
                        f"Question: {query}\n"
                        f"Answer summary: {answer[:300]}"
                    ),
                },
            ],
            max_tokens=150,
            temperature=0.5,
        )

        import json
        raw = response.choices[0].message.content.strip()
        # Strip markdown code blocks if present
        raw = raw.replace("```json", "").replace("```", "").strip()
        questions = json.loads(raw)
        if isinstance(questions, list):
            return questions[:3]
        return []

    except Exception as e:
        log.warning(f"Follow-up generation failed ({e})")
        return []
