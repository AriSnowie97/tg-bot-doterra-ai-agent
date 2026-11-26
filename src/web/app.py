"""
doTERRA Bot — Мінімальний веб-сервер для перегляду MD-документів.

Маршрути:
    GET /           — список усіх документів
    GET /docs/{slug} — повний вміст MD-файлу (відрендерений у HTML)

Запуск:
    uvicorn src.web.app:app --host 0.0.0.0 --port 8000

Змінні оточення:
    DOCS_BASE_URL   — публічний URL цього сервера (для посилань у боті)
"""

# Standard
import html
import os
from pathlib import Path
# Special
import re
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import markdown

from pydantic import BaseModel, Field
import nh3
from src.web.auth import require_service_token, require_telegram_user
from src.agent import generate_response
from src.content.parser import slugify
from src.catalog_sync import get_catalog_overrides, get_override_doc
from src.safety import redact
from src.security_log import log_security_event
from src.agent.specialist import (
    has_cat_mention,
    has_red_flags,
    is_crisis,
    is_emergency,
    is_prompt_injection,
)

# ---------------------------------------------------------------------------
# Налаштування
# ---------------------------------------------------------------------------

DOCS_DIR = Path(__file__).parent.parent / "content" / "docs"

app = FastAPI(title="doTERRA Docs Viewer", docs_url=None, redoc_url=None)

# Додаємо CORS для того, щоб React (який запущено на іншому порту чи домені) міг робити запити
from fastapi.middleware.cors import CORSMiddleware

# Дозволені origin'и (через кому). Підтримуємо GitHub Pages та власний домен Railway.
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "https://arisnowie97.github.io,https://tg-bot-doterra-ai-agent-production.up.railway.app",
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Telegram-Init-Data"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Базові заголовки безпеки для всіх відповідей API та HTML-сторінок."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/app"):
        # Telegram Web / Desktop відкривають Mini App в iframe — не блокуємо його через X-Frame-Options
        if request.url.path in ("/app", "/app/", "/app/index.html"):
            response.headers.setdefault("Cache-Control", "no-cache")
    else:
        response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "cross-origin")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


# Монтуємо папку з картинками
IMAGES_DIR = Path(__file__).parent.parent / "content" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

# Монтуємо зібраний Telegram Mini App (працює незалежно від GitHub Pages)
MINIAPP_DIR = Path(__file__).parent / "miniapp_dist"
if MINIAPP_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(MINIAPP_DIR), html=True), name="miniapp")


# ---------------------------------------------------------------------------
# Моделі
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    query: str = Field(max_length=1000)

class ChatResponse(BaseModel):
    response: str


class LessonContextItem(BaseModel):
    lesson_id: str = ""
    title: str = ""
    source_ref: str = ""
    text: str = ""


class AromaAskRequest(BaseModel):
    user_id: str = ""
    tariff: str = ""
    lesson_id: str | None = None
    language: str = "uk"
    message: str = Field(max_length=2000)
    lesson_context: list[LessonContextItem] = Field(default_factory=list)


class AromaSafetyInfo(BaseModel):
    triggered: bool = False
    route_to: str | None = None
    reason: str | None = None


class AromaAskResponse(BaseModel):
    answer: str
    safety: AromaSafetyInfo = Field(default_factory=AromaSafetyInfo)


# ---------------------------------------------------------------------------
# Допоміжні функції
# ---------------------------------------------------------------------------

# Дозволені мови статей
ALLOWED_LANGS = {"ua", "en"}

# Allow-list для HTML, що генерує markdown. Усе інше (script, iframe, on*-атрибути,
# javascript:-посилання) вирізається.
_ALLOWED_TAGS = {
    "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "blockquote", "pre", "code",
    "strong", "em", "b", "i", "del", "s", "a", "img",
    "table", "thead", "tbody", "tr", "th", "td", "details", "summary",
}
_ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "code": {"class"},
}
_ALLOWED_SCHEMES = {"http", "https", "mailto"}


def _validate_lang(lang: str) -> None:
    if lang not in ALLOWED_LANGS:
        raise HTTPException(status_code=400, detail="Невірна мова")


