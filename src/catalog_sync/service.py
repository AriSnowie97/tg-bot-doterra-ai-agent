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
            f"1. Пиши ТІЛЬКИ факти з наданого тексту, нічого не вигадуй.\n"
            f"2. Фокус — регуляція стану та підтримка добробуту, НІКОЛИ не обіцяй лікування хвороб.\n"
            f"3. Грамотна літературна українська та англійська без помилок.\n"
            f"4. Обов'язковий формат заголовку UA:\n"
            f"   # {title}\n"
            f"   **Категорія:** {category_ua}\n"
            f"   **Тип:** ... (ринки: {markets_str})\n"
            f"   ---\n"
            f"   ## Короткий опис / ## Склад та ключові інгредієнти / ## Спосіб застосування / ## Застереження\n"
            f"5. Обов'язковий формат заголовку EN:\n"
            f"   # {title}\n"
            f"   **Category:** {category_en}\n"
            f"   **Type:** ... (markets: {markets_str})\n"
            f"   ---\n"
            f"   ## Short Description / ## Ingredients & Features / ## Directions for Use / ## Precautions\n"
            f"6. Не додавай теги зображень `![...]` — вони підставляються автоматично.\n\n"
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
    r"renewing|holiday|seasonal|sunshine|essential-oil|essential|oil|fixed))+|-blend$",
    re.IGNORECASE,
)


def _canonical_alias(slug: str) -> str:
    """Нормалізує слaг для виявлення дублікатів (напр. adaptiv-touch == adaptiv-touch-calming-blend)."""
    s = slug.strip().lower()
    if s.startswith("doterra-"):
        s = s[len("doterra-"):]
    prev = None
    while prev != s:
        prev = s
        s = _ALIAS_SUFFIX_RE.sub("", s).strip("-")
    return s


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

    # 3. Пошук та автоматичне додавання НОВИНОК (із захистом від дублікатів-синонімів)
    known_aliases = {_canonical_alias(k) for k in known_active}
    restored_set = {r["slug"] for r in report["restored"]}
    new_slugs = [
        s for s in discovered.keys()
        if s not in known_active
        and _canonical_alias(s) not in known_aliases
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

        cat_ua, cat_en = infer_category(slug, meta["title"], primary_url)
        md_ua, md_en = await _build_cards_with_llm(slug, meta, cat_ua, cat_en, info["markets"])

        item = {
            "slug": slug,
            "title_ua": meta["title"],
            "title_en": meta["title"],
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
            "title": meta["title"],
            "category": cat_ua,
            "markets": info["markets"],
            "has_image": bool(meta.get("image_url")),
        })

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


def format_sync_report_html(report: dict) -> str:
    """Форматує звіт синхронізації каталогу у гарний HTML для адміна в Telegram."""
    healthy = report.get("markets_healthy", 0)
    total_m = report.get("markets_checked", 0)
    codes = ", ".join(report.get("healthy_market_codes", [])) or "немає"
    added = report.get("added", [])
    restored = report.get("restored", [])
    archived = report.get("archived", [])
    skip_reason = report.get("archive_skipped_reason", "")

    lines = [
        "🌍 <b>Звіт автосинхронізації каталогу doTERRA</b>",
        "",
        f"📡 <b>Ринків перевірено:</b> {healthy}/{total_m} ({html.escape(codes)})",
        f"📦 <b>Знайдено товарів на сайтах:</b> {report.get('total_discovered', 0)}",
        f"🆕 <b>Додано новинок:</b> {len(added)}",
        f"♻️ <b>Відновлено:</b> {len(restored)}",
        f"🗄 <b>Архівовано (зникли з усіх ринків):</b> {len(archived)}",
    ]

    if added:
        lines.append("\n<b>Новинки:</b>")
        for item in added[:10]:
            m_str = ", ".join(item.get("markets", [])[:4])
            img_icon = "🖼" if item.get("has_image") else "🌿"
            lines.append(
                f"  • {img_icon} <b>{html.escape(item['title'])}</b> "
                f"(<i>{html.escape(item['category'])}</i> · {html.escape(m_str)})"
            )
        if len(added) > 10:
            lines.append(f"  … та ще {len(added) - 10}")

    if archived:
        lines.append("\n<b>Архівовано:</b>")
        for slug in archived[:10]:
            lines.append(f"  • <code>{html.escape(slug)}</code>")
        if len(archived) > 10:
            lines.append(f"  … та ще {len(archived) - 10}")

    if skip_reason:
        lines.append(f"\n🛡 <i>{html.escape(skip_reason)}</i>")

    return "\n".join(lines)
