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


def test_parse_product_page_rejects_wave0_and_uses_working_fallback():
    from src.catalog_sync.markets import parse_product_page

    html_with_wave0 = """
    <html><head>
      <title>Baking Spice | dōTERRA Essential Oils</title>
      <meta property="og:description" content="Warm baking spice blend.">
      <meta property="og:image" content="https://www.doterra.com/medias/bakingspice.jpg?context=abc&amp;pool=wave0">
    </head><body>
      <img src="https://prd-evo-content.doterra.com/europe/images/products/bakingspice-5ml-large.png" />
      <p>Official doTERRA Baking Spice blend description text long enough to pass minimum page length check.</p>
      <p>Warm ginger, cardamom, cassia, clove, and cinnamon bark essential oils for culinary creations and cozy aroma.</p>
    </body></html>
    """
    with patch("src.catalog_sync.markets.fetch_html", return_value=html_with_wave0):
        meta = parse_product_page("https://www.doterra.com/MX/es_MX/p/baking-spice")
    assert meta is not None
    assert "pool=wave0" not in meta["image_url"]
    assert meta["image_url"] == "https://prd-evo-content.doterra.com/europe/images/products/bakingspice-5ml-large.png"


def test_merge_markdown_cards_appends_unique_info_without_duplicates():
    from src.catalog_sync.service import _merge_markdown_cards

    primary = (
        "![doTERRA Product](/images/products/test.jpg)\n\n"
        "# Test Oil\n\n"
        "## Короткий опис\n\n"
        "👑 М'яка цитрусова олія для настрою\n\n"
        "## Застереження\n\n"
        "> ⚠️ Зберігати в недоступному для дітей місці.\n\n"
        "#doterra #test\n"
    )
    secondary = (
        "# Test Oil\n\n"
        "## Короткий опис\n\n"
        "👑 М'яка цитрусова олія для настрою\n"
        "👑 Додаткова корисна властивість для дифузора\n\n"
        "## Цікаві факти\n\n"
        "👑 Виготовлено методом холодного пресування\n\n"
        "## Застереження\n\n"
        "> ⚠️ Інший стандартний текст застереження.\n\n"
        "#doterra #newtag\n"
    )
    merged, added = _merge_markdown_cards(primary, secondary)
    assert added == 2
    assert merged.count("М'яка цитрусова олія для настрою") == 1
    assert "Додаткова корисна властивість для дифузора" in merged
    assert "Виготовлено методом холодного пресування" in merged
    assert "Інший стандартний текст застереження" not in merged
    assert "#newtag" in merged


def test_deduplicate_dynamic_overrides_removes_static_dups_and_merges_dynamic_dups():
    from src.catalog_sync.service import deduplicate_dynamic_overrides, _compact_alias

    assert _compact_alias("citrusbliss") == _compact_alias("citrus-bliss")
    assert _compact_alias("air-repair") == _compact_alias("air-x-air-blend")
    assert _compact_alias("deep-blue-stick") == _compact_alias("deep-blue-stick-copaiba")

    fake_overrides = [
        {
            "slug": "citrusbliss",
            "status": "active",
            "title_ua": "Citrus Bliss",
            "title_en": "Citrus Bliss",
            "md_ua": "# Citrus Bliss\n\n## Короткий опис\n\n👑 Test",
            "md_en": "# Citrus Bliss\n\n## Short Description\n\n👑 Test",
            "markets": ["MX"],
        },
        {
            "slug": "brand-new-oil",
            "status": "active",
            "title_ua": "Brand New Oil",
            "title_en": "Brand New Oil",
            "md_ua": "# Brand New Oil\n\n## Короткий опис\n\n👑 Опис США",
            "md_en": "# Brand New Oil\n\n## Short Description\n\n👑 US desc",
            "markets": ["US"],
            "image_url": "https://media.doterra.com/us/en/test.jpg",
        },
        {
            "slug": "brand-new-oil-eu",
            "status": "active",
            "title_ua": "Brand New Oil",
            "title_en": "Brand New Oil",
            "md_ua": "# Brand New Oil\n\n## Короткий опис\n\n👑 Унікальний факт з Європи",
            "md_en": "# Brand New Oil\n\n## Short Description\n\n👑 Unique EU fact",
            "markets": ["EU"],
            "image_url": "",
        },
    ]
    deleted = []
    upserted = []
    with patch("src.catalog_sync.store.get_catalog_overrides", return_value=(fake_overrides, set())), \
         patch("src.catalog_sync.service._get_static_product_slugs", return_value={"citrus-bliss": MagicMock(read_text=lambda encoding="utf-8": "# Citrus Bliss")}), \
         patch("src.catalog_sync.service.delete_catalog_override", side_effect=lambda s: deleted.append(s) or True), \
         patch("src.catalog_sync.service.upsert_catalog_item", side_effect=lambda x: upserted.append(x) or True), \
         patch("src.catalog_sync.service._vectorize_markdown_to_rag"):
        res = deduplicate_dynamic_overrides(dry_run=False)

    assert "citrusbliss" in deleted
    assert "brand-new-oil-eu" in deleted
    assert len(upserted) == 1
    assert upserted[0]["slug"] == "brand-new-oil"
    assert set(upserted[0]["markets"]) == {"US", "EU"}
    assert "Унікальний факт з Європи" in upserted[0]["md_ua"]
    assert len(res["removed"]) == 2
    assert len(res["merged"]) == 1
