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
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import markdown

from pydantic import BaseModel
from src.agent import generate_response

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


def _get_all_docs() -> list[dict]:
    """Повертає список усіх MD-файлів із директорії docs."""
    if not DOCS_DIR.exists():
        return []
    return sorted(
        [
            {"slug": p.stem, "filename": p.name}
            for p in DOCS_DIR.glob("*.md")
        ],
        key=lambda d: d["slug"],
    )


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


@app.get("/api/docs/{slug}")
async def api_get_doc(slug: str):
    """Повертає відрендерений HTML статті у форматі JSON для React-додатку."""
    if not slug.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Невірний slug")

    md_path = DOCS_DIR / f"{slug}.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail=f"Документ '{slug}' не знайдено")

    md_text = md_path.read_text(encoding="utf-8")
    html_content = _render_md(md_text)
    
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

    md_path = DOCS_DIR / f"{slug}.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail=f"Документ '{slug}' не знайдено")

    md_text = md_path.read_text(encoding="utf-8")
    html_content = _render_md(md_text)

    body = (
        '<a class="back" href="/">← До списку документів</a>'
        + html_content
    )
    return HTMLResponse(_html_page(f"doTERRA — {slug}", body))
