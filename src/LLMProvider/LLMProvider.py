# Standard
import re
import asyncio
from abc import ABC, abstractmethod
# Special
from google.genai import types
# Local

class LLMProvider(ABC):
    """LLMProvider - інтерфейс для LLMs, абстрактний клас, що
    описує необхідні змінні та методи для класів-нащадків."""

    def embed_content(self, content):
        """Генерація embedding для введеного content."""
        last_error = None

        # Searching for a working key
        for api_key in self.LLM_API_KEYS:
            try:
                response = self._embed_content(api_key, content)
                return response
            
            except Exception as e:
                last_error = e
    
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
                               MAX_RETRIES: int = 2) -> str:
        """Генерація відповіді на основі prompt.

        Стратегія при помилках:
            - 429 per-minute: чекає retryDelay із відповіді і повторює.
            - 429 per-day / limit=0: пропускає до наступної моделі.
            - 503 UNAVAILABLE: чекає і повторює (тимчасове перевантаження).
            - 404 NOT_FOUND: пропускає модель одразу.
            - Інша помилка: пропускає до наступного API-ключа.
        """
        last_error: Exception | None = None
        
        for api_key in self.LLM_API_KEYS:
            for model in self.GENERATION_MODELS:
                for attempt in range(1, MAX_RETRIES + 2):  # спроби: 1, 2, 3
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
                            print(f"[agent] ✅ Success: key=...{api_key[-6:]}, model={model}")
                            return response

                    except Exception as e:
                        error_str = str(e)
                        last_error = e

                        is_404 = "404" in error_str or "NOT_FOUND" in error_str
                        is_429 = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str
                        is_503 = "503" in error_str or "UNAVAILABLE" in error_str

                        # 404 — модель застаріла або не існує, пропускаємо одразу
                        if is_404:
                            print(f"[agent] 404 model not found, skip: {model}")
                            break

                        # 503 — тимчасове перевантаження, чекаємо і повторюємо
                        if is_503:
                            if attempt <= MAX_RETRIES:
                                delay = attempt * 10
                                print(f"[agent] 503 on model={model}, retry in {delay}s (attempt {attempt})")
                                await asyncio.sleep(delay)
                                continue
                            print(f"[agent] 503 retries exhausted for model={model} → next model")
                            break

                        # 429 — розрізняємо per-day і per-minute
                        if is_429:
                            is_per_day = (
                                "GenerateRequestsPerDay" in error_str
                                or '"limit": 0' in error_str
                                or "limit: 0" in error_str
                            )
                            if is_per_day:
                                print(f"[agent] Per-day quota exhausted, model={model} → next model")
                                break

                            # per-minute — чекаємо retryDelay і повторюємо
                            if attempt <= MAX_RETRIES:
                                delay = self._parse_retry_delay(error_str) or (attempt * 15)
                                print(f"[agent] Per-minute 429, model={model}, retry in {delay}s (attempt {attempt})")
                                await asyncio.sleep(delay)
                                continue
                            print(f"[agent] Retries exhausted for model={model} → next model")
                            break

                        # Невідома помилка — наступний ключ
                        print(f"[agent] Unknown error on model={model}: {e}")
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