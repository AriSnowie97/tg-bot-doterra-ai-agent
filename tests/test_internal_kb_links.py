"""Службові матеріали бази знань не повинні ставати кнопками-статтями про продукти."""

from src.agent.product_links import (
    extract_product_links,
    is_internal_kb_slug,
    strip_internal_kb_links,
)


def test_internal_slug_detection():
    for slug in (
        "03_intake_flow_and_routing",
        "03-intake-flow-and-routing",
        "01_oils_safety_reference",
        "#/article/02-emotional-themes-map",
    ):
        assert is_internal_kb_slug(slug), slug
    assert not is_internal_kb_slug("lavender")
    assert not is_internal_kb_slug("doterra-serenity")


def test_extract_skips_internal_links():
    text = (
        "🔹 [Лаванда](lavender) для спокою. "
        "Деталі: [Логіка бота](03_intake_flow_and_routing), "
        "[Довідник безпеки олій](01_oils_safety_reference)."
    )
    slugs = [s for _, s in extract_product_links(text)]
    assert "lavender" in slugs
    assert not any(s.startswith(("01", "03")) for s in slugs)


def test_strip_internal_links_keeps_product_links():
    out = strip_internal_kb_links("[Лаванда](lavender) і [Довідник](01_oils_safety_reference)")
    assert "[Лаванда](lavender)" in out
    assert "01_oils_safety_reference" not in out
    assert "Довідник" not in out


def test_strip_internal_links_removes_dangling_label_at_end():
    text = "Пораджу лаванду.\n\n[Довідник безпеки олій](01_oils_safety_reference)"
    out = strip_internal_kb_links(text)
    assert out == "Пораджу лаванду."


def test_strip_internal_kb_references_from_context():
    from src.agent.product_links import strip_internal_kb_references

    content = (
        "Лаванда — заспокійлива олія.\n"
        "* [Довідник безпеки](01_oils_safety_reference) — правила\n"
        "* [Лаванда Touch](lavender-touch) — ролер"
    )
    out = strip_internal_kb_references(content)
    assert "01_oils_safety_reference" not in out
    assert "lavender-touch" in out
    assert "заспокійлива" in out


def test_intake_doc_hidden_from_articles_list():
    from src.web.app import HIDDEN_ARTICLE_SLUGS

    assert "03-intake-flow-and-routing" in HIDDEN_ARTICLE_SLUGS

