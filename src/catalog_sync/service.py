"""
Автоматичний синхронізатор каталогу doTERRA по всіх ринках світу.

Ключові гарантії безпеки:
1. Circuit Breaker по ринках: автоархівація вмикається ТІЛЬКИ якщо успішно відповіли
   >= MIN_HEALTHY_MARKETS ринків (дефолт 3) і кожен повернув >= MIN_PRODUCTS_PER_MARKET товарів.
2. Захист від тимчасового зникнення (missing_streak): товар архівується тільки після
   MISSING_STREAK_THRESHOLD (дефолт 3) повних перевірок поспіль, коли його немає на ЖОДНОМУ
   зі здорових ринків.
3. Захист від масового видалення: якщо кандидатів на архівацію > 10% каталогу (або > 15 шт),
   архівація блокується, а адміну надсилається попередження.
4. Переживає перезбірку контейнера: усі нові/архівовані товари пишуться у PostgreSQL
   (`catalog_overrides` + `knowledge_chunks`), а з флагом `write_files=True` — також
   у `src/content/products/` для автоматичного Pull Request через GitHub Actions.
"""

from __future__ import annotations

import asyncio
import html
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from src.content.parser import DoterraMarkdownParser, slugify
from src.safety import redact

from .markets import GLOBAL_MARKETS, MarketConfig, parse_product_page, scan_market
from .store import (
    delete_catalog_override,
    ensure_catalog_tables,
    get_all_override_states,
    log_sync_run,
    record_missing_streak,
    upsert_catalog_item,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PRODUCTS_DIR = PROJECT_ROOT / "src" / "content" / "products"
PRODUCTS_EN_DIR = PRODUCTS_DIR / "en"

# Параметри безпеки
MIN_PRODUCTS_PER_MARKET = 15
MIN_HEALTHY_MARKETS = 3
MISSING_STREAK_THRESHOLD = 3
MAX_ARCHIVE_RATIO = 0.10
MAX_ARCHIVE_ABSOLUTE = 15
DEFAULT_MAX_NEW_PER_RUN = 15

# Канонічні категорії (ті самі 9, що в Mini App)
CANONICAL_CATEGORIES: dict[str, str] = {
    "Ефірні олії": "Essential Oils",
    "Суміші олій": "Oil Blends",
    "Ролери (Touch)": "Roll-ons (Touch)",
    "Дифузори": "Diffusers",
    "БАДи": "Supplements",
    "Догляд за собою": "Personal Care",
    "Товари для дому": "Home Care",
    "Набори": "Kits & Collections",
    "Сезонна колекція": "Seasonal Collection",
}


def infer_category(slug: str, title: str, url: str = "") -> tuple[str, str]:
    """Визначає канонічну категорію (UA, EN) за назвою/слагом продукту."""
    text = f"{slug} {title} {url}".lower()
    if any(k in text for k in ("diffuser", "humidifier")):
        return "Дифузори", "Diffusers"
    if any(k in text for k in ("touch", "roll-on", "roller")):
        return "Ролери (Touch)", "Roll-ons (Touch)"
    if any(k in text for k in ("holiday", "christmas", "winterberry", "yule", "endless-summer", "limited")):
        return "Сезонна колекція", "Seasonal Collection"
    if any(k in text for k in ("kit", "collection", "bundle", "pack", "trio", "combo")):
        return "Набори", "Kits & Collections"
    if any(k in text for k in ("capsule", "softgel", "supplement", "vitamin", "probiotic", "complex", "beadlet", "chewable", "gum", "protein", "greens", "omega", "vmg", "metapwr", "terrazyme", "llv", "pb-assist", "pb-restore")):
        return "БАДи", "Supplements"
    if any(k in text for k in ("abode", "cleaner", "laundry", "dishwasher", "hand-wash", "sanitizing", "toothpaste", "mouth-rinse", "soap", "dispenser", "tray")):
        return "Товари для дому", "Home Care"
    if any(k in text for k in ("skin", "cream", "serum", "cleanser", "toner", "lotion", "balm", "shampoo", "conditioner", "scrub", "mask", "stick", "deodorant", "ikise", "verage", "spa", "baby", "sunscreen", "ointment", "rub", "wash")):
        return "Догляд за собою", "Personal Care"
    if any(k in text for k in ("blend", "guard", "breathe", "digest", "zengest", "deep-blue", "adaptiv", "serenity", "balance", "aromatouch", "cheer", "console", "forgive", "motivate", "passion", "peace", "intune", "immortelle", "revitazen", "zendocrine", "elevation", "purify", "terrashield", "citrus-bliss", "shinrin")):
        return "Суміші олій", "Oil Blends"
    return "Ефірні олії", "Essential Oils"


def _build_template_card(
    slug: str,
    title: str,
    description: str,
    image_url: str,
    category_ua: str,
    category_en: str,
    markets: list[str],
    source_url: str,
) -> tuple[str, str]:
    """Детермінований фолбек-генератор UA та EN карток у стандарті product_template.md."""
    img_line = f"![doTERRA Product]({image_url})\n\n" if image_url else ""
    markets_str = ", ".join(markets) if markets else "US"
    clean_desc = description.strip() or f"{title} — офіційний продукт doTERRA."

    md_ua = (
        f"{img_line}# {title}\n\n"
        f"**Категорія:** {category_ua}\n\n"
        f"**Тип:** Офіційний продукт doTERRA (ринки: {markets_str})\n\n"
        f"---\n\n"
        f"## Короткий опис\n\n"
        f"👑 {clean_desc}\n"
        f"👑 Підтримка щоденного добробуту та м'якої регуляції стану за стандартом якості CPTG®\n\n"
        f"## Спосіб застосування\n\n"
        f"🔹 Дотримуйтеся інструкції виробника на упаковці продукту\n"
        f"🔹 Для персонального підбору концентрації та способу застосування зверніться до Наталії Котелянської\n\n"
        f"## Застереження\n\n"
        f"> ⚠️ Можлива індивідуальна чутливість. Зберігати в недоступному для дітей місці. "
        f"Якщо ви вагітні, годуєте грудьми або перебуваєте під наглядом лікаря — проконсультуйтеся з ним.\n\n"
        f"#doterra #{slug.replace('-', '')} #новинка\n"
    )

    md_en = (
        f"{img_line}# {title}\n\n"
        f"**Category:** {category_en}\n\n"
        f"**Type:** Official doTERRA Product (markets: {markets_str})\n\n"
        f"---\n\n"
        f"## Short Description\n\n"
        f"👑 {clean_desc}\n"
        f"👑 Supports everyday wellness and gentle balance with CPTG® quality standards\n\n"
        f"## Directions for Use\n\n"
        f"🔹 Follow the official product label instructions\n"
        f"🔹 For personalized concentration and usage guidance, consult Natalia Kotelianska\n\n"
        f"## Precautions\n\n"
        f"> ⚠️ Possible skin sensitivity. Keep out of reach of children. "
        f"If pregnant, nursing, or under a doctor's care, consult your physician.\n\n"
        f"#doterra #{slug.replace('-', '')} #new\n"
    )
    return md_ua, md_en


async def _build_cards_with_llm(
    slug: str,
    meta: dict,
    category_ua: str,
    category_en: str,
    markets: list[str],
) -> tuple[str, str]:
    """Генерує якісні UA + EN картки через Gemini (із безпечним фолбеком на шаблон)."""
    title = meta["title"]
    desc = meta.get("description", "")
    excerpt = meta.get("excerpt", "")
    image_url = meta.get("image_url", "")
    source_url = meta.get("source_url", "")

    has_gemini_key = bool(
        os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY_1") or os.getenv("GOOGLE_API_KEY")
    )
    if not has_gemini_key:
        return _build_template_card(slug, title, desc, image_url, category_ua, category_en, markets, source_url)

    try:
        from google.genai import types
        from src.LLMProvider import GeminiFlashProvider as LLM

        img_prefix = f"![doTERRA Product]({image_url})\n\n" if image_url else ""
        markets_str = ", ".join(markets)
        prompt = (
            f"На основі офіційної сторінки продукту doTERRA створи ДВІ структуровані картки "
            f"(спочатку українською, потім англійською), розділені рівно рядком `===EN_CARD===`.\n\n"
            f"ПРАВИЛА:\n"
            f"1. Вихідна сторінка може бути японською, корейською, іспанською, португальською, німецькою, "
            f"французькою, польською чи іншою мовою. ОБОВ'ЯЗКОВО повністю переклади І ЗАГОЛОВОК (`# ...`), "
            f"І ВЕСЬ ТЕКСТ: перша картка — 100% літературною українською (без ієрогліфів, кани, хангилю, "
            f"іспанських чи англійських речень), друга картка — 100% англійською.\n"
            f"2. Заголовок `# ...` має бути чистим і лаконічним (БЕЗ дописок на кшталт "
            f"`| Aceites esenciales dōTERRA`, `- dōTERRA Product Information`, `| 도테라 에센셜 오일`). "
            f"Брендову назву продукту можна залишити латиницею + українську назву в дужках, якщо доречно.\n"
            f"3. Пиши ТІЛЬКИ факти з наданого тексту, нічого не вигадуй.\n"
            f"4. Фокус — регуляція стану та підтримка добробуту, НІКОЛИ не обіцяй лікування хвороб.\n"
            f"5. Обов'язковий формат заголовку UA:\n"
            f"   # <Чиста назва продукту українською>\n"
            f"   **Категорія:** {category_ua}\n"
            f"   **Тип:** ... (ринки: {markets_str})\n"
            f"   ---\n"
            f"   ## Короткий опис / ## Склад та ключові інгредієнти / ## Спосіб застосування / ## Застереження\n"
            f"6. Обов'язковий формат заголовку EN:\n"
            f"   # <Clean product title in English>\n"
            f"   **Category:** {category_en}\n"
            f"   **Type:** ... (markets: {markets_str})\n"
            f"   ---\n"
            f"   ## Short Description / ## Ingredients & Features / ## Directions for Use / ## Precautions\n"
            f"7. Не додавай теги зображень `![...]` — вони підставляються автоматично.\n\n"
            f"ОФІЦІЙНІ ДАНІ ({source_url}):\n"
            f"Title: {title}\n"
            f"Description: {desc}\n"
            f"Page excerpt: {excerpt[:2200]}"
        )
        resp = await LLM().generate_content(
            prompt,
            types.GenerateContentConfig(temperature=0.2, max_output_tokens=2048),
        )
        raw = (resp.text or "").strip()
        if "===EN_CARD===" in raw:
            ua_part, en_part = raw.split("===EN_CARD===", 1)
            ua_part = re.sub(r"^!\[[^\]]*\]\([^)]*\)\s*", "", ua_part.strip())
            en_part = re.sub(r"^!\[[^\]]*\]\([^)]*\)\s*", "", en_part.strip())
            if len(ua_part) > 120 and len(en_part) > 120:
                return f"{img_prefix}{ua_part}\n", f"{img_prefix}{en_part}\n"
    except Exception as e:
        print(f"[catalog_sync] LLM card build fallback for {slug}: {redact(e)}")

    return _build_template_card(slug, title, desc, image_url, category_ua, category_en, markets, source_url)


_ALIAS_SUFFIX_RE = re.compile(
    r"(?:-(?:calming|springtime|protective|soothing|respiratory|grounding|joyful|restful|"
    r"detoxification|rejuvenating|inspiring|invigorating|encouraging|comforting|reassuring|"
    r"renewing|holiday|seasonal|sunshine|essential-oil|essential|oil|fixed|air-blend|"
    r"metabolic-blend|massage-blend|outback-blend|cellular-complex-15|cellular-complex|"
    r"roll-on|plus|5ml|10ml|15ml|jp|kr|eu|uk|au|nz|za|br|mx|ca|us|sg|il))+|-blend$",
    re.IGNORECASE,
)

# Регіональні назви / варіанти слагов для існуючих статичних продуктів (AU/NZ/ZA/BR/JP/KR/MX -> канон)
_REGIONAL_ALIAS_MAP: dict[str, str] = {
    "on-guard-oil-beadlet": "on-guard-beadlets",
    "on-guard-beadlet": "on-guard-beadlets",
    "clearify": "air-x",
    "air-repair": "air-x",
    "affirm": "align",
    "ascend": "arise",
    "coast": "coastal-escape",
    "deep-blue-touch": "deep-blue",
    "deep-blue-stick": "deep-blue-stick-copaiba",
    "citrusbliss": "citrus-bliss",
    "natures-rx": "natures-rx-collection",
    "ikise-skin-ritual": "ikise-skin-care-collection",
    "ikise-skin-care": "ikise-skin-care-collection",
    "vanilla-dream-lip-balm": "vanilla-dream-restorative-lip-balm",
    "yarrow-pom-active-botanical-nutritive-duo": "yarrow-pom",
    "doterra-kids-oil-collection-kit": "doterra-kids-collection",
    "kids-oil-collection-kit": "kids-collection",
    "doterra-lifelong-vitality-pack-llv": "lifelong-vitality-pack",
    "lifelong-vitality-pack-llv": "lifelong-vitality-pack",
    "zengest": "digestzen",
    "xeo-mega": "eo-mega",
}

_CATEGORY_PREFIX_RE = re.compile(
    r"^(?:body\s+care|sun\s+care|starter\s+kits?|collections?|"
    r"hd\s+clear\s+skin\s+care|d[oō]terra\s+hair\s+care|"
    r"d[oō]terra\s+baby)\s*[—–-]+\s*",
    re.IGNORECASE,
)

_GENERIC_DUP_SLUGS: frozenset[str] = frozenset({
    "body-care",
    "sun-care",
    "starter-kits",
    "collections",
    "essential-skin-care",
    "hd-clear-skin-care",
    "verage-skin-care",
    "veráge-skin-care",
    "doterra-spa",
    "dōterra-spa",
    "doterra-hair-care",
    "dōterra-hair-care",
    "doterra-baby",
})

_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
_CYRILLIC_RE = re.compile(r"[А-Яа-яІіЇїЄєҐґ]")
_FOREIGN_BOILERPLATE_RE = re.compile(
    r"(?:Aceites\s+esenciales|Product\s+Information|도테라|Mezcla\s+de|Difusor\s+Osito|Óleo)",
    re.IGNORECASE,
)
_TITLE_NOISE_RE = re.compile(
    r"\s*(?:\|\s*(?:Aceites\s+esenciales\s+d[oō]TERRA|도테라\s*에센셜\s*오일|d[oō]TERRA\s+Essential\s+Oils)"
    r"|-\s*d[oō]TERRA\s+Product\s+Information).*$",
    re.IGNORECASE,
)


def _clean_product_title(title: str) -> str:
    return _TITLE_NOISE_RE.sub("", (title or "").strip()).strip(" |-")


def _extract_h1_title(md_text: str, fallback: str = "") -> str:
    for line in (md_text or "").splitlines():
        s = line.strip()
        if s.startswith("# "):
            cleaned = _clean_product_title(s[2:])
            if cleaned:
                return cleaned
    return _clean_product_title(fallback)


def _needs_translation(ov: dict) -> bool:
    """Перевіряє, чи містить динамічна картка неперекладений японський/корейський/іспанський або лише англійський текст."""
    t_ua = ov.get("title_ua") or ""
    t_en = ov.get("title_en") or ""
    s_ua = ov.get("short_ua") or ""
    md_ua = ov.get("md_ua") or ""
    md_en = ov.get("md_en") or ""
    if not (md_ua or md_en):
        return False
    combined_titles = f"{t_ua} {t_en}"
    if _CJK_RE.search(combined_titles) or _CJK_RE.search(s_ua) or _CJK_RE.search(md_ua[:600]) or _CJK_RE.search(md_en[:600]):
        return True
    if _FOREIGN_BOILERPLATE_RE.search(combined_titles):
        return True
    # Якщо українська картка взагалі не містить кирилиці в короткому описі (напр., залишився лише англійський опис)
    if s_ua and not _CYRILLIC_RE.search(s_ua):
        return True
    return False


def _canonical_alias(slug: str) -> str:
    """Нормалізує слаг для виявлення дублікатів (напр. adaptiv-touch == adaptiv-touch-calming-blend)."""
    s = slugify(slug).strip().lower()
    if s in _REGIONAL_ALIAS_MAP:
        s = _REGIONAL_ALIAS_MAP[s]
    if s.startswith("doterra-"):
        s = s[len("doterra-"):]
    if s.startswith("adaptive-"):
        s = "adaptiv-" + s[len("adaptive-"):]
    prev = None
    while prev != s:
        prev = s
        s = _ALIAS_SUFFIX_RE.sub("", s).strip("-")
    mapped = _REGIONAL_ALIAS_MAP.get(s, s)
    if mapped.startswith("doterra-"):
        mapped = mapped[len("doterra-"):]
    return mapped


def _compact_alias(slug: str) -> str:
    """Бездефісний ключ канонічного слага (ловить 'citrusbliss' == 'citrus-bliss', 'onguard' == 'on-guard')."""
    return re.sub(r"[^a-z0-9]", "", _canonical_alias(slug))


def _normalize_title_key(title: str) -> str:
    """Нормалізує назву продукту для виявлення дублікатів (прибирає префікси категорій, бренд, дужки)."""
    s = _clean_product_title(title or "")
    # Прибираємо лише префікс категорії перед тире ('Body Care — Fractionated Coconut Oil' -> 'Fractionated Coconut Oil')
    s = _CATEGORY_PREFIX_RE.sub("", s)
    # Якщо залишилося "Назва — підзаголовок" для брендових серій (напр. "Essential Skin Care — Facial Cleanser")
    s = s.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[®™©]", "", s)
    s = re.sub(r"\bd[oō]terra\b", " ", s)
    s = re.sub(r"\bskin\s+care\b", " ", s)
    s = re.sub(r"\b(?:essential\s+oils?|oil|overview)\b", " ", s)
    s = re.sub(r"\b(?:restorative|springtime|invigorating|calming|protective|soothing|respiratory|grounding|digestive|detoxification|refreshing|woodland|holiday|seasonal|active\s+botanical\s+nutritive\s+duo)\b", " ", s)
    # Нормалізуємо діакритику (veráge -> verage)
    s = s.replace("á", "a").replace("ō", "o").replace("é", "e").replace("’", "'")
    s = re.sub(r"[^a-zа-яіїєґ0-9]+", " ", s)
    return " ".join(s.split())


def _line_fingerprint(line: str) -> str:
    """Короткий нормалізований відбиток рядка для перевірки, чи факт уже є у статті."""
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
    s = re.sub(r"[^a-zа-яіїєґ0-9]+", " ", s.lower())
    return " ".join(s.split())


def _split_md_sections(md_text: str) -> tuple[str, list[tuple[str, list[str]]], str]:
    """Розбиває картку продукту на (header_block, [(heading, lines), ...], hashtags_line)."""
    lines = (md_text or "").splitlines()
    hashtags = ""
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].strip().startswith("#") and not lines[-1].strip().startswith("# "):
        # Останній рядок із хештегами (#ефірніолії #дотерра)
        if re.match(r"^(?:#[a-zA-Zа-яА-ЯіїєґІЇЄҐ0-9_]+\s*)+$", lines[-1].strip()):
            hashtags = lines.pop().strip()
            while lines and not lines[-1].strip():
                lines.pop()

    header_lines: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    cur_heading: str | None = None
    cur_body: list[str] = []

    for ln in lines:
        if ln.startswith("## "):
            if cur_heading is not None:
                sections.append((cur_heading, cur_body))
            cur_heading = ln.strip()
            cur_body = []
        elif cur_heading is None:
            header_lines.append(ln)
        else:
            cur_body.append(ln)
    if cur_heading is not None:
        sections.append((cur_heading, cur_body))

    return "\n".join(header_lines).strip(), sections, hashtags


