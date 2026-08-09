# Standard
import os
# Special
from google import genai
from google.genai import types
# Local
from . import LLMProvider


class GeminiFlashProvider(LLMProvider):
    NAME = "GeminiFlashProvider"
    
    LLM_API_KEYS = [
        os.getenv("GEMINI_API_KEY_1", ""),
        os.getenv("GEMINI_API_KEY_2", ""),
        os.getenv("GEMINI_API_KEY_3", "")
    ]

    EMBED_MODELS = [
        "gemini-embedding-2"
    ]

    GENERATION_MODELS: list[str] = [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ]


    def _get_client(self, api_key: str):
        return genai.Client(api_key=api_key)


    def _embed_content(self, api_key: str, content: str) -> list[float]:
        client = self._get_client(api_key)

        response = client.models.embed_content(
            model=self.EMBED_MODELS[0],
            contents=content,
            config={
                "output_dimensionality": 768
            }
        )

        return response


    def _generate_content(self, api_key: str, model: str, content: str,
                          config: types.GenerateContentConfigOrDict | None = None) -> str:
        """Синхронний виклик Gemini API (запускається через asyncio.to_thread).

        Args:
            api_key:       Gemini API ключ.
            model:         назва моделі Gemini.
            system_prompt: системний промпт із RAG-контекстом.
            user_text:     повідомлення користувача.

        Returns:
            Текст відповіді моделі.
        """
        client = self._get_client(api_key)
    
        response = client.models.generate_content(
            model=model,
            contents=content,
            config=config
        )

        return response