def _render_md(md_text: str) -> str:
    """Конвертує Markdown-текст у безпечний (очищений) HTML."""
    raw_html = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "nl2br"]
    )
    return nh3.clean(
        raw_html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        url_schemes=_ALLOWED_SCHEMES,
    )


# Актуальні новинки 2026 року зі статичного каталогу (доповнюються динамічними з catalog_overrides)
STATIC_NEW_2026_SLUGS = {
    "ikise-skin-care-collection",
    "intune-stick-hiba-wood",
    "naio-wood",
    "frankincense-stick-naio-wood",
    "natures-rx-collection",
    "doterra-on-guard-stick-echinacea",
    "deep-blue-stick-copaiba",
    "volo-diffuser",
    "roam-diffuser",
    "pilot-diffuser",
    "bubble-diffuser",
}

# Новорічна та зимова колекція doTERRA Holiday 2026 («A Season of Wōnder», US & EU)
STATIC_HOLIDAY_2026_MARKETS: dict[str, list[str]] = {
    "doterra-advent-calendar-2026": ["US"],
    "mini-stick-trio": ["US"],
    "red-lumist-diffuser-holiday-joy-set": ["US"],
    "pink-sand-lip-oil": ["US"],
    "vanilla-dream-lip-balm": ["US"],
    "vanilla-dream-restorative-hand-cream": ["US", "EU"],
    "holiday-joy": ["US", "EU"],
    "holiday-peace": ["US", "EU"],
    "holiday-love": ["US", "EU", "CA"],
    "winterberry": ["US"],
    "yule-log": ["US"],
    "wassail": ["US"],
    "cinnamon-drops": ["US"],
    "lemon-lime-drops": ["US", "EU"],
    "lumist-silver-diffuser-holiday-joy-kit": ["US"],
    "doterra-hygge": ["US", "EU"],
    "northern-escape": ["US", "EU"],
    "black-spruce-pebble-diffuser-set": ["EU"],
}

_NEW_MARKERS_RE = re.compile(
    r"(?:#новинка\d*|#new20\d\d|\bновинка\s+20\d\d\b|\bnew\s+20\d\d\b)",
    re.IGNORECASE,
)
_HOLIDAY_MARKERS_RE = re.compile(
    r"(?:#новорічн\w*|#святков\w*|#holiday20\d\d|holiday\s+2026|новорічн\w+\s+колекці)",
    re.IGNORECASE,
)
_RETURNED_MARKERS_RE = re.compile(
    r"(?:#повернення|#returned|повернувся\s+на\s+ринок|returned\s+to\s+market)",
    re.IGNORECASE,
)


def _detect_static_update_info(slug: str, md_text: str) -> tuple[str, list[str]]:
    """Визначає статус новинки/святкової колекції/повернення для статичного .md продукту."""
    if _RETURNED_MARKERS_RE.search(md_text):
        return "returned", ["US"]
    if slug in STATIC_HOLIDAY_2026_MARKETS:
        return "holiday", list(STATIC_HOLIDAY_2026_MARKETS[slug])
    if _HOLIDAY_MARKERS_RE.search(md_text):
        return "holiday", ["US", "EU"]
    if slug in STATIC_NEW_2026_SLUGS or _NEW_MARKERS_RE.search(md_text):
        return "new", ["US"]
    return "", []


