"""Журнал подій безпеки.

Усі підозрілі та чутливі події (спроби злому, відмови в доступі, перевищення лімітів,
робота з пам'яттю про користувача) пишуться в stdout одним рядком у форматі

    [SECURITY] 2026-10-25T12:00:00+00:00 event=prompt_injection user_id=1 chat_id=2 chat_type=private

Сюди ніколи не потрапляє текст повідомлень користувача, лише службові поля, ідентифікатори
та довжини. Значення проходять через redact() і обрізаються, а керівні символи прибираються
(захист від підміни рядків журналу).
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

from src.safety import redact

_MAX_VALUE_LEN = 120
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f  ]")
_FIELD_NAME = re.compile(r"[^a-z0-9_]")


def _clean(value: Any) -> str:
    text = _CONTROL_CHARS.sub(" ", redact(str(value)))
    text = text.replace('"', "'").strip()
    return text[:_MAX_VALUE_LEN]


# Захист журналу від флуду: не більше _BURST_LIMIT записів одного типу за _BURST_WINDOW секунд,
# далі лишається один підсумковий рядок про пропущені записи.
_BURST_LIMIT = 30
_BURST_WINDOW = 10.0
_burst: dict[str, list[float]] = {}


def _throttled(event: str) -> bool:
    now = time.monotonic()
    state = _burst.setdefault(event, [now, 0, 0])  # [початок вікна, записано, пропущено]
    if now - state[0] > _BURST_WINDOW:
        if state[2]:
            print(f"[SECURITY] event={event} suppressed={int(state[2])} window_s={int(_BURST_WINDOW)}", flush=True)
        state[0], state[1], state[2] = now, 0, 0
    state[1] += 1
    if state[1] > _BURST_LIMIT:
        state[2] += 1
        return True
    return False


def log_security_event(event: str, **fields: Any) -> None:
    """Пише один рядок у журнал безпеки. Ніколи не кидає винятків."""
    try:
        if _throttled(_FIELD_NAME.sub("_", event.lower())[:60]):
            return
        parts = [f"event={_FIELD_NAME.sub('_', event.lower())[:60]}"]
        for key, value in fields.items():
            if value is None:
                continue
            cleaned = _clean(value)
            if " " in cleaned:
                cleaned = f'"{cleaned}"'
            parts.append(f"{_FIELD_NAME.sub('_', key.lower())[:30]}={cleaned}")
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(f"[SECURITY] {stamp} " + " ".join(parts), flush=True)
    except Exception:  # журнал не повинен ламати обробку повідомлень
        pass


def message_fields(message: Any) -> dict[str, Any]:
    """Службові поля повідомлення для журналу (без тексту)."""
    user = getattr(message, "from_user", None)
    chat = getattr(message, "chat", None)
    text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    return {
        "user_id": getattr(user, "id", None),
        "chat_id": getattr(chat, "id", None),
        "chat_type": getattr(getattr(chat, "type", None), "value", getattr(chat, "type", None)),
        "text_len": len(text),
    }
