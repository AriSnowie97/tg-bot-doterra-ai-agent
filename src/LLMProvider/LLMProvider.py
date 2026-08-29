# Standard
import re
import asyncio
import time
from abc import ABC, abstractmethod
# Special
from google.genai import types
# Local

class LLMProvider(ABC):
    """LLMProvider - інтерфейс для LLMs, абстрактний клас, що
    описує необхідні змінні та методи для класів-нащадків."""

    def embed_content(self, content, MAX_RETRIES: int = 5):
        """Генерація embedding для введеного content з Retry-логікою для 429."""
        last_error = None

        for attempt in range(1, MAX_RETRIES + 2):
            for api_key in self.LLM_API_KEYS:
                try:
                    response = self._embed_content(api_key, content)
                    return response
                except Exception as e:
                    error_str = str(e)
                    last_error = e

                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        print(f"[agent] 429 on embed_content with key ...{api_key[-6:] if api_key else ''}")
                        continue
                    
                    print(f"[agent] Error on embed_content with key ...{api_key[-6:] if api_key else ''}: {e}")
                    continue
            
            # Якщо всі ключі перебрані і спроба ще є - чекаємо
            if attempt <= MAX_RETRIES:
                delay = self._parse_retry_delay(str(last_error))
                if not delay:
                    delay = attempt * 10
                print(f"[agent] All keys failed. Sleeping {delay}s before attempt {attempt+1}")
                time.sleep(delay)
            else:
                break

        raise RuntimeError(f"Для {self.NAME} усі API-ключі недоступні. {last_error}")


    def _parse_retry_delay(self, error_str: str) -> float | None:
        """Витягує retryDelay із тексту помилки Gemini (формат: 'N.NNs' або 'Ns')."""
        match = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+\.?\d*)\s*s", error_str)
        if match:
            return float(match.group(1)) + 1.0  # +1с буфер
        return None


    async def generate_content(self,
                               content: str,
                               config: types.GenerateContentConfigOrDict | None = None,
                               MAX_RETRIES: int = 2,
                               models: list[str] | None = None) -> str:
        """Генерація відповіді на основі prompt."""
        models = models if models is not None else self.GENERATION_MODELS
        last_error: Exception | None = None
        
        for attempt in range(1, MAX_RETRIES + 2):
            for api_key in self.LLM_API_KEYS:
                for model in models:
                    try:
                        response = await asyncio.to_thread(
                            self._generate_content,
                            api_key=api_key,
                            model=model,
                            content=content,
                            config=config
                        )

                        if response.text is None:
                            candidates = response.candidates or []
                            finish_reason = candidates[0].finish_reason if candidates else "unknown"
                            raise ValueError(f"response.text=None, finish_reason={finish_reason}, model={model}")
                        else:
                            print(f"[agent] ✅ Success: key=...{api_key[-6:] if api_key else ''}, model={model}")
                            return response

                    except Exception as e:
                        error_str = str(e)
                        last_error = e

                        is_404 = "404" in error_str or "NOT_FOUND" in error_str
                        if is_404:
                            print(f"[agent] 404 model not found, skip: {model}")
                            continue

                        is_429 = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str
                        if is_429:
                            print(f"[agent] 429 on model={model}, key=...{api_key[-6:] if api_key else ''} → next")
                            continue

                        is_503 = "503" in error_str or "UNAVAILABLE" in error_str
                        if is_503:
                            print(f"[agent] 503 on model={model}, key=...{api_key[-6:] if api_key else ''} → next")
                            continue

                        print(f"[agent] Unknown error on model={model}: {e}")
                        continue
            
            if attempt <= MAX_RETRIES:
                delay = attempt * 5
                print(f"[agent] All keys/models failed. Sleeping {delay}s before attempt {attempt+1}")
                await asyncio.sleep(delay)
            else:
                break

        raise RuntimeError(
            f"Усі Gemini API-ключі та моделі недоступні. "
            f"Остання помилка: {last_error}"
        )


    # Mandatory variables
    @property
    @abstractmethod
    def NAME(self):
        """Ім'я класу Provider."""
        pass

    @property
    @abstractmethod
    def LLM_API_KEYS(self):
        """Список Api ключів."""
        pass

    @property
    @abstractmethod
    def EMBED_MODELS(self):
        """Список моделей для embedding."""
        pass

    @property
    @abstractmethod
    def GENERATION_MODELS(self):
        """Список моделей для генерації контенту."""
        pass


    # Mandatory methods
    @abstractmethod
    def _get_client(self, api_key: str):
        """Отримання клієнта LLM."""
        pass


    @abstractmethod
    def _embed_content(self, api_key: str, content: str) -> list[float]:
        """Приватний допоміжний метод для публічного embed_content. 
        Генерація embedding для введеного content."""
        pass


    @abstractmethod
    def _generate_content(self, api_key: str, model: str, content: str,
                          config: types.GenerateContentConfigOrDict | None = None,) -> str:
        """Приватний допоміжний метод для публічного generate_content."""
        pass