def _get_article_metadata(lang: str, md_path: Path, base_url: str = "", section_name: str = "") -> dict:
    """Витягує метадані з .md файлу."""
    original_stem = md_path.stem
    slug = slugify(original_stem)
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    LANG = {
        "ua": {
            "other": "Інше",
            "guide": "_Гід",
            "guides": "Гайди",
            "category": "**Категорія:**",
            "type": "**Тип:**",
            "article": "**Артикул",
            "link": "**Посилання",
        },
        "en": {
            "other": "Other",
            "guide": "_Guide",
            "guides": "Guides",
            "category": "**Category:**",
            "type": "**Type:**",
            "article": "**Article",
            "link": "**Link",
        }
    }
    
    title = original_stem
    short = ""
    category = LANG[lang]["other"]
    image = ""
    
    # Шукаємо image в перших рядках
    for line in lines[:5]:
        if line.startswith("![") and "](" in line:
            parts = line.split("](")[1].split(")")
            if parts:
                image = parts[0]
                # Якщо картинка локальна, робимо її абсолютною
                if image.startswith("/images/") and base_url:
                    image = f"{base_url}{image}"
                # Якщо картинка це шаблонний текст або стандартна заглушка doTERRA
                if (
                    image == "Тут_буде_офіційне_фото_після_завантаження_через_бот"
                    or "New-Default-Image" in image
                ):
                    image = ""
            break

    # Шукаємо заголовок
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break
    title = re.sub(r"\s*\((?:чанк|chunk)\s*\d+\)", "", title, flags=re.IGNORECASE).strip()
            
    # Шукаємо категорію
    for line in lines:
        if LANG[lang]["category"] in line:
            category = line.split(LANG[lang]["category"])[1].strip()
            if "→" in category:
                category = category.split("→")[0].strip()
            elif ">" in category:
                category = category.split(">")[0].strip()
            break
    
    if category == LANG[lang]["other"]:
        if section_name == "books":
            category = "Книги та довідники" if lang == "ua" else "Books & Guides"
        elif LANG[lang]["guide"] in original_stem or original_stem.startswith("0"):
            category = LANG[lang]["guides"]
            
    # Шукаємо короткий опис
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith("#"): continue
        if line.startswith("!["): continue
        if line.startswith(LANG[lang]["category"]) or line.startswith(LANG[lang]["type"]) or line.startswith(LANG[lang]["article"]) or line.startswith(LANG[lang]["link"]): continue
        if line.startswith("**Джерело") or line.startswith("**Джерела") or line.startswith("**Source") or line.startswith("**Sources"): continue
        if line.startswith("**Статус") or line.startswith("**Status") or line.startswith("**Призначення") or line.startswith("**Purpose"): continue
        if line.startswith("⚠️") or line.startswith("**⚠️"): continue
        if line.startswith("---"): continue
        
        short = line
        if len(short) > 120:
            short = short[:117] + "..."
        break

    update_type, markets = (
        _detect_static_update_info(slug, text)
        if section_name in ("products", "kits")
        else ("", [])
    )

    return {
        "slug": slug,
        "title": title,
        "short": short,
        "tag": category,
        "image": image,
        "section": section_name,
        "update_type": update_type,
        "markets": markets,
        "updated_at": "",
    }

CONTENT_DIR = Path(__file__).parent.parent / "content"
DIRECTORIES_TO_SEARCH = [
    "docs",
    "products",
    "symphony_of_the_cells",
    "kits",
    "books"
]

# Службові довідники за книгами та логіка маршрутизації бота використовуються всередині ІІ-помічниці
# (RAG-пошук та пости), а вижимки з книг інтегровані безпосередньо у картки продуктів doTERRA
HIDDEN_ARTICLE_SLUGS = {
    "01-oils-safety-reference",
    "02-emotional-themes-map",
    "03-intake-flow-and-routing",
    "04-modern-essentials-supplement",
    "05-azbuka-supplement",
    "06-aromalogiya-supplement",
}

def _get_all_docs() -> list[dict]:
    """Повертає список усіх MD-файлів із вказаних директорій."""
    if not CONTENT_DIR.exists():
        return []
        
    docs = []
    for dir_name in DIRECTORIES_TO_SEARCH:
        d = CONTENT_DIR / dir_name
        if d.exists():
            for p in d.glob("*.md"):
                if slugify(p.stem) in HIDDEN_ARTICLE_SLUGS:
                    continue
                docs.append({"slug": slugify(p.stem), "filename": p.name})
                
    return sorted(docs, key=lambda d: d["slug"])


