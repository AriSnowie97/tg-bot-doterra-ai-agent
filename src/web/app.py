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
import os
from pathlib import Path
# Special
import re
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import markdown

from pydantic import BaseModel
from src.agent import generate_response
from src.content.parser import slugify

# ---------------------------------------------------------------------------
# Налаштування
# ---------------------------------------------------------------------------

DOCS_DIR = Path(__file__).parent.parent / "content" / "docs"

app = FastAPI(title="doTERRA Docs Viewer", docs_url=None, redoc_url=None)

# Додаємо CORS для того, щоб React (який запущено на іншому порту чи домені) міг робити запити
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшені краще вказати конкретні домени (наприклад, ваш github.io)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтуємо папку з картинками
IMAGES_DIR = Path(__file__).parent.parent / "content" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")


# ---------------------------------------------------------------------------
# Моделі
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    response: str


# ---------------------------------------------------------------------------
# Допоміжні функції
# ---------------------------------------------------------------------------

def _render_md(md_text: str) -> str:
    """Конвертує Markdown-текст у HTML."""
    return markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "nl2br"]
    )


def _get_article_metadata(md_path: Path, base_url: str = "", section_name: str = "") -> dict:
    """Витягує метадані з .md файлу."""
    original_stem = md_path.stem
    slug = slugify(original_stem)
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    
    title = original_stem
    short = ""
    category = "Інше"
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
                # Якщо картинка це шаблонний текст
                if image == "Тут_буде_офіційне_фото_після_завантаження_через_бот":
                    image = ""
            break

    # Шукаємо заголовок
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break
            
    # Шукаємо категорію
    for line in lines:
        if "**Категорія:**" in line:
            category = line.split("**Категорія:**")[1].strip()
            if "→" in category:
                category = category.split("→")[0].strip()
            elif ">" in category:
                category = category.split(">")[0].strip()
            break
    
    if category == "Інше":
        if "_Гід" in original_stem or original_stem.startswith("0"):
            category = "Гайди"
            
    # Шукаємо короткий опис
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith("#"): continue
        if line.startswith("!["): continue
        if line.startswith("**Категорія:**") or line.startswith("**Тип:**") or line.startswith("**Артикул") or line.startswith("**Посилання"): continue
        if line.startswith("---"): continue
        
        short = line
        if len(short) > 120:
            short = short[:117] + "..."
        break
        
    return {
        "slug": slug,
        "title": title,
        "short": short,
        "tag": category,
        "image": image,
        "section": section_name
    }

CONTENT_DIR = Path(__file__).parent.parent / "content"
DIRECTORIES_TO_SEARCH = [
    "docs",
    "products",
    "symphony_of_the_cells",
    "advice",
    "kits"
]

def _get_all_docs() -> list[dict]:
    """Повертає список усіх MD-файлів із вказаних директорій."""
    if not CONTENT_DIR.exists():
        return []
        
    docs = []
    for dir_name in DIRECTORIES_TO_SEARCH:
        d = CONTENT_DIR / dir_name
        if d.exists():
            for p in d.glob("*.md"):
                docs.append({"slug": slugify(p.stem), "filename": p.name})
                
    return sorted(docs, key=lambda d: d["slug"])


def _html_page(title: str, body: str) -> str:
    """Обгортає HTML-тіло в мінімальну сторінку."""
    return f"""<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
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

@app.post("/api/chat", response_model=ChatResponse)
async def api_chat(request: ChatRequest):
    """Ендпоінт для чату з Mini App."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        response_text = await generate_response(request.query)
        return ChatResponse(response=response_text)
    except Exception as e:
        print(f"[api_chat] Error: {e}")
        raise HTTPException(status_code=500, detail="Помилка при генерації відповіді")


@app.get("/api/articles")
async def api_get_articles(request: Request):
    """Повертає список усіх статей з метаданими для Mini App."""
    if not CONTENT_DIR.exists():
        return []
    
    base_url = str(request.base_url).rstrip("/")
    articles = []
    for dir_name in DIRECTORIES_TO_SEARCH:
        d = CONTENT_DIR / dir_name
        if d.exists():
            for md_path in d.glob("*.md"):
                # Пропускаємо технічні файли-гайди (01_Гід, 02_Гід тощо)
                if md_path.stem[0].isdigit() and "_Гід" in md_path.stem:
                    continue
                
                articles.append(_get_article_metadata(md_path, base_url, dir_name))
        
    # Сортуємо: спочатку гайди (якщо якісь залишились), потім інші за алфавітом
    articles.sort(key=lambda a: (0 if a["tag"] == "Гайди" else 1, a["title"]))
    return articles

@app.get("/api/docs/{slug}")
async def api_get_doc(slug: str, request: Request):
    """Повертає відрендерений HTML статті у форматі JSON для React-додатку."""
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
    html_content = _render_md(md_text)
    
    # Робимо відносні посилання на картинки абсолютними (щоб працювали в React)
    base_url = str(request.base_url).rstrip("/")
    html_content = html_content.replace('src="/images/', f'src="{base_url}/images/')
    
    # Витягнемо заголовок з першого рядка якщо це H1, або просто використаємо slug
    title = slug
    lines = md_text.splitlines()
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()

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
            f'<li><a href="/docs/{d["slug"]}">{d["filename"]}</a></li>'
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
    html_content = _render_md(md_text)

    body = (
        '<a class="back" href="/">← До списку документів</a>'
        + html_content
    )
    return HTMLResponse(_html_page(f"doTERRA — {slug}", body))