def _norm_heading_key(heading: str) -> str:
    h = heading.lstrip("#").strip().lower()
    mapping = {
        "короткий опис": "desc",
        "опис": "desc",
        "short description": "desc",
        "description": "desc",
        "склад та ключові інгредієнти": "ingredients",
        "склад": "ingredients",
        "composition and key ingredients": "ingredients",
        "ingredients & features": "ingredients",
        "ingredients": "ingredients",
        "показання": "indications",
        "indications": "indications",
        "benefits": "indications",
        "спосіб застосування": "directions",
        "directions for use": "directions",
        "directions": "directions",
        "сумісність з іншими продуктами doterra": "compat",
        "compatibility with other doterra products": "compat",
        "цікаві факти": "facts",
        "interesting facts": "facts",
        "fun facts": "facts",
        "застереження": "cautions",
        "cautions": "cautions",
        "precautions": "cautions",
        "за даними літератури та довідників": "literature",
        "from literature & reference guides": "literature",
    }
    return mapping.get(h, re.sub(r"[^a-zа-яіїєґ0-9]+", "", h))


def _extract_md_image(md_text: str) -> str:
    for ln in (md_text or "").splitlines()[:5]:
        if ln.startswith("![") and "](" in ln:
            url = ln.split("](", 1)[1].split(")", 1)[0].strip()
            low = url.lower()
            if url and not any(b in low for b in ("тут_буде", "new-default-image", "pool=wave0", "-za-en-web.")):
                return url
    return ""


