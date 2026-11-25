"""
Реєстр світових ринків doTERRA та безпечний HTTP/2 парсер офіційних сторінок doterra.com.
"""

from __future__ import annotations

import html as html_lib
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse


@dataclass(frozen=True)
class MarketConfig:
    code: str
    name: str
    prefix: str  # напр. "/US/en"


# 18 офіційних регіональних сайтів doTERRA по всьому світу (US — перший за пріоритетом)
GLOBAL_MARKETS: tuple[MarketConfig, ...] = (
    MarketConfig("US", "United States", "/US/en"),
    MarketConfig("CA", "Canada", "/CA/en"),
    MarketConfig("EU", "Europe", "/EU/en"),
    MarketConfig("UK", "United Kingdom", "/GB/en_GB"),
    MarketConfig("DE", "Germany", "/DE/de_DE"),
    MarketConfig("FR", "France", "/FR/fr_FR"),
    MarketConfig("IT", "Italy", "/IT/it_IT"),
    MarketConfig("ES", "Spain", "/ES/es_ES"),
    MarketConfig("PL", "Poland", "/PL/pl_PL"),
    MarketConfig("AU", "Australia", "/AU/en_AU"),
    MarketConfig("NZ", "New Zealand", "/NZ/en_NZ"),
    MarketConfig("ZA", "South Africa", "/ZA/en_ZA"),
    MarketConfig("IL", "Israel", "/IL/en_IL"),
    MarketConfig("SG", "Singapore", "/SG/en_SG"),
    MarketConfig("JP", "Japan", "/JP/ja_JP"),
    MarketConfig("KR", "South Korea", "/KR/ko_KR"),
    MarketConfig("BR", "Brazil", "/BR/pt_BR"),
    MarketConfig("MX", "Mexico", "/MX/es_MX"),
)

# Стандартні розділи каталогу doTERRA для виявлення новинок, святкових і лімітованих пропозицій
LISTING_PATHS: tuple[str, ...] = (
    "/pl/new-products",
    "/pl/holiday",
    "/pl/holiday-products",
    "/pl/holiday-gifts",
    "/pl/seasonal-offers",
    "/pl/single-oils",
    "/pl/proprietary-blends",
    "/pl/diffusers",
    "/pl/essential-oil-diffusers",
    "/pl/supplements",
    "/pl/skin-care",
    "/pl/personal-care-products",
    "/pl/essential-oil-kits",
    "/pl/home-care",
    "/pl/limited-time-offers",
)

_OFFICIAL_HOST_RE = re.compile(r"^(?:[a-zA-Z0-9-]+\.)*doterra\.com$")
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
_BAD_IMAGE_SUBSTRINGS = (
    "fallback_image",
    "default-image",
    "new-default-image",
    "targeted-solutions-sleep",
    "social_media",
    "placeholder",
)


