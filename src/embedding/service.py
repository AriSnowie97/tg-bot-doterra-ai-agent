# Standard
# Special
# Local
from src.LLMProvider import GeminiFlashProvider as LLM


def create_embedding(content: str) -> list[float]:
    """Генерація embedding для переданого content.
    Повертає response."""
    response = LLM().embed_content(content)

    return response.embeddings[0].values