def _merge_markdown_cards(primary_md: str, secondary_md: str) -> tuple[str, int]:
    """Доповнює основну картку унікальною інформацією з дубліката (без повторів).

    Повертає (merged_markdown, count_added_items).
    """
    if not secondary_md or not secondary_md.strip():
        return primary_md, 0
    if not primary_md or not primary_md.strip():
        return secondary_md, 1

    added = 0
    p_header, p_sections, p_tags = _split_md_sections(primary_md)
    _, s_sections, s_tags = _split_md_sections(secondary_md)

    # Якщо в основній картці немає робочого фото, а в дублікаті є — підхоплюємо фото
    if not _extract_md_image(primary_md):
        sec_img = _extract_md_image(secondary_md)
        if sec_img:
            p_header = f"![doTERRA Product]({sec_img})\n\n" + re.sub(
                r"^\s*!\[[^\]]*\]\([^)]*\)\s*", "", p_header
            )
            added += 1

    # Збираємо відбитки всіх уже наявних рядків основної картки
    existing_fps: set[str] = {
        _line_fingerprint(ln)
        for _, body in p_sections
        for ln in body
        if len(_line_fingerprint(ln)) >= 12
    }

    p_idx_by_key = {_norm_heading_key(h): idx for idx, (h, _) in enumerate(p_sections)}

    for s_heading, s_body in s_sections:
        s_key = _norm_heading_key(s_heading)
        # Застереження не дублюємо, якщо вони вже є в основній картці
        if s_key == "cautions" and "cautions" in p_idx_by_key:
            continue

        unique_lines: list[str] = []
        for ln in s_body:
            stripped = ln.strip()
            if not stripped or stripped == "---":
                continue
            fp = _line_fingerprint(stripped)
            if len(fp) < 12:
                continue
            # Перевіряємо на точний збіг або повне входження у вже наявний рядок
            if any(fp == ex or fp in ex or ex in fp for ex in existing_fps):
                continue
            unique_lines.append(stripped)
            existing_fps.add(fp)

        if not unique_lines:
            continue

        if s_key in p_idx_by_key:
            idx = p_idx_by_key[s_key]
            heading, body = p_sections[idx]
            while body and not body[-1].strip():
                body.pop()
            body.extend(unique_lines)
            p_sections[idx] = (heading, body)
        else:
            # Вставляємо нову секцію перед застереженнями/літературою або в кінець
            p_sections.append((s_heading, [""] + unique_lines))
            p_idx_by_key[s_key] = len(p_sections) - 1
        added += len(unique_lines)

    # Об'єднуємо хештеги без дублікатів
    tags_list: list[str] = []
    for raw_tags in (p_tags, s_tags):
        for t in raw_tags.split():
            if t.startswith("#") and t.lower() not in {x.lower() for x in tags_list}:
                tags_list.append(t)

    parts = [p_header]
    for heading, body in p_sections:
        clean_body = "\n".join(body).strip()
        parts.append(f"{heading}\n\n{clean_body}" if clean_body else heading)
    if tags_list:
        parts.append(" ".join(tags_list))

    return "\n\n".join(p for p in parts if p).strip() + "\n", added


