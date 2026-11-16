"""Тести міжсервісного маршруту POST /v1/aroma/ask для інтеграції з Аромакадемією."""

import importlib

from fastapi.testclient import TestClient

from src.agent import prompt as prompt_mod

web_app_mod = importlib.import_module("src.web.app")


def test_v1_aroma_ask_requires_configured_token(monkeypatch):
    monkeypatch.delenv("AROMA_SERVICE_TOKEN", raising=False)
    client = TestClient(web_app_mod.app)
    res = client.post(
        "/v1/aroma/ask",
        json={"message": "Що таке лаванда?"},
        headers={"X-Service-Token": "any"},
    )
    assert res.status_code == 503


def test_v1_aroma_ask_rejects_invalid_token(monkeypatch):
    monkeypatch.setenv("AROMA_SERVICE_TOKEN", "expected-secret")
    client = TestClient(web_app_mod.app)
    res = client.post(
        "/v1/aroma/ask",
        json={"message": "Що таке лаванда?"},
        headers={"X-Service-Token": "wrong-secret"},
    )
    assert res.status_code == 401


def test_v1_aroma_ask_forwards_lesson_context_and_cleans_markdown_links(monkeypatch):
    monkeypatch.setenv("AROMA_SERVICE_TOKEN", "expected-secret")
    captured: dict = {}

    async def fake_generate_response(user_text: str, **kwargs):
        captured["user_text"] = user_text
        captured["extra_chunks"] = kwargs.get("extra_chunks")
        return (
            "🌿 **[Лаванда](lavender)** чудово підходить для вечірнього відпочинку. "
            "Деталі у [Наталії](https://www.instagram.com/nkotelianska/)."
        )

    monkeypatch.setattr(web_app_mod, "generate_response", fake_generate_response)

    client = TestClient(web_app_mod.app)
    res = client.post(
        "/v1/aroma/ask",
        json={
            "user_id": "u_1",
            "tariff": "standard",
            "lesson_id": "lesson_1_1",
            "language": "uk",
            "message": "Розкажи про лаванду",
            "lesson_context": [
                {
                    "lesson_id": "lesson_1_1",
                    "title": "1.1 Основи",
                    "source_ref": "Урок 1.1",
                    "text": "Лаванда має м'який аромат.",
                }
            ],
        },
        headers={"X-Service-Token": "expected-secret"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["safety"]["triggered"] is False
    assert "**" not in body["answer"]
    assert "[Лаванда](lavender)" not in body["answer"]
    assert "Лаванда чудово підходить" in body["answer"]
    assert "https://www.instagram.com/nkotelianska/" in body["answer"]
    assert captured["extra_chunks"][0]["is_course_material"] is True
    assert "Лаванда має м'який аромат." in captured["extra_chunks"][0]["content"]


def test_v1_aroma_ask_reports_safety_flag_for_cat_or_red_flag(monkeypatch):
    monkeypatch.setenv("AROMA_SERVICE_TOKEN", "expected-secret")

    async def fake_generate_response(user_text: str, **kwargs):
        return "Для котиків потрібна консультація Наталії."

    monkeypatch.setattr(web_app_mod, "generate_response", fake_generate_response)

    client = TestClient(web_app_mod.app)
    res = client.post(
        "/v1/aroma/ask",
        json={"message": "Чи можна лаванду для мого кота?"},
        headers={"X-Service-Token": "expected-secret"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["safety"]["triggered"] is True
    assert body["safety"]["route_to"] == "natalia_or_doctor"
    assert body["safety"]["reason"] == "cat_safety"


def test_build_system_prompt_formats_course_material_without_product_slug():
    prompt_text = prompt_mod.build_system_prompt(
        [
            {
                "is_course_material": True,
                "course_label": "Матеріал уроку Аромакадемії: 1.1 Основи",
                "content": "Ефірні олії — леткі ароматичні сполуки.",
            }
        ]
    )
    assert "[Матеріал уроку Аромакадемії: 1.1 Основи]" in prompt_text
    assert "Ефірні олії — леткі ароматичні сполуки." in prompt_text
    assert "[product_slug: unknown]" not in prompt_text
