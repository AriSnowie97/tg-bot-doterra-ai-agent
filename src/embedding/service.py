# Standard
import os
# Special
from google import genai
# Local


EMBED_MODEL = "gemini-embedding-2"

GEMINI_API_KEY_1 = os.getenv("GEMINI_API_KEY_1", "")
GEMINI_API_KEY_2 = os.getenv("GEMINI_API_KEY_2", "")
GEMINI_API_KEY_3 = os.getenv("GEMINI_API_KEY_3", "")

GEMINI_API_KEYS = [
    GEMINI_API_KEY_1,
    GEMINI_API_KEY_2,
    GEMINI_API_KEY_3
]


def create_embedding(content: str) -> list[float]:
    """Генерація embedding для переданого content."""

    last_error = None

    for api_key in GEMINI_API_KEYS:
        try:
            client = genai.Client(api_key=api_key)

            response = client.models.embed_content(
                model=EMBED_MODEL,
                contents=content,
                config={
                    "output_dimensionality": 768
                }
            )

            return response.embeddings[0].values
        
        except Exception as e:
            last_error = e

    raise RuntimeError(f"Усі API-ключі недоступні. {last_error}")