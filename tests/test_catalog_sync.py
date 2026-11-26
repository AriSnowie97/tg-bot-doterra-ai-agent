"""Тести глобального моніторингу та безпечної автосинхронізації каталогу doTERRA."""

from unittest.mock import MagicMock, patch
import pytest

from src.catalog_sync.markets import (
    GLOBAL_MARKETS,
    MarketConfig,
    is_official_doterra_url,
    normalize_product_slug,
)
from src.catalog_sync.service import (
    format_sync_report_html,
    infer_category,
    run_catalog_sync,
)


def test_global_markets_coverage_and_us_priority():
    assert len(GLOBAL_MARKETS) >= 15
    assert GLOBAL_MARKETS[0].code == "US"
    codes = {m.code for m in GLOBAL_MARKETS}
    for required in ("US", "EU", "UK", "CA", "AU", "JP", "BR"):
        assert required in codes


@pytest.mark.parametrize("url,expected", [
    ("https://www.doterra.com/US/en/p/lavender-oil", True),
    ("https://media.doterra.com/us/en/pips/lavender.pdf", True),
    ("http://www.doterra.com/US/en/p/lavender-oil", False),
    ("https://evil-doterra.com/US/en/p/lavender-oil", False),
    ("https://doterra.com.attacker.tld/x", False),
])
def test_is_official_doterra_url(url, expected):
    assert is_official_doterra_url(url) is expected


def test_normalize_product_slug():
    assert normalize_product_slug("lavender-oil") == "lavender"
    assert normalize_product_slug("naio-wood-essential-oil") == "naio-wood"
    assert normalize_product_slug("castor-oil") == "castor-oil"
    assert normalize_product_slug("IKISE_Skin_Care") == "ikise-skin-care"


@pytest.mark.parametrize("slug,title,expected_ua,expected_en", [
    ("volo-diffuser", "Volo Diffuser", "Дифузори", "Diffusers"),
    ("lavender-touch", "Lavender Touch", "Ролери (Touch)", "Roll-ons (Touch)"),
    ("ikise-dual-serum", "IKISE Dual Serum", "Догляд за собою", "Personal Care"),
    ("metapwr-advantage", "MetaPWR Advantage", "БАДи", "Supplements"),
    ("natures-rx-kit", "Nature's Rx Kit", "Набори", "Kits & Collections"),
])
def test_infer_category(slug, title, expected_ua, expected_en):
    assert infer_category(slug, title) == (expected_ua, expected_en)


@pytest.mark.anyio
async def test_circuit_breaker_blocks_archiving_when_few_healthy_markets():
    markets = (
        MarketConfig("US", "US", "/US/en"),
        MarketConfig("EU", "EU", "/EU/en"),
    )
    # Обидва ринки повернули замало товарів -> здорових < 3 -> архівація заблокована
    with patch("src.catalog_sync.service.scan_market", return_value={"lavender": "https://www.doterra.com/US/en/p/lavender-oil"}), \
         patch("src.catalog_sync.service._get_static_product_slugs", return_value={"lavender": MagicMock(), "old-item": MagicMock()}), \
         patch("src.catalog_sync.service.get_all_override_states", return_value={"old-item": {"status": "active", "missing_streak": 5, "markets": [], "has_md": False}}):
        report = await run_catalog_sync(markets=markets, write_files=False, save_db=False, dry_run=True)

    assert report["markets_healthy"] == 0
    assert report["archived"] == []
    assert "Автоархівацію пропущено" in report["archive_skipped_reason"]


