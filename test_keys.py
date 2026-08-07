"""
Діагностичний скрипт — тестує кожен API ключ на кожній моделі.
Запуск: python test_keys.py
"""
# Standard
import os
import sys
# Special
from dotenv import load_dotenv
from google import genai
from google.genai import types
# Local
from src.LLMProvider import GeminiFlashProvider as LLM


# Фікс кодування для Windows PowerShell
sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

llm = LLM()

KEYS = llm.LLM_API_KEYS
MODELS = llm.GENERATION_MODELS

# KEYS = {
#     "KEY_1": os.getenv("GEMINI_API_KEY_1", ""),
#     "KEY_2": os.getenv("GEMINI_API_KEY_2", ""),
#     "KEY_3": os.getenv("GEMINI_API_KEY_3", ""),
# }

# MODELS = [
#     "gemini-3.6-flash",
#     "gemini-3.5-flash",
#     "gemini-3.5-flash-lite",
#     "gemini-3.1-flash-lite",
#     "gemini-2.0-flash",
# ]

for key_name, api_key in enumerate(KEYS, 1): # KEYS.items():
    if not api_key:
        print(f"\n[{key_name}] NOT SET in .env\n")
        continue

    print(f"\n[{key_name}] prefix={api_key[:12]}...")

    for model in MODELS:
        try:
            # client = genai.Client(api_key=api_key)
            # response = client.models.generate_content(
            #     model=model,
            #     contents="Say 'OK' in one word.",
            #     config=types.GenerateContentConfig(max_output_tokens=5),
            # )
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
