"""
Тести для модуля автопублікації постів у Telegram-канал (src/publisher).
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.agent.specialist import MEDICAL_DISCLAIMER, EN_MEDICAL_DISCLAIMER
from src.publisher.service import (
    _strip_disclaimer,
    _build_post_url,
    _ensure_clean_post,
    publish_channel_post,
)


class TestStripDisclaimer:
    """Перевірка повного очищення медичного дисклеймера з постів."""

    def test_strip_exact_ukrainian_disclaimer(self):
        text = f"Чудовий пост про користь лаванди 🌿\n\n{MEDICAL_DISCLAIMER}"
        cleaned = _strip_disclaimer(text)
        assert "не є медичною консультацією" not in cleaned
        assert "проконсультуйтеся з лікарем" not in cleaned
        assert cleaned == "Чудовий пост про користь лаванди 🌿"

    def test_strip_exact_english_disclaimer(self):
        text = f"Wonderful post about lavender 🌿\n\n{EN_MEDICAL_DISCLAIMER}"
        cleaned = _strip_disclaimer(text)
        assert "medical advice" not in cleaned
        assert cleaned == "Wonderful post about lavender 🌿"

    def test_strip_custom_disclaimer_lines(self):
        # Випадок зі скріншоту 1 користувача
        text = (
            "Чи використовуєте ви такі практики у своїй рутині?\n"
            "Поділіться у коментарях та ставте ❤️ або 🔥, якщо пост був для вас корисним!\n\n"
            "ℹ️ Ця інформація має ознайомлювальний характер і не є медичною консультацією. "
            "Перед застосуванням проконсультуйтеся з лікарем."
        )
        cleaned = _strip_disclaimer(text)
        assert "не є медичною консультацією" not in cleaned
        assert "проконсультуйтеся з лікарем" not in cleaned
        assert "ℹ️" not in cleaned
        assert cleaned.endswith("якщо пост був для вас корисним!")

    def test_keep_normal_text_intact(self):
        text = "Лаванда та м'ята — чудовий дует для вечірнього спокою і релаксу ✨"
        assert _strip_disclaimer(text) == text


class TestBuildPostUrl:
    """Перевірка генерації посилань на опублікований пост у каналі."""

    def test_url_from_chat_username(self):
        mock_msg = MagicMock()
        mock_msg.message_id = 155
        mock_msg.chat.username = "nkotelianskablog"

        url = _build_post_url("@test_channel", mock_msg)
        assert url == "https://t.me/nkotelianskablog/155"

    def test_url_from_at_channel_id(self):
        mock_msg = MagicMock()
        mock_msg.message_id = 99
        mock_msg.chat = None

        url = _build_post_url("@my_doterra_club", mock_msg)
        assert url == "https://t.me/my_doterra_club/99"

    def test_url_from_numeric_channel_id(self):
        mock_msg = MagicMock()
        mock_msg.message_id = 42
        mock_msg.chat = None

        url = _build_post_url("-1002345678901", mock_msg)
        assert url == "https://t.me/c/2345678901/42"

    def test_url_from_link_channel_id(self):
        mock_msg = MagicMock()
        mock_msg.message_id = 12
        mock_msg.chat = None

        url = _build_post_url("https://t.me/nkotelianskablog", mock_msg)
        assert url == "https://t.me/nkotelianskablog/12"


@pytest.mark.anyio
class TestPublishChannelPost:
    """Тестування publish_channel_post: відсутність дисклеймера і посилання для адміна."""

    async def test_publish_omits_disclaimer_and_notifies_admins(self, monkeypatch):
        monkeypatch.setenv("CHANNEL_ID", "@testchannel")
        monkeypatch.setenv("ADMIN_IDS", "12345678")

        mock_bot = AsyncMock()
        sent_channel_msg = MagicMock()
        sent_channel_msg.message_id = 777
        sent_channel_msg.chat.username = "testchannel"
        mock_bot.send_message.return_value = sent_channel_msg

        fake_generated_post = (
            "ТВІЙ ПРИРОДНИЙ ЩИТ У ЗИМОВИЙ СЕЗОН 🌿 🔥\n\n"
            "Зима приносить не лише затишок, а й виклики для імунітету.\n\n"
            "Ставте ❤️ якщо корисно!\n\n"
            + MEDICAL_DISCLAIMER
        )

        with patch("src.publisher.service._generate_post_text", new=AsyncMock(return_value=fake_generated_post)):
            post_url = await publish_channel_post(mock_bot)

        assert post_url == "https://t.me/testchannel/777"

        # 1. Перевірка відправки посту у канал
        assert mock_bot.send_message.call_count == 2
        channel_call = mock_bot.send_message.call_args_list[0]
        channel_text = channel_call.kwargs["text"]

        assert "не є медичною консультацією" not in channel_text
        assert "проконсультуйтеся з лікарем" not in channel_text
        assert "ТВІЙ ПРИРОДНИЙ ЩИТ" in channel_text

        # 2. Перевірка сповіщення адміну (скріншот 2: посилання "Читати далі" і перехід у ТГК)
        admin_call = mock_bot.send_message.call_args_list[1]
        admin_text = admin_call.kwargs["text"]
        admin_markup = admin_call.kwargs["reply_markup"]

        assert admin_call.kwargs["chat_id"] == 12345678
        assert "📢 <b>Опубліковано новий пост у канал!</b>" in admin_text
        assert "👉 <a href=\"https://t.me/testchannel/777\">Читати далі</a>" in admin_text
        assert admin_markup is not None
        button = admin_markup.inline_keyboard[0][0]
        assert button.text == "📖 Читати далі в каналі"
        assert button.url == "https://t.me/testchannel/777"