def _get_static_product_slugs() -> dict[str, Path]:
    """Повертає {slug: path} для всіх статичних карток у src/content/products/."""
    res: dict[str, Path] = {}
    if PRODUCTS_DIR.exists():
        for p in sorted(PRODUCTS_DIR.glob("*.md")):
            res[slugify(p.stem)] = p
    return res


def _vectorize_markdown_to_rag(slug: str, md_ua: str) -> None:
    """Парсить нову UA-картку в чанки та одразу додає її у `knowledge_chunks` для RAG."""
    if not (os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")):
        return
    try:
        from src.storage.storage import bulk_upsert_chunks, creating_table_for_chunks

        parser = DoterraMarkdownParser()
        tmp_path = PROJECT_ROOT / "data" / f".tmp_sync_{slug}.md"
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            tmp_path.write_text(md_ua, encoding="utf-8")
            chunks = parser.parse_file(tmp_path)
            for c in chunks:
                c.product_slug = slug
            if chunks:
                creating_table_for_chunks()
                bulk_upsert_chunks([c.to_dict() for c in chunks], delete_orphans=False)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
    except Exception as e:
        print(f"[catalog_sync] RAG vectorize skipped for {slug}: {redact(e)}")


def _extract_short(md_text: str) -> str:
    for line in md_text.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "![", "**Категорія", "**Category", "**Тип", "**Type", "---", ">")):
            continue
        return s[:117] + "..." if len(s) > 120 else s
    return ""