@pytest.mark.anyio
async def test_adds_new_product_and_archives_only_after_3_misses(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY_1", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    markets = (
        MarketConfig("US", "US", "/US/en"),
        MarketConfig("EU", "EU", "/EU/en"),
        MarketConfig("UK", "UK", "/GB/en_GB"),
    )
    # 20 існуючих + 1 новинка на всіх 3 ринках (кожен ринок здоровий >= 15 товарів)
    base_slugs = {f"oil-{i}": f"https://www.doterra.com/US/en/p/oil-{i}" for i in range(20)}
    discovered_map = {**base_slugs, "brand-new-oil": "https://www.doterra.com/US/en/p/brand-new-oil"}
    static_map = {
        **{k: MagicMock() for k in base_slugs},
        "gone-once": MagicMock(),
        "gone-three-times": MagicMock(),
    }
    db_states = {
        "gone-once": {"status": "active", "missing_streak": 0, "markets": ["US"], "has_md": False},
        "gone-three-times": {"status": "active", "missing_streak": 2, "markets": ["US"], "has_md": False},
    }
    fake_page = {
        "title": "Brand New Oil 2026",
        "description": "Fresh official oil for daily balance.",
        "image_url": "https://www.doterra.com/medias/brand-new-oil.png",
        "source_url": "https://www.doterra.com/US/en/p/brand-new-oil",
        "excerpt": "Official excerpt",
    }

    upserted = []
    streaks = []

    with patch("src.catalog_sync.service.scan_market", return_value=discovered_map), \
         patch("src.catalog_sync.service._get_static_product_slugs", return_value=static_map), \
         patch("src.catalog_sync.service.get_all_override_states", return_value=db_states), \
         patch("src.catalog_sync.service.ensure_catalog_tables", return_value=True), \
         patch("src.catalog_sync.service.parse_product_page", return_value=fake_page), \
         patch("src.catalog_sync.service.upsert_catalog_item", side_effect=lambda x: upserted.append(x) or True), \
         patch("src.catalog_sync.service._vectorize_markdown_to_rag"), \
         patch("src.catalog_sync.service.record_missing_streak", side_effect=lambda s, st, archive: streaks.append((s, st, archive)) or True), \
         patch("src.catalog_sync.service.log_sync_run"):
        report = await run_catalog_sync(markets=markets, write_files=False, save_db=True, dry_run=False)

    assert report["markets_healthy"] == 3
    assert [a["slug"] for a in report["added"]] == ["brand-new-oil"]
    assert upserted[0]["markets"] == ["US", "EU", "UK"]
    assert upserted[0]["change_type"] == "new"
    # gone-once отримує streak=1 без архівації; gone-three-times досягає 3 і архівується
    assert ("gone-once", 1, False) in streaks
    assert ("gone-three-times", 3, True) in streaks
    assert report["archived"] == ["gone-three-times"]

    html_report = format_sync_report_html(report)
    assert "Brand New Oil 2026" in html_report
    assert "Gone Three Times" in html_report
    assert "США" in html_report


def test_jp_kr_mx_translation_detection_and_regional_dedup():
    from src.catalog_sync.service import _canonical_alias, _clean_product_title, _needs_translation

    assert _canonical_alias("black-pepper-oil-jp") == _canonical_alias("black-pepper")
    assert _canonical_alias("basil-oil-jp") == _canonical_alias("basil")
    assert _canonical_alias("aromatouch-massage-blend") == _canonical_alias("aromatouch")
    assert _canonical_alias("brave-roll-on") == _canonical_alias("brave")
    assert _canonical_alias("zengest") == _canonical_alias("digestzen")
    assert _canonical_alias("adaptive-calming-blend-capsules") == _canonical_alias("adaptiv-calming-blend-capsules")

    assert _clean_product_title("Baking Spice - dōTERRA Product Information | Aceites esenciales dōTERRA") == "Baking Spice"
    assert _needs_translation({"title_ua": "ブラックペッパー", "md_ua": "test"}) is True
    assert _needs_translation({"title_ua": "Stress Bundle", "short_ua": "The Stress Bundle brings together...", "md_ua": "x"}) is True
    assert _needs_translation({"title_ua": "Дифузор Ведмедик", "title_en": "Bear Diffuser", "short_ua": "Компактний дифузор", "md_ua": "# Дифузор", "md_en": "# Diffuser"}) is False


@pytest.mark.anyio
async def test_restored_product_marked_with_returned_change_type(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY_1", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    markets = (
        MarketConfig("US", "US", "/US/en"),
        MarketConfig("EU", "EU", "/EU/en"),
        MarketConfig("UK", "UK", "/GB/en_GB"),
    )
    base_slugs = {f"oil-{i}": f"https://www.doterra.com/US/en/p/oil-{i}" for i in range(18)}
    discovered_map = {**base_slugs, "seasonal-oil": "https://www.doterra.com/US/en/p/seasonal-oil"}
    static_map = {**{k: MagicMock() for k in base_slugs}, "seasonal-oil": MagicMock()}
    db_states = {
        "seasonal-oil": {"status": "archived", "missing_streak": 3, "markets": ["US"], "has_md": False},
    }
    upserted = []

    with patch("src.catalog_sync.service.scan_market", return_value=discovered_map), \
         patch("src.catalog_sync.service._get_static_product_slugs", return_value=static_map), \
         patch("src.catalog_sync.service.get_all_override_states", return_value=db_states), \
         patch("src.catalog_sync.service.ensure_catalog_tables", return_value=True), \
         patch("src.catalog_sync.service.upsert_catalog_item", side_effect=lambda x: upserted.append(x) or True), \
         patch("src.catalog_sync.service.log_sync_run"):
        report = await run_catalog_sync(markets=markets, write_files=False, save_db=True, dry_run=False)

    assert [r["slug"] for r in report["restored"]] == ["seasonal-oil"]
    assert upserted[0]["slug"] == "seasonal-oil"
    assert upserted[0]["change_type"] == "returned"
    assert upserted[0]["status"] == "active"
    assert upserted[0]["markets"] == ["US", "EU", "UK"]
