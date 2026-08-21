import os
import asyncio
from dotenv import load_dotenv
import glob
import sys

# 1. Завантажуємо .env перед імпортом
load_dotenv()

# 2. Виправляємо кодування для консолі Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ТЕПЕР імпортуємо провайдер, коли змінні вже завантажені
from src.LLMProvider.GeminiFlashProvider import GeminiFlashProvider
from google.genai import types

TEMPLATE = """
![doTERRA Product](Тут_буде_офіційне_фото_після_завантаження_через_бот)

# Назва Продукту

**Категорія:** Назва категорії (наприклад: Ефірні Олії, БАДи, Догляд за собою, Товари для дому, Дифузори, Набори)

**Тип:** Уточнення (наприклад: Ефірна олія, Капсули, Лосьйон тощо)

**Посилання:** https://www.doterra.com/US/en/p/тут-посилання-на-продукт

---

## Короткий опис

👑 Основна перевага 1
👑 Основна перевага 2
👑 Основна перевага 3

## Склад та ключові інгредієнти

▫️ Інгредієнт 1
▫️ Інгредієнт 2

## Показання

🔹 Коли та для чого використовувати

## Спосіб застосування

🔹 Інструкція 1
🔹 Інструкція 2

## Сумісність з іншими продуктами doTERRA

🔹 З чим можна поєднувати

## Цікаві факти

👑 Факт 1
👑 Факт 2

## Застереження

> ⚠️ Можлива чутливість шкіри. Зберігати в недоступному для дітей місці. Якщо ви вагітні, годуєте грудьми або перебуваєте під наглядом лікаря, проконсультуйтеся з ним. Уникайте контакту з очима, внутрішнім вухом та чутливими ділянками.

#хештег1 #хештег2 #дотерра
"""

PROMPT = f"""
У мене є документ про продукт doTERRA. Я хочу, щоб ти переписав його СУВОРО за наступним шаблоном:

{TEMPLATE}

ПРАВИЛА:
1. Збережи всі важливі дані з оригінального файлу.
2. Якщо в оригіналі є розділи, яких немає в шаблоні (наприклад, "Вплив на фізичне тіло", "Дослідження", "Дозування" тощо), додай їх в самий кінець документа ПІСЛЯ шаблону, але перед хештегами, під заголовком "## Додаткова інформація". 
3. Не втрачай дані! Просто перерозподіли їх у правильні розділи шаблону. Якщо щось не підходить - в кінець у "## Додаткова інформація".
4. Відповідай ТІЛЬКИ готовим markdown текстом, без вступних слів (без "Ось ваш текст" тощо). Без блоків коду ```markdown на початку, просто чистий текст.
5. Завжди залишай картинку `![doTERRA Product](...)` на самому початку (або використай існуючу з оригінального файлу, якщо вона там є).
"""

async def process_file(provider, filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        print(f"Обробка {filepath}...")
        
        # Перевірка чи файл вже відповідає шаблону (проста евристика)
        if "## Короткий опис" in content and "## Застереження" in content and "## Вплив на фізичне тіло" not in content:
            print(f"Skipping {filepath} - looks already formatted")
            return
            
        full_prompt = f"{PROMPT}\n\nОСЬ ОРИГІНАЛЬНИЙ ТЕКСТ:\n\n{content}"
        
        response = await provider.generate_content(
            content=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
            )
        )
        
        new_content = response.text.strip()
        if new_content.startswith("```markdown"):
            new_content = new_content[11:]
        if new_content.startswith("```"):
            new_content = new_content[3:]
        if new_content.endswith("```"):
            new_content = new_content[:-3]
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content.strip() + "\n")
            
        print(f"Успішно оновлено {filepath}")
    except Exception as e:
        print(f"Помилка в {filepath}: {e}")

async def main():
    provider = GeminiFlashProvider()
    
    docs = glob.glob("src/content/docs/*.md")
    products = glob.glob("src/content/products/*.md")
    
    all_files = docs + products
    print(f"Знайдено {len(all_files)} файлів.")
    
    for f in all_files:
        await process_file(provider, f)

if __name__ == "__main__":
    asyncio.run(main())
