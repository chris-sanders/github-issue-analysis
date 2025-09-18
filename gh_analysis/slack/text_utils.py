"""Text splitting utilities for Slack message formatting."""

from typing import List


def split_text_at_boundaries(text: str, max_length: int = 2900) -> List[str]:
    """Split text at sentence/paragraph boundaries while preserving formatting.

    Args:
        text: The text to split
        max_length: Maximum length per part (default 2900 to leave room for formatting)

    Returns:
        List of text parts, each under max_length
    """
    if len(text) <= max_length:
        return [text]

    parts = []
    current_part = ""

    # Split by paragraphs first, then sentences if needed
    paragraphs = text.split("\n\n")

    for paragraph in paragraphs:
        if len(current_part + paragraph) <= max_length:
            current_part += paragraph + "\n\n"
        else:
            if current_part:
                parts.append(current_part.rstrip())
                current_part = ""

            # If paragraph itself is too long, split by sentences
            if len(paragraph) > max_length:
                sentences = paragraph.split(". ")
                # If only one sentence (no periods found), force split at character boundary
                if len(sentences) == 1 and len(paragraph) > max_length:
                    # Force split at character boundaries as last resort
                    while len(paragraph) > max_length:
                        parts.append(paragraph[:max_length])
                        paragraph = paragraph[max_length:]
                    if paragraph:
                        current_part = paragraph + "\n\n"
                else:
                    # Handle sentence-by-sentence splitting
                    for i, sentence in enumerate(sentences):
                        sentence_with_period = sentence + (
                            ". " if i < len(sentences) - 1 else ""
                        )
                        if len(current_part + sentence_with_period) <= max_length:
                            current_part += sentence_with_period
                        else:
                            if current_part:
                                parts.append(current_part.rstrip())
                            current_part = sentence_with_period
            else:
                current_part = paragraph + "\n\n"

    if current_part:
        parts.append(current_part.rstrip())

    return parts


def create_continuation_header(title: str, is_continuation: bool) -> str:
    """Generate header with continuation indicator if needed.

    Args:
        title: Base title text
        is_continuation: Whether this is a continuation part

    Returns:
        Title with continuation indicator if needed
    """
    return f"{title} (continued)" if is_continuation else title


def estimate_blocks_size(blocks: List[dict]) -> int:
    """Calculate approximate character count for blocks.

    Args:
        blocks: List of Slack Block Kit blocks

    Returns:
        Total estimated character count
    """
    total = 0
    for block in blocks:
        if block.get("type") == "section" and "text" in block:
            total += len(block["text"].get("text", ""))
    return total
