"""
Глобальний моніторинг та автосинхронізація каталогу doTERRA по всіх ринках світу.

Підтримує два канали постійного збереження (переживають перезбірку контейнера):
1. PostgreSQL (`catalog_overrides`) — миттєве оновлення Mini App та RAG без передеплою.
2. Запис у `src/content/products/` (`--write-files`) — для GitHub Actions → Pull Request у Git.
"""

from .markets import GLOBAL_MARKETS, MarketConfig
from .store import (
    ensure_catalog_tables,
    get_catalog_overrides,
    get_override_doc,
    get_catalog_stats,
    invalidate_overrides_cache,
)
from .service import run_catalog_sync, format_sync_report_html

__all__ = [
    "GLOBAL_MARKETS",
    "MarketConfig",
    "ensure_catalog_tables",
    "get_catalog_overrides",
    "get_override_doc",
    "get_catalog_stats",
    "invalidate_overrides_cache",
    "run_catalog_sync",
    "format_sync_report_html",
]