async def run_catalog_sync(
    markets: tuple[MarketConfig, ...] | list[MarketConfig] = GLOBAL_MARKETS,
    *,
    write_files: bool = False,
    save_db: bool = True,
    dry_run: bool = False,
    max_new: int = DEFAULT_MAX_NEW_PER_RUN,
    progress_callback: Callable[[str], None] | None = None,
) -> dict:
    """Повний цикл глобальної автосинхронізації каталогу doTERRA по всіх ринках.

    Returns:
        Словник зі статистикою та списками доданих/відновлених/архівованих продуктів.
    """
    def _log(msg: str) -> None:
        print(f"[catalog_sync] {msg}", flush=True)
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception:
                pass

    report: dict = {
        "markets_checked": len(markets),
        "markets_healthy": 0,
        "healthy_market_codes": [],
        "total_discovered": 0,
        "added": [],
        "restored": [],
        "archived": [],
        "archive_skipped_reason": "",
        "errors": [],
    }

    if save_db and not dry_run:
        ensure_catalog_tables()

    # 1. Скануємо всі ринки паралельно (до 6 потоків — ввічливо до doterra.com)
    _log(f"🌍 Сканую {len(markets)} світових ринків doTERRA...")
    market_results: dict[str, dict[str, str]] = {}

    def _scan_one(m: MarketConfig) -> tuple[str, dict[str, str]]:
        return m.code, scan_market(m)

    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(_scan_one, m): m for m in markets}
        for fut in as_completed(futs):
            m = futs[fut]
            try:
                code, found = fut.result()
                market_results[code] = found
                if len(found) >= MIN_PRODUCTS_PER_MARKET:
                    report["healthy_market_codes"].append(code)
            except Exception as e:
                report["errors"].append(f"{m.code}: {redact(e)}")

    report["markets_healthy"] = len(report["healthy_market_codes"])

    # Об'єднуємо всі знайдені товари: slug -> {markets: [...], urls: {code: url}}
    # Порядок ринків зберігаємо як у GLOBAL_MARKETS (US перший!)
    discovered: dict[str, dict] = {}
    for m in markets:
        for slug, url in market_results.get(m.code, {}).items():
            entry = discovered.setdefault(slug, {"markets": [], "urls": {}})
            entry["markets"].append(m.code)
            entry["urls"][m.code] = url

    report["total_discovered"] = len(discovered)
    _log(
        f"✅ Перевірено ринків: {report['markets_healthy']}/{report['markets_checked']} здорових, "
        f"знайдено унікальних товарів: {len(discovered)}"
    )

    static_slugs = _get_static_product_slugs()
    db_states = get_all_override_states() if save_db else {}

    known_active: set[str] = set(static_slugs.keys())
    for slug, st in db_states.items():
        if st["status"] == "archived":
            known_active.discard(slug)
        elif st["status"] == "active":
            known_active.add(slug)

    # 2. Відновлення раніше архівованих товарів, якщо вони знову з'явилися в продажу
    for slug, st in db_states.items():
        if st["status"] == "archived" and slug in discovered:
            if not dry_run and save_db:
                upsert_catalog_item({
                    "slug": slug,
                    "status": "active",
                    "markets": discovered[slug]["markets"],
                    "change_type": "returned",
                })
            report["restored"].append({"slug": slug, "markets": discovered[slug]["markets"]})

    # 3. Пошук та автоматичне додавання НОВИНОК (із захистом від дублікатів-синонімів та по назві)
    known_aliases = {_canonical_alias(k) for k in known_active}
    known_compact = {_compact_alias(k) for k in known_active}
    known_static_titles: set[str] = set()
    for p in static_slugs.values():
        try:
            t = _extract_h1_title(p.read_text(encoding="utf-8"), p.stem)
            nt = _normalize_title_key(t)
            if nt:
                known_static_titles.add(nt)
        except Exception:
            pass
    restored_set = {r["slug"] for r in report["restored"]}
    new_slugs = [
        s for s in discovered.keys()
        if s not in known_active
        and _canonical_alias(s) not in known_aliases
        and _compact_alias(s) not in known_compact
        and s not in restored_set
    ]
    # Пріоритезуємо новинки, що є на US або на >= 2 ринках
    new_slugs.sort(key=lambda s: (0 if "US" in discovered[s]["markets"] else 1, -len(discovered[s]["markets"]), s))

    for slug in new_slugs[:max_new]:
        info = discovered[slug]
        # Беремо US URL, якщо є, інакше перший за пріоритетом
        primary_code = "US" if "US" in info["urls"] else info["markets"][0]
        primary_url = info["urls"][primary_code]

        meta = await asyncio.to_thread(parse_product_page, primary_url)
        if not meta:
            continue

        # Додаткова перевірка на дублікат за нормалізованою назвою перед створенням нової картки
        cand_title_key = _normalize_title_key(meta["title"])
        if cand_title_key and cand_title_key in known_static_titles:
            _log(f"⏭️ Пропущено дублікат за назвою: {slug} ({meta['title']})")
            continue

        cat_ua, cat_en = infer_category(slug, meta["title"], primary_url)
        md_ua, md_en = await _build_cards_with_llm(slug, meta, cat_ua, cat_en, info["markets"])
        title_ua = _extract_h1_title(md_ua, meta["title"])
        title_en = _extract_h1_title(md_en, meta["title"])
        if _normalize_title_key(title_en) in known_static_titles:
            _log(f"⏭️ Пропущено дублікат після перекладу: {slug} ({title_en})")
            continue
        known_aliases.add(_canonical_alias(slug))
        known_compact.add(_compact_alias(slug))
        if cand_title_key:
            known_static_titles.add(cand_title_key)

        item = {
            "slug": slug,
            "title_ua": title_ua,
            "title_en": title_en,
            "category_ua": cat_ua,
            "category_en": cat_en,
            "short_ua": _extract_short(md_ua),
            "short_en": _extract_short(md_en),
            "image_url": meta.get("image_url", ""),
            "md_ua": md_ua,
            "md_en": md_en,
            "markets": info["markets"],
            "source_url": primary_url,
            "change_type": "new",
        }

        if not dry_run:
            if save_db:
                upsert_catalog_item(item)
                await asyncio.to_thread(_vectorize_markdown_to_rag, slug, md_ua)
            if write_files:
                PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)
                PRODUCTS_EN_DIR.mkdir(parents=True, exist_ok=True)
                (PRODUCTS_DIR / f"{slug}.md").write_text(md_ua, encoding="utf-8")
                (PRODUCTS_EN_DIR / f"{slug}.md").write_text(md_en, encoding="utf-8")

        report["added"].append({
            "slug": slug,
            "title": title_ua,
            "category": cat_ua,
            "markets": info["markets"],
            "has_image": bool(meta.get("image_url")),
        })

    # 3.5. Доперекладаємо наявні динамічні картки з іноземних ринків (JP/KR/MX/BR/EN-only)
    if not dry_run and save_db:
        report["translated"] = await retranslate_existing_overrides(limit=15)
    else:
        report["translated"] = []

    # 3.6. Автоматична перевірка на дублікати: доповнення унікальної інфи + видалення дублів
    dedup_summary: dict = {"merged": [], "removed": []}
    if save_db:
        dyn_dedup = await asyncio.to_thread(deduplicate_dynamic_overrides, dry_run)
        dedup_summary["merged"].extend(dyn_dedup.get("merged", []))
        dedup_summary["removed"].extend(dyn_dedup.get("removed", []))
    if write_files:
        st_dedup = await asyncio.to_thread(deduplicate_static_products, dry_run)
        dedup_summary["merged"].extend(st_dedup.get("merged", []))
        dedup_summary["removed"].extend(st_dedup.get("removed", []))
    report["deduped"] = dedup_summary

    # 4. Безпечна автоархівація товарів, які зникли з УСІХ здорових ринків
    # Circuit Breaker 1: недостатньо здорових ринків -> не чіпаємо існуючий каталог
    if report["markets_healthy"] < MIN_HEALTHY_MARKETS:
        report["archive_skipped_reason"] = (
            f"Автоархівацію пропущено (здорових ринків {report['markets_healthy']} < {MIN_HEALTHY_MARKETS})"
        )
    else:
        missing_now = [s for s in known_active if s not in discovered]
        # Оновлюємо streak для присутніх товарів (скидаємо в 0 якщо був > 0)
        if not dry_run and save_db:
            for slug, st in db_states.items():
                if st["status"] == "active" and st["missing_streak"] > 0 and slug in discovered:
                    record_missing_streak(slug, 0, archive=False)

        # Рахуємо кандидатів, які досягли MISSING_STREAK_THRESHOLD
        to_archive: list[str] = []
        to_increment: list[tuple[str, int]] = []
        for slug in missing_now:
            prev_streak = db_states.get(slug, {}).get("missing_streak", 0)
            new_streak = prev_streak + 1
            if new_streak >= MISSING_STREAK_THRESHOLD:
                to_archive.append(slug)
            else:
                to_increment.append((slug, new_streak))

        # Circuit Breaker 2: захист від масового видалення (>10% або >15 шт за прогон)
        max_allowed = min(MAX_ARCHIVE_ABSOLUTE, max(3, int(len(known_active) * MAX_ARCHIVE_RATIO)))
        if len(to_archive) > max_allowed:
            report["archive_skipped_reason"] = (
                f"Заблоковано масове видалення ({len(to_archive)} > ліміт {max_allowed}) — перевірте сайти doTERRA"
            )
        else:
            if not dry_run and save_db:
                for slug, streak in to_increment:
                    record_missing_streak(slug, streak, archive=False)
                for slug in to_archive:
                    record_missing_streak(slug, MISSING_STREAK_THRESHOLD, archive=True)
            if not dry_run and write_files:
                for slug in to_archive:
                    for folder in (PRODUCTS_DIR, PRODUCTS_EN_DIR):
                        p = folder / f"{slug}.md"
                        if p.exists():
                            p.unlink()
            report["archived"] = to_archive

    if save_db and not dry_run:
        log_sync_run(
            markets_checked=report["markets_checked"],
            markets_healthy=report["markets_healthy"],
            added=len(report["added"]),
            restored=len(report["restored"]),
            archived=len(report["archived"]),
            notes=report["archive_skipped_reason"],
        )

    return report