def _html_page(title: str, body: str) -> str:
    """Обгортає HTML-тіло в мінімальну сторінку."""
    return f"""<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  body {{ font-family: sans-serif; max-width: 820px; margin: 40px auto; padding: 0 16px; line-height: 1.6; color: #222; }}
  h1 {{ border-bottom: 2px solid #ccc; padding-bottom: 8px; }}
  h2 {{ margin-top: 2em; }}
  hr {{ border: none; border-top: 1px solid #ddd; margin: 24px 0; }}
  a {{ color: #2a7a2a; }}
  pre {{ background: #f4f4f4; padding: 12px; border-radius: 4px; overflow-x: auto; }}
  code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 3px; }}
  .back {{ display: inline-block; margin-bottom: 24px; font-size: 0.9em; }}
</style>
</head>
<body>
{body}
</body>
</html>"""


# ---------------------------------------------------------------------------
# API Маршрути (для React WebApp)
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Ендпоінт перевірки працездатності сервісу (healthcheck для Railway/Docker)."""
    return {"status": "ok", "service": "doterra-ai-agent"}


@app.post("/api/chat", response_model=ChatResponse)
async def api_chat(request: ChatRequest, user: dict = Depends(require_telegram_user)):
    """Ендпоінт для чату з Mini App."""
    clean_query = request.query.strip()
    if not clean_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    if len(clean_query) > 1000:
        raise HTTPException(status_code=400, detail="Query is too long (max 1000 characters)")

    if is_prompt_injection(clean_query):
        log_security_event("prompt_injection_attempt", user_id=user.get("id"), channel="mini_app", text_len=len(clean_query))
    
    try:
        response_text = await generate_response(clean_query)
        return ChatResponse(response=response_text)
    except Exception as e:
        print(f"[api_chat] Error: {redact(e)}")
        err_str = str(e)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            return ChatResponse(
                response="🌿 Зараз тимчасово вичерпано ліміт запитів до Google API (429 Resource Exhausted). Зачекай, будь ласка, трішки або звернись до Наталії Котелянської напряму: https://www.instagram.com/nkotelianska/ 💛"
            )
        raise HTTPException(status_code=500, detail="Помилка при генерації відповіді")


def _format_aroma_plain_text(text: str) -> str:
    """Перетворює внутрішні markdown-посилання [Назва](slug) на чистий текст для клієнтів без Markdown."""
    def _replace_link(match: re.Match[str]) -> str:
        label, target = match.group(1), match.group(2).strip()
        if target.startswith(("http://", "https://")):
            return f"{label} ({target})"
        return label

    cleaned = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _replace_link, text)
    return cleaned.replace("**", "").strip()


def _detect_aroma_safety_reason(text: str) -> str | None:
    if is_crisis(text):
        return "crisis"
    if is_emergency(text):
        return "emergency"
    if has_red_flags(text):
        return "red_flag"
    if has_cat_mention(text):
        return "cat_safety"
    return None


@app.post("/v1/aroma/ask", response_model=AromaAskResponse)
async def v1_aroma_ask(
    request: AromaAskRequest,
    _: None = Depends(require_service_token),
):
    """Міжсервісний контракт Ароми для Аромакадемії (POST /v1/aroma/ask)."""
    clean_message = request.message.strip()
    if not clean_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if is_prompt_injection(clean_message):
        log_security_event(
            "prompt_injection_attempt",
            user_id=request.user_id,
            channel="aroma_academy",
            text_len=len(clean_message),
        )

    extra_chunks = [
        {
            "is_course_material": True,
            "course_label": (
                f"Матеріал уроку Аромакадемії: {item.title or item.lesson_id or 'урок'}"
                + (f" ({item.source_ref})" if item.source_ref else "")
            ),
            "content": item.text.strip(),
        }
        for item in request.lesson_context[:5]
        if item.text and item.text.strip()
    ]

    try:
        raw_answer = await generate_response(
            clean_message,
            extra_chunks=extra_chunks or None,
        )
    except Exception as e:
        print(f"[v1_aroma_ask] Error: {redact(e)}")
        raise HTTPException(status_code=503, detail="Aroma service temporarily unavailable")

    answer = _format_aroma_plain_text(raw_answer)
    safety_reason = _detect_aroma_safety_reason(clean_message)
    safety = (
        AromaSafetyInfo(triggered=True, route_to="natalia_or_doctor", reason=safety_reason)
        if safety_reason
        else AromaSafetyInfo()
    )
    return AromaAskResponse(answer=answer, safety=safety)


def _get_request_base_url(request: Request) -> str:
    base_url = str(request.base_url).rstrip("/")
    if request.headers.get("x-forwarded-proto") == "https":
        base_url = base_url.replace("http://", "https://")
    return base_url


def _collect_articles(lang: str, base_url: str) -> list[dict]:
    """Збирає всі активні статті та динамічні оновлення каталогу для заданої мови."""
    if not CONTENT_DIR.exists():
        return []

    from src.catalog_sync.service import _canonical_alias

    articles: list[dict] = []
    seen_slugs: set[str] = set()
    seen_aliases: set[str] = set()
    active_overrides, archived_slugs = get_catalog_overrides()
    override_by_slug = {ov["slug"]: ov for ov in active_overrides}

    for dir_name in DIRECTORIES_TO_SEARCH:
        if lang == "ua":
            d = CONTENT_DIR / dir_name
        else:  # lang == "en"
            d = CONTENT_DIR / dir_name / lang

        if d.exists():
            for md_path in sorted(d.glob("*.md")):
                # Пропускаємо технічні файли-гайди (01_Гід, 02_Гід тощо)
                if md_path.stem[0].isdigit() and "_Гід" in md_path.stem:
                    continue
                # Службова логіка роботи бота або архівовані з усіх ринків позиції
                item_slug = slugify(md_path.stem)
                if item_slug in HIDDEN_ARTICLE_SLUGS or item_slug in archived_slugs or item_slug in seen_slugs:
                    continue
                seen_slugs.add(item_slug)
                if dir_name == "products":
                    seen_aliases.add(_canonical_alias(item_slug))

                meta = _get_article_metadata(lang, md_path, base_url, dir_name)
                ov = override_by_slug.get(item_slug)
                if ov:
                    ov_type = ov.get("change_type")
                    has_ov_card = bool(ov.get("md_ua") or ov.get("md_en"))
                    # Порожні рядки трекінгу missing_streak (change_type='track' або без md) НЕ є новинками!
                    if ov_type == "returned":
                        meta["update_type"] = "returned"
                        if ov.get("markets"):
                            meta["markets"] = ov["markets"]
                        if ov.get("updated_at"):
                            meta["updated_at"] = ov["updated_at"]
                    elif ov_type in ("new", "holiday") and has_ov_card:
                        meta["update_type"] = ov_type
                        if ov.get("markets"):
                            meta["markets"] = ov["markets"]
                        if ov.get("updated_at"):
                            meta["updated_at"] = ov["updated_at"]
                articles.append(meta)

    # Додаємо динамічні новинки та повернення з PostgreSQL (catalog_overrides)
    for ov in active_overrides:
        ov_slug = ov["slug"]
        if (
            ov_slug in seen_slugs
            or _canonical_alias(ov_slug) in seen_aliases
            or ov_slug in HIDDEN_ARTICLE_SLUGS
            or not (ov.get("md_ua") or ov.get("md_en"))
        ):
            continue
        seen_slugs.add(ov_slug)
        seen_aliases.add(_canonical_alias(ov_slug))
        title = (ov.get("title_en") or ov.get("title_ua") or ov_slug) if lang == "en" else (ov.get("title_ua") or ov.get("title_en") or ov_slug)
        short = (ov.get("short_en") or ov.get("short_ua") or "") if lang == "en" else (ov.get("short_ua") or ov.get("short_en") or "")
        tag = (ov.get("category_en") or "Essential Oils") if lang == "en" else (ov.get("category_ua") or "Ефірні олії")
        ov_type = ov.get("change_type") if ov.get("change_type") in ("new", "holiday", "returned") else "new"
        local_img = IMAGES_DIR / "products" / f"{ov_slug}.jpg"
        if local_img.exists():
            ov_image = f"{base_url}/images/products/{ov_slug}.jpg" if base_url else f"/images/products/{ov_slug}.jpg"
        else:
            ov_image = ov.get("image_url", "")
            if "-za-en-web." in ov_image or "pool=wave0" in ov_image:
                # Старі регіональні CDN-фото (ZA / wave0) віддають 404 — не передаємо битий URL на фронтенд
                ov_image = ""
        # Чистимо технічні хвости сайту в заголовку та за можливості беремо перекладений H1
        from src.catalog_sync.service import _clean_product_title, _extract_h1_title, _CJK_RE
        raw_title = (ov.get("title_en") or ov.get("title_ua") or ov_slug) if lang == "en" else (ov.get("title_ua") or ov.get("title_en") or ov_slug)
        md_for_lang = (ov.get("md_en") or "") if lang == "en" else (ov.get("md_ua") or "")
        h1_title = _extract_h1_title(md_for_lang, raw_title)
        title = h1_title if (_CJK_RE.search(raw_title) or "|" in raw_title) and not _CJK_RE.search(h1_title) else _clean_product_title(raw_title)
        articles.append({
            "slug": ov_slug,
            "title": title,
            "short": short,
            "tag": tag,
            "image": ov_image,
            "section": "products",
            "update_type": ov_type,
            "markets": ov.get("markets") or [],
            "updated_at": ov.get("updated_at") or "",
        })

    return articles


@app.get("/api/articles/{lang}")
async def api_get_articles(lang: str, request: Request):
    """Повертає список усіх статей з метаданими для Mini App."""
    _validate_lang(lang)
    articles = _collect_articles(lang, _get_request_base_url(request))
    # Сортуємо: спочатку гайди (якщо якісь залишились), потім інші за алфавітом
    articles.sort(key=lambda a: (0 if a["tag"] == "Гайди" else 1, a["title"]))
    return articles


@app.get("/api/whats-new/{lang}")
async def api_get_whats_new(lang: str, request: Request):
    """Повертає новорічну колекцію, новинки та продукти, які повернулися на ринки doTERRA."""
    _validate_lang(lang)
    articles = _collect_articles(lang, _get_request_base_url(request))
    updates = [a for a in articles if a.get("update_type") in ("new", "holiday", "returned")]

    db_updates = sorted(
        [a for a in updates if a.get("updated_at")],
        key=lambda a: a["updated_at"],
        reverse=True,
    )
    order_rank = {"holiday": 0, "returned": 1, "new": 2}
    static_updates = sorted(
        [a for a in updates if not a.get("updated_at")],
        key=lambda a: (order_rank.get(a.get("update_type", ""), 3), a.get("title", "").lower()),
    )
    return static_updates + db_updates

@app.get("/api/docs/{slug}/{lang}")
async def api_get_doc(slug: str, lang: str, request: Request):
    """Повертає відрендерений HTML статті у форматі JSON для React-додатку."""
    _validate_lang(lang)
    if not slug.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Невірний slug")

    # 0. Перевіряємо динамічні зміни каталогу в PostgreSQL (новинки та архів)
    norm_slug = slugify(slug)
    ov_title, ov_md, ov_archived = get_override_doc(norm_slug, lang)
    if ov_archived:
        raise HTTPException(status_code=404, detail=f"Документ '{slug}' архівовано")

    md_text = None
    if ov_md:
        md_text = ov_md
    else:
        target_path = None
        if CONTENT_DIR.exists():
            for p in CONTENT_DIR.rglob("*.md"):
                if slugify(p.stem) == norm_slug:
                    if lang == "ua":
                        if p.parent.name != "en":
                            target_path = p
                            break

                    else: # lang == "en"
                        if p.parent.name == lang:
                            target_path = p
                            break

        if not target_path:
            raise HTTPException(status_code=404, detail=f"Документ '{slug}' не знайдено")

        md_text = target_path.read_text(encoding="utf-8")
    # Прибираємо плейсхолдер або биті wave0/ZA CDN зображення, і підставляємо локальне студійне фото якщо воно є
    img_slug = slugify(slug)
    local_product_img = IMAGES_DIR / "products" / f"{img_slug}.jpg"
    if local_product_img.exists():
        local_md_img = f"![doTERRA Product](/images/products/{img_slug}.jpg)"
        if re.match(r"^\s*!\[[^\]]*\]\([^)]*\)", md_text):
            md_text = re.sub(
                r"^\s*!\[[^\]]*\]\([^)]*\)",
                local_md_img,
                md_text,
                count=1,
            )
        else:
            md_text = f"{local_md_img}\n\n{md_text}"
    else:
        md_text = re.sub(
            r"^!\[[^\]]*\]\((?:Тут_буде_офіційне_фото_після_завантаження_через_бот|[^)]*(?:New-Default-Image|pool=wave0|-za-en-web\.)[^)]*)\)\s*\n*",
            "",
            md_text,
            count=1,
            flags=re.MULTILINE,
        )
    html_content = _render_md(md_text)
    
    # Робимо відносні посилання на картинки абсолютними (щоб працювали в React)
    base_url = str(request.base_url).rstrip("/")
    if request.headers.get("x-forwarded-proto") == "https":
        base_url = base_url.replace("http://", "https://")
    html_content = html_content.replace('src="/images/', f'src="{base_url}/images/')
    
    # Витягнемо заголовок з першого рядка якщо це H1, або просто використаємо slug
    title = slug
    lines = md_text.splitlines()
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
    title = re.sub(r"\s*\((?:чанк|chunk)\s*\d+\)", "", title, flags=re.IGNORECASE).strip()

    return {"title": title, "content": html_content, "slug": slug}


# ---------------------------------------------------------------------------
# Маршрути (старі, для перегляду в браузері)
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Список усіх документів."""
    docs = _get_all_docs()
    if not docs:
        items = "<p>Документи не знайдено.</p>"
    else:
        items = "<ul>" + "".join(
            f'<li><a href="/docs/{html.escape(d["slug"], quote=True)}">{html.escape(d["filename"])}</a></li>'
            for d in docs
        ) + "</ul>"

    body = f"<h1>doTERRA — База знань</h1>{items}"
    return HTMLResponse(_html_page("doTERRA Docs", body))


