import os
import re
import pytest
from src.content.parser import DoterraMarkdownParser
from src.agent.prompt import SYSTEM_PROMPT


class TestContentLinks:
    """Перевірка відсутності зовнішніх комерційних посилань на сайт doterra.com."""

    def test_no_doterra_website_hyperlinks_in_markdown(self):
        """Всі MD-файли контенту не повинні містити звичайних посилань на сайт doterra.com."""
        found_links = []
        for root, dirs, files in os.walk("src/content"):
            for f in files:
                if f.endswith(".md"):
                    path = os.path.join(root, f)
                    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                        for line_no, line in enumerate(fp, 1):
                            line_s = line.strip()
                            # Ігноруємо теги зображень на початку для обкладинки Mini App
                            if line_s.startswith("!["):
                                continue
                            if "doterra.com" in line_s:
                                found_links.append((path, line_no, line_s))

        assert not found_links, f"Знайдено посилання на doterra.com у MD-файлах: {found_links}"

    def test_no_doterra_urls_in_json_variants(self):
        """JSON-файли не повинні містити зовнішніх посилань на doterra.com у variants чи research."""
        found_urls = []
        for root, dirs, files in os.walk("src/content"):
            for f in files:
                if f.endswith(".json"):
                    path = os.path.join(root, f)
                    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                        content = fp.read()
                        if "doterra.com" in content:
                            found_urls.append(path)

        assert not found_urls, f"Знайдено doterra.com у JSON-файлах: {found_urls}"

    def test_parser_strips_image_chunks_and_doterra_urls(self):
        """Парсер не повинен створювати окремих чанків із фото-банерами чи посиланнями doterra.com."""
        parser = DoterraMarkdownParser()
        sample_md = (
            "![doTERRA Product](https://www.doterra.com/medias/lavender.png)\n\n"
            "# Тестова Лаванда\n\n"
            "**Категорія:** Ефірні олії\n\n"
            "## Короткий опис\n\n"
            "Чудова олія для сну та розслаблення.\n\n"
            "## Варіанти\n\n"
            "* Посилання на сайт: https://www.doterra.com/US/en/p/lavender-oil\n"
        )
        chunks = parser.parse_text(sample_md, product_slug="test-lavender")

        for c in chunks:
            # Чанк не повинен містити розмітку зображень
            assert "![doTERRA" not in c.content, f"Зображення знайдено в чанку {c.section_key}: {c.content}"
            # Чанк не повинен містити посилання doterra.com
            assert "doterra.com" not in c.content, f"doterra.com знайдено в чанку {c.section_key}: {c.content}"

    def test_system_prompt_forbids_doterra_website_links(self):
        """Системний промпт повинен містити чітку заборону на посилання doterra.com."""
        assert "КАТЕГОРИЧНО ЗАБОРОНЕНО давати посилання на офіційний сайт doterra.com" in SYSTEM_PROMPT

    def test_service_sanitizes_doterra_com_leakage(self):
        """Санітизатор повинен вирізати doterra.com у разі випадкової генерації моделлю."""
        text = "Ось чудова лаванда! Детальніше: https://www.doterra.com/US/en/p/lavender-oil або [Лаванда](lavender)"
        cleaned = re.sub(r"https?://(?:www\.)?doterra\.com[^\s\)]*", "", text)
        assert "doterra.com" not in cleaned
        assert "[Лаванда](lavender)" in cleaned
