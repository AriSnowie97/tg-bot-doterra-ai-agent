"""
Виявлення та формування посилань на продукти/статті для кнопок у Telegram Mini App.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Кеш каталогу продуктів та пошукового індексу
_PRODUCT_SEARCH_INDEX: list[tuple[int, re.Pattern, str, str, re.Pattern | None]] | None = None
_CATALOG_DICT: dict[str, str] | None = None

# Службові матеріали бази знань (папка content/books: довідники, правила безпеки, логіка опитування
# та маршрутизації бота тощо). Це не статті про продукти — бот не повинен давати на них кнопки.
_INTERNAL_KB_SLUGS_FALLBACK: frozenset[str] = frozenset({
    "01-oils-safety-reference",
    "02-emotional-themes-map",
    "03-intake-flow-and-routing",
    "04-modern-essentials-supplement",
    "05-azbuka-supplement",
    "06-aromalogiya-supplement",
})
_INTERNAL_KB_SLUGS: frozenset[str] | None = None


def _normalize_slug(slug: str) -> str:
    """Приводить slug до єдиного вигляду (нижній регістр, дефіси замість підкреслень)."""
    s = (slug or "").strip().lower().lstrip("#/")
    if s.startswith("article/"):
        s = s[len("article/"):]
    return re.sub(r"[\s_]+", "-", s).strip("-")


def _load_internal_kb_slugs() -> frozenset[str]:
    """Slugs усіх файлів із content/books (та fallback-список), які не є статтями про продукти."""
    global _INTERNAL_KB_SLUGS
    if _INTERNAL_KB_SLUGS is not None:
        return _INTERNAL_KB_SLUGS
    slugs = set(_INTERNAL_KB_SLUGS_FALLBACK)
    books_dir = Path(__file__).resolve().parent.parent / "content" / "books"
    if books_dir.is_dir():
        for p in books_dir.rglob("*.md"):
            slugs.add(_normalize_slug(p.stem))
    _INTERNAL_KB_SLUGS = frozenset(slugs)
    return _INTERNAL_KB_SLUGS


def is_internal_kb_slug(slug: str) -> bool:
    """True, якщо slug — службовий матеріал бази знань, а не стаття про продукт."""
    return _normalize_slug(slug) in _load_internal_kb_slugs()

# Базовий словник канонічних відповідностей для популярних олій та сумішей
# (дозволяє знаходити олії навіть при відмінках української мови, наприклад "лаванди", "м'яти", "кедра")
_CANONICAL_OIL_MAP: dict[str, dict[str, any]] = {
    "lavender": {
        "name": "Лаванда",
        "stems": [r"лаванд", r"lavender"],
        "avoid_context": r"лавандов\w*\s+курт\w*|курт\w*\s+лавандов\w*",
    },
    "peppermint": {
        "name": "М'ята перцева",
        "stems": [r"перцев\w*\s+м['’`]?ят", r"м['’`]?ят\w*\s+перцев", r"м['’`]?ят", r"peppermint"],
    },
    "lemon": {
        "name": "Лимон",
        "stems": [r"лимон", r"lemon"],
    },
    "tea-tree": {
        "name": "Чайне дерево",
        "stems": [r"чайн\w*\s+дерев", r"мелалеук", r"tea tree", r"melaleuca"],
    },
    "frankincense": {
        "name": "Ладан",
        "stems": [r"ладан", r"босвелі", r"frankincense"],
    },
    "wild-orange": {
        "name": "Дикий апельсин",
        "stems": [r"дик\w*\s+апельсин", r"апельсин", r"wild orange"],
    },
    "oregano": {
        "name": "Орегано",
        "stems": [r"орегано", r"материнк"],
    },
    "eucalyptus": {
        "name": "Евкаліпт",
        "stems": [r"евкаліпт", r"eucalyptus"],
    },
    "rosemary": {
        "name": "Розмарин",
        "stems": [r"розмарин", r"rosemary"],
    },
    "cedarwood": {
        "name": "Кедр",
        "stems": [r"кедр", r"cedarwood"],
    },
    "roman-chamomile": {
        "name": "Римська ромашка",
        "stems": [r"римськ\w*\s+ромашк", r"ромашк", r"chamomile"],
    },
    "copaiba": {
        "name": "Копайба",
        "stems": [r"копайб", r"copaiba"],
    },
    "bergamot": {
        "name": "Бергамот",
        "stems": [r"бергамот", r"bergamot"],
    },
    "clary-sage": {
        "name": "Шавлія",
        "stems": [r"мускатн\w*\s+шавлі", r"шавлі", r"clary sage"],
    },
    "clove": {
        "name": "Гвоздика",
        "stems": [r"гвоздик", r"clove"],
    },
    "ginger": {
        "name": "Імбир",
        "stems": [r"імбир", r"ginger"],
    },
    "grapefruit": {
        "name": "Грейпфрут",
        "stems": [r"грейпфрут", r"grapefruit"],
    },
    "patchouli": {
        "name": "Пачулі",
        "stems": [r"пачул", r"patchouli"],
    },
    "geranium": {
        "name": "Герань",
        "stems": [r"геран", r"geranium"],
    },
    "ylang-ylang": {
        "name": "Іланг-іланг",
        "stems": [r"іланг[- ]?іланг", r"іланг", r"ylang"],
    },
    "vetiver": {
        "name": "Ветивер",
        "stems": [r"ветив", r"ветів", r"vetiver"],
    },
    "marjoram": {
        "name": "Майоран",
        "stems": [r"майоран", r"marjoram"],
    },
    "thyme": {
        "name": "Чебрець",
        "stems": [r"чебрец", r"тім['’`]?ян", r"thyme"],
    },
    "basil": {
        "name": "Базилік",
        "stems": [r"базилік", r"basil"],
    },
    "cypress": {
        "name": "Кипарис",
        "stems": [r"кипарис", r"cypress"],
    },
    "fennel-sweet": {
        "name": "Фенхель",
        "stems": [r"фенхел", r"fennel"],
    },
    "helichrysum": {
        "name": "Безсмертник",
        "stems": [r"безсмертник", r"helichrysum"],
    },
    "juniper-berry": {
        "name": "Ялівець",
        "stems": [r"ялівец", r"ялівц", r"juniper"],
    },
    "lemongrass": {
        "name": "Лемонграс",
        "stems": [r"лемонграс", r"lemongrass"],
    },
    "lime": {
        "name": "Лайм",
        "stems": [r"лайм", r"lime"],
    },
    "myrrh": {
        "name": "Мирра",
        "stems": [r"мирр", r"myrrh"],
    },
    "sandalwood": {
        "name": "Сандал",
        "stems": [r"сандал", r"sandalwood"],
    },
    "spearmint": {
        "name": "Садова м'ята",
        "stems": [r"садов\w*\s+м['’`]?ят", r"зелен\w*\s+м['’`]?ят", r"spearmint"],
    },
    "tangerine": {
        "name": "Мандарин",
        "stems": [r"мандарин", r"tangerine"],
    },
    "wintergreen": {
        "name": "Вінтергрін",
        "stems": [r"вінтергрін", r"грушанк", r"wintergreen"],
    },
    "black-pepper": {
        "name": "Чорний перець",
        "stems": [r"чорн\w*\s+перец", r"black pepper"],
    },
    "cardamom": {
        "name": "Кардамон",
        "stems": [r"кардамон", r"cardamom"],
    },
    "cinnamon-bark": {
        "name": "Кориця",
        "stems": [r"кориц", r"cinnamon"],
    },
    "coriander": {
        "name": "Коріандр",
        "stems": [r"коріандр", r"coriander"],
    },
    "cilantro": {
        "name": "Кінза",
        "stems": [r"кінз", r"cilantro"],
    },
    "cassia": {
        "name": "Касія",
        "stems": [r"касі", r"cassia"],
    },
    "arborvitae": {
        "name": "Туя",
        "stems": [r"туя", r"туї", r"туєю", r"arborvitae"],
    },
    "blue-tansy": {
        "name": "Блакитна пижма",
        "stems": [r"пижм", r"blue tansy"],
    },
    "petitgrain": {
        "name": "Петитгрейн",
        "stems": [r"петитгрейн", r"petitgrain"],
    },
    "neroli-touch": {
        "name": "Неролі",
        "stems": [r"нерол", r"neroli"],
    },
    "rose": {
        "name": "Троянда",
        "stems": [r"троянд", r"роза", r"rose"],
    },
    "jasmine": {
        "name": "Жасмин",
        "stems": [r"жасмин", r"jasmine"],
    },
    "magnolia-touch": {
        "name": "Магнолія",
        "stems": [r"магнолі", r"magnolia"],
    },
    "madagascar-vanilla": {
        "name": "Мадагаскарська ваніль",
        "stems": [r"ваніл", r"vanilla"],
    },
    "melissa": {
        "name": "Меліса",
        "stems": [r"меліс", r"melissa"],
    },
    # Фірмові суміші doTERRA:
    "doterra-serenity-softgels": {
        "name": "Serenity Softgels",
        "stems": [r"serenity\s+softgels", r"капсул\w*\s+serenity", r"капсул\w*\s+сереніті"],
    },
    "doterra-serenity": {
        "name": "Serenity",
        "stems": [r"serenity", r"сереніті", r"серенити"],
    },
    "on-guard": {
        "name": "On Guard",
        "stems": [r"on\s*guard", r"он\s*гард", r"онгард"],
    },
    "deep-blue": {
        "name": "Deep Blue",
        "stems": [r"deep\s*blue", r"діп\s*блю", r"дип\s*блю"],
    },
    "doterra-breathe": {
        "name": "Breathe",
        "stems": [r"breathe", r"респіраторн\w*\s+суміш"],
    },
    "doterra-balance-fixed": {
        "name": "Balance",
        "stems": [r"balance", r"суміш\w*\s+баланс"],
    },
    "adaptiv": {
        "name": "Adaptiv",
        "stems": [r"adaptiv", r"адаптів", r"адаптив"],
    },
    "digestzen": {
        "name": "DigestZen",
        "stems": [r"digestzen", r"дайджестзен", r"зенджест", r"зенеджест"],
    },
    "aromatouch": {
        "name": "AromaTouch",
        "stems": [r"aromatouch", r"арома\s*тач"],
    },
    "citrus-bliss": {
        "name": "Citrus Bliss",
        "stems": [r"citrus\s*bliss", r"цитрус\s*блісс"],
    },
    "elevation": {
        "name": "Elevation",
        "stems": [r"elevation", r"елевейшн"],
    },
    "purify": {
        "name": "Purify",
        "stems": [r"purify", r"п['’`]?юріфай"],
    },
    "zendocrine": {
        "name": "Zendocrine",
        "stems": [r"zendocrine", r"зендокрин"],
    },
    "calmer": {
        "name": "Calmer",
        "stems": [r"calmer", r"калмер", r"дитяч\w*\s+суміш\w*\s+для\s+сну"],
    },
    "thinker": {
        "name": "Thinker",
        "stems": [r"thinker", r"тінкер"],
    },
    "rescuer": {
        "name": "Rescuer",
        "stems": [r"rescuer", r"рескьюер", r"рескюер"],
    },
    "steady": {
        "name": "Steady",
        "stems": [r"steady", r"стеді"],
    },
    "stronger": {
        "name": "Stronger",
        "stems": [r"stronger", r"стронгер"],
    },
    "tamer": {
        "name": "Tamer",
        "stems": [r"tamer", r"теймер"],
    },
    "brave": {
        "name": "Brave",
        "stems": [r"brave", r"брейв"],
    },
    "terrashield": {
        "name": "TerraShield",
        "stems": [r"terrashield", r"террашилд"],
    },
    "pasttense": {
        "name": "PastTense",
        "stems": [r"pasttense", r"пасттенс"],
    },
    "clarycalm": {
        "name": "ClaryCalm",
        "stems": [r"clarycalm", r"клерікалм"],
    },
    "ddr-prime-cellular-complex-15": {
        "name": "DDR Prime",
        "stems": [r"ddr\s*prime", r"ддр\s*прайм"],
    },
    "metapwr-metabolic-blend": {
        "name": "MetaPWR",
        "stems": [r"metapwr", r"метапавер"],
    },
}


def _load_product_catalog() -> tuple[dict[str, str], list[tuple[int, re.Pattern, str, str, re.Pattern | None]]]:
    """Завантажує та індексує картки продуктів і довідників з бази знань."""
    global _PRODUCT_SEARCH_INDEX, _CATALOG_DICT
    if _PRODUCT_SEARCH_INDEX is not None and _CATALOG_DICT is not None:
        return _CATALOG_DICT, _PRODUCT_SEARCH_INDEX

    catalog: dict[str, str] = {}
    content_dir = Path(__file__).resolve().parent.parent / "content" / "products"

    if content_dir.is_dir():
        for p in content_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    slug = d.get("slug") or p.stem
                    name = d.get("name_ua")
                    if not name or name.startswith("Категорія:"):
                        name = d.get("name_en") or d.get("name") or p.stem
                    catalog[slug] = re.sub(r"\(.*?\)", "", name).strip()
            except Exception:
                pass

        for p in content_dir.glob("*.md"):
            slug = p.stem.replace("_", "-").lower()
            title = slug.replace("-", " ").title()
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("# "):
                            title = line[2:].strip()
                            break
            except Exception:
                pass
            title = re.sub(r"\s*\((?:чанк|chunk)\s*\d+\)", "", title, flags=re.IGNORECASE)
            title = re.sub(r"#.*", "", title).strip()
            if slug not in catalog or catalog[slug].startswith("Категорія:"):
                catalog[slug] = title

    # Службові матеріали бази знань (книги/довідники/логіка роботи бота) — це не статті про продукти,
    # тому вони ніколи не потрапляють у каталог кнопок.
    for kb_slug in list(catalog):
        if is_internal_kb_slug(kb_slug):
            del catalog[kb_slug]

    # Оновлюємо канонічні назви у словнику каталогу для красивих підписів кнопок
    for slug, meta in _CANONICAL_OIL_MAP.items():
        if slug in catalog or slug.startswith("doterra-"):
            catalog[slug] = meta["name"]
        elif slug not in catalog:
            catalog[slug] = meta["name"]

    items: list[tuple[int, re.Pattern, str, str, re.Pattern | None]] = []
    seen_patterns: set[tuple[str, str]] = set()

    # 1. Додаємо канонічні правила пошуку (пріоритетні)
    for slug, meta in _CANONICAL_OIL_MAP.items():
        disp_name = meta["name"]
        avoid_rgx = re.compile(meta["avoid_context"], re.IGNORECASE) if "avoid_context" in meta else None

        for stem in meta.get("stems", []):
            pattern_str = rf"(?<!\w){stem}[а-яіїєґ]*(?!\w)" if any(c in stem for c in "абвгдеєжзиіїйклмнопрстуфхцчшщьюя") else rf"(?<!\w){stem}(?!\w)"
            key = (slug, pattern_str)
            if key not in seen_patterns:
                seen_patterns.add(key)
                try:
                    rgx = re.compile(pattern_str, re.IGNORECASE)
                    priority = len(stem) * 10
                    # Специфічні складні суміші мають вищий пріоритет
                    if "softgel" in slug or "touch" in slug or "combo" in slug:
                        priority += 50
                    items.append((priority, rgx, disp_name, slug, avoid_rgx))
                except Exception:
                    pass

    # 2. Додаємо всі інші товари з каталогу
    for slug, display_name in catalog.items():
        clean_display = re.sub(r"^(?:d[oō]TERRA)\s+", "", display_name, flags=re.IGNORECASE)
        clean_display = re.sub(r"\s*[—–-].*", "", clean_display).strip()
        clean_display = re.sub(r"\(.*?\)", "", clean_display).strip()

        aliases: set[str] = set()
        slug_words = slug.replace("-", " ").replace("_", " ").strip()
        if len(slug_words) >= 4:
            aliases.add(slug_words)
        if len(clean_display) >= 3:
            aliases.add(clean_display)
        if slug.startswith("doterra-") and len(slug[8:]) >= 4:
            aliases.add(slug[8:].replace("-", " "))

        final_display = clean_display or display_name
        if final_display.startswith("doTERRA ") and len(final_display) > 16:
            final_display = final_display[len("doTERRA "):]

        for alias in aliases:
            pattern_str = rf"(?<!\w){re.escape(alias)}(?!\w)"
            key = (slug, pattern_str)
            if key not in seen_patterns:
                seen_patterns.add(key)
                try:
                    rgx = re.compile(pattern_str, re.IGNORECASE)
                    priority = len(alias)
                    items.append((priority, rgx, final_display, slug, None))
                except Exception:
                    pass

    # Сортуємо за спаданням пріоритету
    items.sort(key=lambda x: x[0], reverse=True)
    _CATALOG_DICT = catalog
    _PRODUCT_SEARCH_INDEX = items
    return _CATALOG_DICT, _PRODUCT_SEARCH_INDEX


# Патерн слів алергії та протипоказань, після яких продукт згадується як заборонений, а не як порада
_ALLERGY_CONTEXT_RE = re.compile(
    r"(?:алергі\w*|алергік|без|протипоказан\w*|виключа\w*)\s+(?:на\s+|для\s+|із\s+)?([a-zA-Zа-яА-ЯіїєґІЇЄҐ]+)",
    re.IGNORECASE,
)


def extract_product_links(text: str, max_links: int = 4) -> list[tuple[str, str]]:
    """Витягує посилання на продукти для створення кнопок Telegram Mini App.
    
    1. Спочатку шукає явні маркдаун-посилання виду [Текст](slug).
    2. Якщо посилань менше ніж max_links — автоматично шукає згадані в тексті продукти з каталогу,
       ігноруючи ті, на які у користувача зазначена алергія чи протипоказання.
    
    Returns:
        Список пар (button_label, clean_slug).
    """
    if not text:
        return []

    catalog, search_index = _load_product_catalog()

    # Виявляємо слова-алергени з контексту (наприклад "алергія на лаванду", "без лаванди")
    excluded_roots = set()
    for m in _ALLERGY_CONTEXT_RE.finditer(text):
        word = m.group(1).lower()
        if len(word) >= 4:
            excluded_roots.add(word[:5])

    pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    raw_links = re.findall(pattern, text)

    result: list[tuple[str, str]] = []
    seen_slugs: set[str] = set()

    for link_text, slug in raw_links:
        slug = slug.strip()
        if not slug or "doterra.com" in slug.lower():
            continue
        clean_slug = slug.lstrip("#/").replace("article/", "")

        # Службові матеріали бази знань (довідники, логіка роботи бота) — не статті про продукти
        if is_internal_kb_slug(clean_slug):
            continue

        # Якщо продукт згадується у контексті алергії — не показуємо для нього кнопку
        if any(root in clean_slug.lower() or root in link_text.lower() for root in excluded_roots):
            continue

        if clean_slug not in seen_slugs:
            seen_slugs.add(clean_slug)
            btn_label = link_text.strip()
            # Нормалізуємо текст кнопки до канонічної назви, якщо це відмінена форма (напр. [лаванди](lavender))
            if clean_slug in catalog:
                canonical = catalog[clean_slug]
                if (btn_label.lower() in canonical.lower() or 
                    canonical.lower().startswith(btn_label.lower()[:4]) or 
                    btn_label.lower() == clean_slug):
                    btn_label = canonical
            result.append((btn_label, clean_slug))

    if len(result) >= max_links:
        return result[:max_links]

    # Шукаємо спочатку в рядках списків/рекомендацій (найрелевантніші)
    bullet_lines = [
        line for line in text.splitlines()
        if re.match(r'^\s*[\u2022\u25cf\u25b6\u25c6\u25c7\u25b8\u2714\u2705\U0001f539\U0001f538\U0001f535\U0001f33f\U0001f4a7\u2014\-*•0-9]\s*', line)
    ]
    target_texts = ["\n".join(bullet_lines), text] if bullet_lines else [text]

    for search_text in target_texts:
        if not search_text.strip():
            continue
        for _, rgx, display_name, slug, avoid_rgx in search_index:
            if slug in seen_slugs:
                continue

            # Пропускаємо продукти, назва або slug яких перетинається з алергеном користувача
            if any(root in display_name.lower() or root in slug.lower() for root in excluded_roots):
                continue

            m = rgx.search(search_text)
            if m:
                # Перевіряємо помилкові спрацьовування (наприклад, "у лавандовій курточці")
                if avoid_rgx and avoid_rgx.search(search_text):
                    continue

                btn_name = display_name
                if btn_name.startswith("doTERRA ") and len(btn_name) > 16:
                    btn_name = btn_name[len("doTERRA "):]
                result.append((btn_name, slug))
                seen_slugs.add(slug)
                if len(result) >= max_links:
                    break
        if len(result) >= max_links:
            break

    return result[:max_links]


def strip_internal_kb_links(text: str) -> str:
    """Повністю прибирає markdown-посилання на службові матеріали бази знань (разом із підписом).

    Так ні Telegram-бот, ні чат Mini App не покажуть кнопку або «висячу» назву довідника/логіки бота.
    """
    if not text:
        return text

    def _repl(m: re.Match) -> str:
        return "" if is_internal_kb_slug(m.group(2)) else m.group(0)

    cleaned = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _repl, text)
    if cleaned == text:
        return text
    # Прибираємо порожні маркери списку та зайві пробіли/порожні рядки, що залишилися після видалення
    cleaned = re.sub(r'(?m)^[ \t]*[\u2022\u25cf\u25b6\u25c6\u25c7\u25b8\U0001f539\U0001f538\U0001f535\-*•][ \t]*(?:\u2014[ \t]*)?$', '', cleaned)
    cleaned = re.sub(r'[ \t]+\n', '\n', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()



def strip_internal_kb_references(content: str) -> str:
    """Прибирає з тексту фрагмента бази знань рядки-«див. також» із посиланнями на службові документи.

    Картки продуктів містять рядки на кшталт `* [Довідник безпеки…](01_oils_safety_reference) — …`.
    Якщо модель їх бачить, вона переказує їх у відповіді як назви довідників і кнопок.
    """
    if not content:
        return content
    kept = []
    for line in content.splitlines():
        links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', line)
        if links and any(is_internal_kb_slug(slug) for _, slug in links):
            continue
        kept.append(line)
    return "\n".join(kept)


def ensure_product_links_in_markdown(text: str, max_links: int = 4) -> str:
    """Гарантує наявність markdown-посилань [Назва](slug) у тексті відповіді.
    
    Якщо LLM згенерувала звичайний текст без квадратних дужок, ця функція акуратно
    обгортає першу згадку кожного рекомендованого продукту у [Назва](slug),
    щоб як веб-чат Mini App, так і Telegram-бот гарантовано створили інтерактивні кнопки.
    """
    if not text:
        return text

    # Якщо посилання вже присутні — нічого не змінюємо
    if re.search(r'\[([^\]]+)\]\(([^)]+)\)', text):
        return text

    detected = extract_product_links(text, max_links=max_links)
    if not detected:
        return text

    catalog, search_index = _load_product_catalog()
    modified_text = text

    for btn_name, slug in detected:
        wrapped = False

        # 1. Спробуємо знайти за канонічними правилами (з урахуванням відмінків)
        if slug in _CANONICAL_OIL_MAP:
            meta = _CANONICAL_OIL_MAP[slug]
            avoid_rgx = re.compile(meta["avoid_context"], re.IGNORECASE) if "avoid_context" in meta else None

            for stem in meta.get("stems", []):
                pattern_str = rf"(?<!\[)\b({stem}[а-яіїєґ]*)\b(?!\])" if any(c in stem for c in "абвгдеєжзиіїйклмнопрстуфхцчшщьюя") else rf"(?<!\[)\b({stem})\b(?!\])"
                try:
                    rgx = re.compile(pattern_str, re.IGNORECASE)
                    m = rgx.search(modified_text)
                    if m:
                        # Перевірка на контекст, що виключає помилкове спрацьовування
                        if avoid_rgx and avoid_rgx.search(m.group(0)):
                            continue
                        modified_text = rgx.sub(rf'[\1]({slug})', modified_text, count=1)
                        wrapped = True
                        break
                except Exception:
                    pass

        if wrapped:
            continue

        # 2. Якщо канонічне правило не спрацювало — шукаємо за точним ім'ям або slug
        search_terms = [btn_name, slug.replace("-", " ")]
        for term in search_terms:
            if not term or len(term) < 3:
                continue
            pattern = re.compile(r'(?<!\[)\b(' + re.escape(term) + r')\b(?!\])', re.IGNORECASE)
            if pattern.search(modified_text):
                modified_text = pattern.sub(rf'[\1]({slug})', modified_text, count=1)
                wrapped = True
                break

    return modified_text