_MARKET_LABELS_UA: dict[str, str] = {
    "US": "США",
    "CA": "Канада",
    "EU": "Європа",
    "UK": "Велика Британія",
    "DE": "Німеччина",
    "FR": "Франція",
    "IT": "Італія",
    "ES": "Іспанія",
    "PL": "Польща",
    "AU": "Австралія",
    "NZ": "Нова Зеландія",
    "ZA": "ПАР",
    "IL": "Ізраїль",
    "SG": "Сінгапур",
    "JP": "Японія",
    "KR": "Корея",
    "BR": "Бразилія",
    "MX": "Мексика",
}


async def retranslate_existing_overrides(limit: int = 15) -> list[str]:
    """Автоматично перекладає українською та англійською існуючі динамічні позиції з JP/KR/MX/BR/EN-only."""
    from .store import get_catalog_overrides

    has_gemini_key = bool(
        os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY_1") or os.getenv("GOOGLE_API_KEY")
    )
    if not has_gemini_key:
        return []

    active_ov, _ = get_catalog_overrides(force_refresh=True)
    static_aliases = {_canonical_alias(s) for s in _get_static_product_slugs().keys()}
    translated_slugs: list[str] = []

    for ov in active_ov:
        if len(translated_slugs) >= limit:
            break
        ov_slug = ov["slug"]
        if _canonical_alias(ov_slug) in static_aliases:
            continue
        if not _needs_translation(ov):
            continue

        raw_title = ov.get("title_en") or ov.get("title_ua") or ov_slug
        raw_desc = ov.get("short_en") or ov.get("short_ua") or ""
        raw_excerpt = (ov.get("md_en") or ov.get("md_ua") or "")[:2400]
        markets = ov.get("markets") or []
        cat_ua = ov.get("category_ua") or "Ефірні олії"
        cat_en = ov.get("category_en") or "Essential Oils"

        meta = {
            "title": raw_title,
            "description": raw_desc,
            "image_url": ov.get("image_url", ""),
            "source_url": ov.get("source_url", ""),
            "excerpt": raw_excerpt,
        }
        md_ua, md_en = await _build_cards_with_llm(ov_slug, meta, cat_ua, cat_en, markets)
        new_title_ua = _extract_h1_title(md_ua, raw_title)
        new_title_en = _extract_h1_title(md_en, raw_title)
        new_short_ua = _extract_short(md_ua)
        new_short_en = _extract_short(md_en)

        # Оновлюємо в БД, тільки якщо переклад справді вдався (зникли CJK / з'явилась кирилиця)
        if _CYRILLIC_RE.search(new_short_ua or md_ua) and not _CJK_RE.search(new_title_ua):
            upsert_catalog_item({
                "slug": ov_slug,
                "status": "active",
                "title_ua": new_title_ua,
                "title_en": new_title_en,
                "category_ua": cat_ua,
                "category_en": cat_en,
                "short_ua": new_short_ua,
                "short_en": new_short_en,
                "image_url": ov.get("image_url", ""),
                "md_ua": md_ua,
                "md_en": md_en,
                "markets": markets,
                "source_url": ov.get("source_url", ""),
                "change_type": ov.get("change_type") or "new",
            })
            await asyncio.to_thread(_vectorize_markdown_to_rag, ov_slug, md_ua)
            translated_slugs.append(ov_slug)
            print(f"[catalog_sync] 🌐 Перекладено UA+EN: {ov_slug} -> {new_title_ua} / {new_title_en}")

    return translated_slugs


