"""
utils/text.py

Text processing utilities for the platform.

Used by the knowledge ingestion pipeline (chunking documents before
embedding), prompt construction, and output formatting.

Design:
    - All functions are pure (no side effects, no state).
    - chunk_text() uses a sliding-window approach with configurable
      overlap — the same algorithm used by most LLM frameworks.
    - No external dependencies beyond the standard library.
"""

from __future__ import annotations

import re
import textwrap


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[str]:
    """
    Split a long text into overlapping chunks for embedding.

    Uses a paragraph-aware strategy: tries to split on paragraph
    boundaries first, then falls back to character-level chunking
    with overlap when paragraphs are too large.

    Args:
        text:          The input text to chunk.
        chunk_size:    Maximum character length per chunk.
        chunk_overlap: Number of characters to repeat at chunk boundaries.

    Returns:
        List of non-empty text chunks.
    """
    if not text or not text.strip():
        return []

    if len(text) <= chunk_size:
        return [text.strip()]

    chunks: list[str] = []
    start = 0
    text = text.strip()

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            # Last chunk — take everything remaining
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break

        # Try to find a natural break point (paragraph, sentence, or word)
        natural_break = _find_natural_break(text, start, end)
        chunk = text[start:natural_break].strip()

        if chunk:
            chunks.append(chunk)

        # Next chunk starts with overlap
        start = max(start + 1, natural_break - chunk_overlap)

    return chunks


def _find_natural_break(text: str, start: int, end: int) -> int:
    """
    Find the best character position to break the text near `end`.

    Priority: double newline (paragraph) > single newline > period > space.
    Falls back to `end` if no natural break is found in range.
    """
    search_window = text[start:end]

    # Paragraph break
    idx = search_window.rfind("\n\n")
    if idx != -1 and idx > len(search_window) // 3:
        return start + idx + 2

    # Sentence end
    idx = search_window.rfind(". ")
    if idx != -1 and idx > len(search_window) // 3:
        return start + idx + 2

    # Single newline
    idx = search_window.rfind("\n")
    if idx != -1 and idx > len(search_window) // 3:
        return start + idx + 1

    # Word boundary
    idx = search_window.rfind(" ")
    if idx != -1:
        return start + idx + 1

    return end


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to a maximum character length, adding a suffix.

    Tries to break at a word boundary.

    Args:
        text:       Input text.
        max_length: Maximum total length including suffix.
        suffix:     String appended when truncation occurs.

    Returns:
        Truncated string, or the original string if short enough.
    """
    if len(text) <= max_length:
        return text

    available = max_length - len(suffix)
    truncated = text[:available]

    # Try to break at word boundary
    last_space = truncated.rfind(" ")
    if last_space > available // 2:
        truncated = truncated[:last_space]

    return truncated.rstrip() + suffix


def sanitize_string(value: str) -> str:
    """
    Remove control characters and normalize whitespace.

    Safe for use before storing text to the database or embedding store.
    """
    # Remove null bytes and other control characters (except newlines/tabs)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    # Normalize excessive whitespace
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def format_as_bullet_list(items: list[str], indent: int = 0) -> str:
    """
    Format a list of strings as a markdown bullet list.

    Args:
        items:  List of text items.
        indent: Number of spaces to indent each bullet.

    Returns:
        Multi-line string with each item as "• item".
    """
    prefix = " " * indent + "• "
    return "\n".join(f"{prefix}{item}" for item in items)


def dedent_and_strip(text: str) -> str:
    """Remove common leading whitespace and strip outer whitespace."""
    return textwrap.dedent(text).strip()


def extract_json_block(text: str) -> str | None:
    """
    Extract the first JSON block from a string (e.g. LLM output).

    Handles both fenced ```json ... ``` blocks and bare JSON objects/arrays.

    Args:
        text: Raw text potentially containing a JSON block.

    Returns:
        The extracted JSON string, or None if no JSON block found.
    """
    # Try fenced code block first
    fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    # Try bare JSON object
    bare = re.search(r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})", text, re.DOTALL)
    if bare:
        return bare.group(1).strip()

    return None