@app.get("/docs/{slug}", response_class=HTMLResponse)
async def view_doc(slug: str) -> HTMLResponse:
    """Повний вміст MD-файлу, відрендерений у HTML."""
    if not slug.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Невірний slug")

    target_path = None
    if CONTENT_DIR.exists():
        for p in CONTENT_DIR.rglob("*.md"):
            if slugify(p.stem) == slug:
                target_path = p
                break

    if not target_path:
        raise HTTPException(status_code=404, detail=f"Документ '{slug}' не знайдено")

    md_text = target_path.read_text(encoding="utf-8")
    # Прибираємо плейсхолдер або биті wave0/ZA CDN зображення, і підставляємо локальне студійне фото якщо воно є
    img_slug = slugify(slug)
    local_product_img = IMAGES_DIR / "products" / f"{img_slug}.jpg"
    if local_product_img.exists():
        local_md_img = f"![doTERRA Product](/images/products/{img_slug}.jpg)"
        if re.match(r"^\s*!\[[^\]]*\]\([^)]*\)", md_text):
            md_text = re.sub(
                r"^\s*!\[[^\]]*\]\([^)]*\)",
                local_md_img,
                md_text,
                count=1,
            )
        else:
            md_text = f"{local_md_img}\n\n{md_text}"
    else:
        md_text = re.sub(
            r"^!\[[^\]]*\]\((?:Тут_буде_офіційне_фото_після_завантаження_через_бот|[^)]*(?:New-Default-Image|pool=wave0|-za-en-web\.)[^)]*)\)\s*\n*",
            "",
            md_text,
            count=1,
            flags=re.MULTILINE,
        )
    html_content = _render_md(md_text)

    body = (
        '<a class="back" href="/">← До списку документів</a>'
        + html_content
    )
    return HTMLResponse(_html_page(f"doTERRA — {slug}", body))