def is_official_doterra_url(url: str) -> bool:
    """Сувора перевірка: дозволяємо запити ТІЛЬКИ до https://*.doterra.com."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme != "https":
            return False
        host = (parsed.hostname or "").lower()
        if not host or not _OFFICIAL_HOST_RE.match(host):
            return False
        return parsed.username is None and parsed.password is None and parsed.port in (None, 443)
    except Exception:
        return False


def _curl_bin() -> str | None:
    if platform.system().lower() == "windows":
        return shutil.which("curl.exe") or shutil.which("curl")
    return shutil.which("curl")


def fetch_html(url: str, timeout: int = 12) -> str:
    """Завантажує HTML офіційної сторінки doterra.com через HTTP/2 curl (або fallback requests)."""
    if not is_official_doterra_url(url):
        return ""

    curl = _curl_bin()
    if curl:
        try:
            proc = subprocess.run(
                [curl, "-sL", "--max-time", str(timeout), "-A", _UA, url],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            if proc.returncode == 0 and proc.stdout:
                return proc.stdout
        except Exception:
            pass

    try:
        import requests

        resp = requests.get(url, headers={"User-Agent": _UA}, timeout=timeout)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return ""


def normalize_product_slug(raw_slug: str) -> str:
    """Приводить URL-слаг doterra.com до уніфікованого slug бази знань."""
    s = raw_slug.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s).strip("-")
    # Прибираємо типові URL-суфікси, щоб 'lavender-oil' збігався з 'lavender'
    for suffix in ("-essential-oil", "-oil"):
        if s.endswith(suffix) and len(s) > len(suffix) + 2:
            # Зберігаємо для деяких складених назв (castor-oil)
            if s != "castor-oil":
                s = s[: -len(suffix)]
    return s


def scan_market(market: MarketConfig, timeout: int = 10) -> dict[str, str]:
    """Сканує один ринок doTERRA і повертає мапу {normalized_slug: full_product_url}."""
    base = f"https://www.doterra.com{market.prefix}"
    found: dict[str, str] = {}

    # 1. Пробуємо sitemap ринку (часто містить усі активні /p/ URL одним запитом!)
    sitemap_html = fetch_html(f"{base}/sitemap.xml", timeout=timeout)
    if sitemap_html and "/p/" in sitemap_html:
        pat_sm = re.compile(rf"https://www\.doterra\.com{re.escape(market.prefix)}/p/([a-zA-Z0-9_-]+)")
        for m in pat_sm.finditer(sitemap_html):
            raw = m.group(1)
            slug = normalize_product_slug(raw)
            if slug and slug not in found:
                found[slug] = m.group(0)

    # 2. Обходимо ключові розділи каталогу (/pl/...) — особливо важливо для новинок
    link_re = re.compile(rf'href="({re.escape(market.prefix)}/p/([a-zA-Z0-9_-]+))[^"]*"')
    for path in LISTING_PATHS:
        page = fetch_html(f"{base}{path}", timeout=timeout)
        if not page:
            continue
        for m in link_re.finditer(page):
            rel_url, raw = m.group(1), m.group(2)
            slug = normalize_product_slug(raw)
            if slug and slug not in found:
                found[slug] = f"https://www.doterra.com{rel_url}"

    return found


def parse_product_page(url: str, timeout: int = 12) -> dict | None:
    """Витягує метадані продукту з офіційної сторінки doterra.com."""
    page = fetch_html(url, timeout=timeout)
    if not page or len(page) < 400:
        return None

    # Перевірка на сторінку 404
    title_m = re.search(r"<title>([^<]+)</title>", page, re.I)
    raw_title = html_lib.unescape(title_m.group(1).strip()) if title_m else ""
    if not raw_title or "404" in raw_title or "page not found" in raw_title.lower():
        return None

    # Чистимо суфікс " | dōTERRA Essential Oils"
    clean_title = re.sub(r"\s*\|\s*d[oō]TERRA.*$", "", raw_title, flags=re.I).strip()
    if not clean_title:
        return None

    # Опис з og:description / meta description
    desc = ""
    for pat in (
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
    ):
        dm = re.search(pat, page, re.I)
        if dm:
            desc = html_lib.unescape(dm.group(1).strip())
            break

    # Суворий og:image (відсікаємо fallback-банери doTERRA)
    image_url = ""
    for pat in (
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    ):
        im = re.search(pat, page, re.I)
        if im:
            cand = urljoin(url, im.group(1).strip()).replace("&amp;", "&")
            low = cand.lower()
            if is_official_doterra_url(cand) and not any(b in low for b in _BAD_IMAGE_SUBSTRINGS):
                image_url = cand
                break

    # Витягуємо очищений фрагмент основного тексту сторінки (для збагачення картки)
    body_text = re.sub(r"<(script|style|noscript|svg)[^>]*>[\s\S]*?</\1>", " ", page, flags=re.I)
    body_text = re.sub(r"<[^>]+>", " ", body_text)
    body_text = html_lib.unescape(re.sub(r"\s+", " ", body_text)).strip()

    return {
        "title": clean_title,
        "description": desc,
        "image_url": image_url,
        "source_url": url,
        "excerpt": body_text[:3000],
    }