def _pick_primary_static_item(group: list[dict]) -> dict:
    """Обирає основну (канонічну) картку серед знайденої групи статичних дублікатів."""
    images_dir = PROJECT_ROOT / "src" / "content" / "images" / "products"

    def _score(item: dict) -> tuple[int, int, int, int, int]:
        slug = item["slug"]
        # 1. Категорійні префікси (body-care, sun-care, collections, starter-kits) — завжди вторинні
        not_generic = 0 if slug in _GENERIC_DUP_SLUGS or item["stem"].lower() in _GENERIC_DUP_SLUGS else 1
        # 2. Чистий ASCII slug без діакритики
        ascii_slug = 1 if item["stem"].isascii() else 0
        # 3. Має локальне студійне фото
        has_local_img = 1 if (images_dir / f"{slug}.jpg").exists() else 0
        # 4. Повніший текст статті
        text_len = len(item["md"])
        # 5. Коротший і чистіший slug (без -llv, -kit-oil тощо)
        neg_slug_len = -len(slug)
        return (not_generic, ascii_slug, has_local_img, text_len, neg_slug_len)

    return max(group, key=_score)


def deduplicate_static_products(dry_run: bool = False) -> dict:
    """Знаходить дублікати у `src/content/products/` (UA + EN), доповнює основну картку та видаляє дублі."""
    result: dict = {"merged": [], "removed": []}
    if not PRODUCTS_DIR.exists():
        return result

    items: list[dict] = []
    for p in sorted(PRODUCTS_DIR.glob("*.md")):
        md = p.read_text(encoding="utf-8")
        slug = slugify(p.stem)
        title = _extract_h1_title(md, p.stem)
        items.append({
            "path": p,
            "stem": p.stem,
            "slug": slug,
            "alias": _canonical_alias(slug),
            "compact": _compact_alias(slug),
            "title": title,
            "title_key": _normalize_title_key(title),
            "md": md,
        })

    # Union-Find групування за однаковим compact_alias або title_key
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    by_compact: dict[str, int] = {}
    by_title: dict[str, int] = {}
    for idx, it in enumerate(items):
        if it["compact"]:
            if it["compact"] in by_compact:
                union(by_compact[it["compact"]], idx)
            else:
                by_compact[it["compact"]] = idx
        tk = it["title_key"]
        if tk and len(tk) >= 5:
            if tk in by_title:
                union(by_title[tk], idx)
            else:
                by_title[tk] = idx

    groups: dict[int, list[dict]] = {}
    for idx, it in enumerate(items):
        groups.setdefault(find(idx), []).append(it)

    for grp in groups.values():
        if len(grp) < 2:
            continue
        primary = _pick_primary_static_item(grp)
        p_path: Path = primary["path"]
        p_en_path = PRODUCTS_EN_DIR / p_path.name
        merged_ua = primary["md"]
        merged_en = p_en_path.read_text(encoding="utf-8") if p_en_path.exists() else ""
        total_added_ua = 0
        total_added_en = 0

        for dup in grp:
            if dup["path"] == p_path:
                continue
            merged_ua, add_ua = _merge_markdown_cards(merged_ua, dup["md"])
            total_added_ua += add_ua

            dup_en_path = PRODUCTS_EN_DIR / dup["path"].name
            if dup_en_path.exists():
                dup_en_md = dup_en_path.read_text(encoding="utf-8")
                if merged_en:
                    merged_en, add_en = _merge_markdown_cards(merged_en, dup_en_md)
                    total_added_en += add_en
                else:
                    merged_en = dup_en_md
                    total_added_en += 1

            result["removed"].append({"slug": dup["slug"], "into": primary["slug"], "source": "static"})
            if not dry_run:
                dup["path"].unlink(missing_ok=True)
                if dup_en_path.exists():
                    dup_en_path.unlink(missing_ok=True)

        if total_added_ua > 0 or total_added_en > 0:
            result["merged"].append({
                "slug": primary["slug"],
                "added_ua_lines": total_added_ua,
                "added_en_lines": total_added_en,
                "source": "static",
            })
            if not dry_run:
                if total_added_ua > 0:
                    p_path.write_text(merged_ua, encoding="utf-8")
                if total_added_en > 0 and merged_en:
                    PRODUCTS_EN_DIR.mkdir(parents=True, exist_ok=True)
                    p_en_path.write_text(merged_en, encoding="utf-8")

    return result


