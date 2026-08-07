"""
Діагностичний скрипт — тестує кожен API ключ на кожній моделі.
Запуск: python test_keys.py
"""
# Standard
import sys
# Special
from dotenv import load_dotenv
from google.genai import types
# Local
from src.LLMProvider import GeminiFlashProvider as LLM


# Фікс кодування для Windows PowerShell
sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

llm = LLM()
KEYS = llm.LLM_API_KEYS
MODELS = llm.GENERATION_MODELS

for key_name, api_key in enumerate(KEYS, 1): # KEYS.items():
    if not api_key:
        print(f"\n[{key_name}] NOT SET in .env\n")
        continue

    print(f"\n[{key_name}] prefix={api_key[:12]}...")

    for model in MODELS:
        try:
            response = llm._generate_content(api_key,
                                             model,
                                             "Say 'OK' in one word.",
                                             types.GenerateContentConfig(max_output_tokens=5))

            # Перевіряємо чи є text у відповіді
            if response.text is not None:
                print(f"  OK {model}: '{response.text.strip()}'")
                break  # цей ключ+модель працює
            else:
                # Показуємо деталі відповіді якщо text=None
                candidates = response.candidates or []
                finish_reason = candidates[0].finish_reason if candidates else "no candidates"
                print(f"  WARN {model}: response.text=None, finish_reason={finish_reason}")

        except Exception as e:
            msg = str(e)[:150].replace("\n", " ")
            print(f"  FAIL {model}: {msg}")