# doTERRA AI Assistant & RAG Research Agent 🌿

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![aiogram 3.x](https://img.shields.io/badge/aiogram-3.x-green.svg)](https://docs.aiogram.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791.svg)](https://github.com/pgvector/pgvector)
[![Google Gemini](https://img.shields.io/badge/LLM-Gemini_Flash-8E75C2.svg)](https://ai.google.dev/)
[![Tests](https://img.shields.io/badge/Tests-61%20passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Академічно-інженерний проект (Дипломна робота):** Дослідження та розробка безпечного діалогового RAG-асистента в чутливих доменах (велнес та ароматерапія) з багаторівневим FSM-скринінгом протипоказань та захистом від медичної дезінформації.

---

## 📌 1. Наукова та практична цінність проекту

Сучасні LLM мають схильність до галюцинацій та генерації надто самовпевнених рекомендацій у сферах, дотичних до здоров'я (велнес, траволікування, ефірні олії). Пряме застосування базового RAG (Retrieval-Augmented Generation) несе ризики, якщо користувач має приховані протипоказання (вагітність, немовлята, хронічні хвороби, прийом ліків).

### 🎯 Наукова новизна та цілі дослідження:
1. **Архітектура безпеки (Safety-First RAG):** Розробка гібридного конвеєра, де генерації відповіді передує детекція медичних скарг та «червоних прапорів» (*Red Flags*).
2. **Діалоговий FSM-скринінг:** Реалізація кінцевого автомата станів (`active` / `red_flag`), що збирає анамнез користувача перед рекомендацією олій та ескалює складні випадки до лікаря або живого спеціаліста.
3. **Захист від рольових ін'єкцій:** Санітизація контексту розмови та нормалізація Unicode NFKC для унеможливлення підробки системних інструкцій.
4. **Оцінка якості та безпеки:** Порівняльний аналіз метрик безпеки (*Safety Rate*, *False Escalation Rate*, *Disclaimer Compliance*) між наївним RAG та Guarded FSM RAG.

---

## 🏗️ 2. Архітектура системи

```mermaid
flowchart TD
    User([Користувач Telegram / Mini App]) --> Middleware[RateLimit Middleware & Sanitizer]
    Middleware --> IntentCheck{Аналіз наміру}
    
    IntentCheck -->|Привітання / Реакція / Стикер| StickerEngine[Stickers Engine aromaaitgbot]
    StickerEngine --> FastReply([Швидка відповідь зі стікером])
    
    IntentCheck -->|Питання / Скарга| Screening[Screening & Red Flag Detector]
    
    Screening -->|Виявлено Red Flag| RedFlagBranch[Ескалація: контакт лікаря / спеціаліста]
    RedFlagBranch --> RespDisclaimer
    
    Screening -->|Медична скарга| FSM[FSM Context Manager active mode]
    FSM --> VectorSearch
    
    Screening -->|Загальне запитання| VectorSearch[pgvector RAG: Косинусний пошук чанків]
    
    VectorSearch --> PromptBuilder[System Prompt + Context Builder]
    PromptBuilder --> GeminiLLM[Google Gemini Flash LLM Provider]
    
    GeminiLLM --> RespDisclaimer[Hardcoded Medical Disclaimer & Safety Redact]
    RespDisclaimer --> FeedbackKB[Inline Feedback 👍 / 👎 + MiniApp Guide Links]
    
    FeedbackKB --> User
    FeedbackKB -->|Збереження голосів| PostgresDB[(PostgreSQL + pgvector Database)]
```

---

## 🧩 3. Ключові компоненти та стек технологій

| Компонент | Технології | Опис |
|---|---|---|
| **Telegram Bot** | Python 3.12+, aiogram 3.20 | Асинхронний бот із підтримкою приватних чатів, груп, WebApp та стікерпаку |
| **Vector Database** | PostgreSQL, pgvector 0.5.0 | Зберігання та косинусний пошук 768-мірних векторних ембеддінгів бази знань |
| **LLM Provider** | Google GenAI SDK (Gemini 2.5/Flash) | Генерація відповідей із захистом від таймаутів (retry + fallback) |
| **Telegram Mini App** | React, Vite, FastAPI, Uvicorn | Інтерактивний каталог продуктів, карточки олій та протоколи *Symphony of the Cells* |
| **Content Pipeline** | BeautifulSoup, ftfy, nh3 | Парсинг офіційних документів doTERRA, санітизація HTML/Markdown, чанкінг |
| **Автопостинг та фонові задачі** | APScheduler 3.11 | Розклад періодичних публікацій освітнього контенту в Telegram-канал |
| **Тестування та CI/CD** | Pytest, GitHub Actions, Docker, Railway | 61 автоматизований тест, лінтинг, автоматичний білд та деплой |

---

## 🛡️ 4. Механізми безпеки та етики

1. **Гарантований медичний дисклеймер:**
   Кожна консультаційна відповідь бота апаратно супроводжується обов'язковим попередженням:
   > *ℹ️ Ця інформація має ознайомлювальний характер і не є медичною консультацією. Перед застосуванням проконсультуйтеся з лікарем.*
2. **Червоні прапори (Red Flags):**
   При виявленні тригерів (вагітність, лактація, діти до 3 років, епілепсія, астма, гіпертонія, онкологія, прийом ліків) бот негайно блокує прямий підбір та перенаправляє до спеціаліста або лікаря.
3. **Захист від витоку секретів (`redact`):**
   Усі логи та винятки проходять через регулярні вирази, які маскують токени Telegram, API-ключі Google, паролі до PostgreSQL та Bearer-токени.
4. **Захист від ін'єкцій у діалог:**
   Функція `sanitize_dialogue_text()` усуває невидимі Unicode-символи нульової ширини та підроблені мітки ролей (`Assistant:`, `[SYSTEM]`, `Бот:`).

---

## 🎨 5. Інтеграція стікерпаку (aromaaitgbot)

Для створення природного та живого спілкування в бота інтегровано фірмовий стікерпак [@aromaaitgbot](https://t.me/addstickers/aromaaitgbot):
* **Короткі питання:** бот періодично супроводжує короткі відповіді тематичним стікером.
* **Привітання та подяки:** миттєва відповідь стікером на репліки на кшталт *"привіт"*, *"дякую"*, *"супер"*, що заощаджує виклики до LLM.
* **Реакція на вхідні стікери:** бот відповідає взаємним стікером зі свого паку.

---

## 🚀 6. Швидкий старт (Local Development)

### Вимоги:
* Python 3.12 або 3.13
* PostgreSQL 15+ з увімкненим розширенням `pgvector`

### Кроки встановлення:

```bash
# 1. Клонувати репозиторій
git clone https://github.com/AriSnowie97/tg-bot-doterra-ai-agent.git
cd tg-bot-doterra-ai-agent

# 2. Створити та активувати віртуальне середовище
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Встановити залежності
pip install -r requirements.txt
pip install pytest

# 4. Налаштувати змінні оточення
# Створіть файл .env на основі прикладу нижче
```

### Конфігурація `.env`:
```ini
BOT_TOKEN=123456789:AA...your_bot_token
DATABASE_URL=postgresql://user:pass@localhost:5432/doterra_db
GEMINI_API_KEY=AIzaSy...your_gemini_key
ADMIN_IDS=12345678,87654321
CHANNEL_ID=@your_channel
WEBAPP_URL=https://arisnowie97.github.io/tg-bot-doterra-ai-agent/

# Налаштування стікерів (опціонально)
STICKER_SET_NAME=aromaaitgbot
STICKER_PROB_SHORT_QUESTION=0.35
STICKER_PROB_CASUAL=0.65
```

---

## 🧪 7. Запуск автотестів

У проекті реалізовано набір модульних тестів для перевірки безпеки, класифікації намірів та фільтрації:

```bash
pytest tests/ -v
```

**Покриття тестів (61 тест):**
* `test_safety.py` — маскування секретів, санітизація ролей, обробка помилок.
* `test_specialist.py` — детекція скарг на здоров'я, червоні прапори, дисклеймер.
* `test_stickers.py` — класифікація коротких питань, реакцій, вибір стікерів за емодзі.

---

## 📊 8. Експериментальна частина (Дипломні бенчмарки)

Для наукової частини дипломної роботи реалізовано модуль оцінки `eval/`:
* **Метрики безпеки (Safety Benchmark):** оцінка частки коректно перехоплених скарг та червоних прапорів.
* **Метрики RAG (Retrieval Benchmark):** оцінка точності пошуку чанків (Recall@K, MRR).
* **Аналітика фідбеку:** аналіз реальних оцінок користувачів 👍 / 👎 за типами продукції.

Детальні результати та графіки експериментів наведені у [docs/DIPLOMA_RESEARCH.md](docs/DIPLOMA_RESEARCH.md).

---

## 📄 Ліцензія
Проект розповсюджується під ліцензією [MIT](LICENSE).