def deduplicate_dynamic_overrides(dry_run: bool = False) -> dict:
    """Знаходить дублікати у PostgreSQL (`catalog_overrides`): доповнює або видаляє зайві записи."""
    from .store import get_catalog_overrides

    result: dict = {"merged": [], "removed": []}
    active_ov, _ = get_catalog_overrides(force_refresh=True)
    if not active_ov:
        return result

    static_slugs = _get_static_product_slugs()
    static_compact = {_compact_alias(s): s for s in static_slugs.keys()}
    static_titles: dict[str, str] = {}
    for s, p in static_slugs.items():
        try:
            nt = _normalize_title_key(_extract_h1_title(p.read_text(encoding="utf-8"), p.stem))
            if nt and len(nt) >= 5:
                static_titles[nt] = s
        except Exception:
            pass

    remaining: list[dict] = []
    # 1. Динамічні дублікати статичних карток -> видаляємо з catalog_overrides (щоб не дублювались у Mini App/RAG)
    for ov in active_ov:
        ov_slug = ov["slug"]
        has_md = bool(ov.get("md_ua") or ov.get("md_en"))
        if not has_md:
            continue
        comp = _compact_alias(ov_slug)
        t_ua = _normalize_title_key(ov.get("title_ua") or "")
        t_en = _normalize_title_key(ov.get("title_en") or "")

        matched_static = (
            static_slugs.get(ov_slug) and ov_slug
            or static_compact.get(comp)
            or (static_titles.get(t_en) if t_en else None)
            or (static_titles.get(t_ua) if t_ua else None)
        )
        if matched_static:
            result["removed"].append({"slug": ov_slug, "into": matched_static, "source": "dynamic_vs_static"})
            if not dry_run:
                delete_catalog_override(ov_slug)
                print(f"[catalog_sync] 🧹 Видалено динамічний дублікат {ov_slug} (вже є статична картка {matched_static})")
            continue
        remaining.append(ov)

    # 2. Динамічні дублікати між собою -> зливаємо ринки й унікальний контент у кращу картку, дубль видаляємо
    groups: dict[str, list[dict]] = {}
    for ov in remaining:
        key = _compact_alias(ov["slug"]) or _normalize_title_key(ov.get("title_en") or ov.get("title_ua") or ov["slug"])
        groups.setdefault(key, []).append(ov)

    for grp in groups.values():
        if len(grp) < 2:
            continue
        grp.sort(
            key=lambda x: (
                1 if "US" in (x.get("markets") or []) else 0,
                1 if "EU" in (x.get("markets") or []) else 0,
                len(x.get("md_ua") or ""),
            ),
            reverse=True,
        )
        keeper = grp[0]
        merged_markets = list(keeper.get("markets") or [])
        merged_ua = keeper.get("md_ua") or ""
        merged_en = keeper.get("md_en") or ""
        keeper_img = keeper.get("image_url") or ""
        enriched = False

        for dup in grp[1:]:
            for m in dup.get("markets") or []:
                if m not in merged_markets:
                    merged_markets.append(m)
                    enriched = True
            if not keeper_img and dup.get("image_url"):
                keeper_img = dup["image_url"]
                enriched = True
            merged_ua, add_ua = _merge_markdown_cards(merged_ua, dup.get("md_ua") or "")
            merged_en, add_en = _merge_markdown_cards(merged_en, dup.get("md_en") or "")
            if add_ua or add_en:
                enriched = True

            result["removed"].append({"slug": dup["slug"], "into": keeper["slug"], "source": "dynamic_vs_dynamic"})
            if not dry_run:
                delete_catalog_override(dup["slug"])
                print(f"[catalog_sync] 🧹 Об'єднано динамічний дублікат {dup['slug']} -> {keeper['slug']}")

        if enriched:
            result["merged"].append({"slug": keeper["slug"], "source": "dynamic"})
            if not dry_run:
                upsert_catalog_item({
                    **keeper,
                    "markets": merged_markets,
                    "image_url": keeper_img,
                    "md_ua": merged_ua,
                    "md_en": merged_en,
                    "short_ua": _extract_short(merged_ua) or keeper.get("short_ua", ""),
                    "short_en": _extract_short(merged_en) or keeper.get("short_en", ""),
                })
                _vectorize_markdown_to_rag(keeper["slug"], merged_ua)

    return result


def _format_markets_ua(markets: list[str]) -> str:
    labels = [_MARKET_LABELS_UA.get(m, m) for m in markets[:4]]
    suffix = f" +{len(markets) - 4}" if len(markets) > 4 else ""
    return ", ".join(labels) + suffix if labels else "світові ринки"


def format_sync_report_html(report: dict) -> str:
    """Форматує простий і зрозумілий звіт про оновлення асортименту (лише для тебе і Наталії)."""
    added = report.get("added", [])
    restored = report.get("restored", [])
    archived = report.get("archived", [])
    translated = report.get("translated", [])
    deduped = report.get("deduped") or {}
    dedup_removed = deduped.get("removed", []) if isinstance(deduped, dict) else []

    lines = ["🌿 <b>Оновлення асортименту doTERRA</b>"]

    if not added and not restored and not archived and not translated and not dedup_removed:
        lines.append("\nУсе актуально — нових змін на ринках doTERRA поки немає ✨")
        return "\n".join(lines)

    if added:
        lines.append(f"\n✨ <b>З'явилися новинки ({len(added)}):</b>")
        for item in added[:10]:
            m_str = _format_markets_ua(item.get("markets", []))
            lines.append(
                f"  • <b>{html.escape(item['title'])}</b> ({html.escape(m_str)})"
            )
        if len(added) > 10:
            lines.append(f"  … та ще {len(added) - 10}")

    if restored:
        lines.append(f"\n♻️ <b>Повернулися у продаж ({len(restored)}):</b>")
        for r in restored[:10]:
            slug = r["slug"] if isinstance(r, dict) else str(r)
            m_str = _format_markets_ua(r.get("markets", [])) if isinstance(r, dict) else ""
            nice_name = slug.replace("-", " ").title()
            lines.append(
                f"  • <b>{html.escape(nice_name)}</b>" + (f" ({html.escape(m_str)})" if m_str else "")
            )
        if len(restored) > 10:
            lines.append(f"  … та ще {len(restored) - 10}")

    if archived:
        lines.append(f"\n📦 <b>Тимчасово зникли з усіх ринків ({len(archived)}):</b>")
        for slug in archived[:10]:
            nice_name = str(slug).replace("-", " ").title()
            lines.append(f"  • {html.escape(nice_name)}")
        if len(archived) > 10:
            lines.append(f"  … та ще {len(archived) - 10}")

    if translated:
        lines.append(f"\n🌐 <b>Автоматично перекладено на укр. та англ.:</b> {len(translated)} поз.")

    if dedup_removed:
        lines.append(f"\n🧹 <b>Прибрано дублікатів (інформацію об'єднано):</b> {len(dedup_removed)} поз.")

    lines.append("\nУсі оновлення вже автоматично додані в Mini App та базу знань Ароми 💛")
    return "\n".join(lines)
