"""
Планувальник автопублікацій у Telegram-канал.

Використовує APScheduler (AsyncIOScheduler) із cron-тригером.
Параметри розкладу читаються з .env:

    POST_SCHEDULE_DAYS=tue,fri   # дні тижня (дефолт: вт + пт)
    POST_SCHEDULE_HOUR=12        # година за часовим поясом розкладу (дефолт: 12:00 за Києвом)
    POST_SCHEDULE_MINUTE=0       # хвилина (дефолт: 0)
    POST_SCHEDULE_TZ=Europe/Kyiv # часовий пояс розкладу (враховує літній/зимовий час)

Використання:
    from src.scheduler import setup_scheduler

    scheduler = setup_scheduler(bot)
    scheduler.start()
    ...
    scheduler.shutdown()
"""

# Standard
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
# Special
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
# Local
from ..publisher import publish_channel_post
from ..catalog_sync import run_catalog_sync, format_sync_report_html, get_catalog_stats
from ..catalog_sync.service import retranslate_existing_overrides
from ..safety import redact


def _get_report_recipients() -> list[int]:
    """Повертає ID отримувачів звіту (лише ти і Наталія — CATALOG_REPORT_CHAT_IDS або ADMIN_IDS)."""
    raw = os.getenv("CATALOG_REPORT_CHAT_IDS") or os.getenv("ADMIN_IDS", "")
    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]


async def _startup_retranslate_overrides() -> None:
    """Разовий фоновий переклад неперекладених позицій (JP/KR/MX/EN-only) у БД після старту."""
    try:
        translated = await retranslate_existing_overrides(limit=20)
        if translated:
            print(f"[scheduler] 🌐 Auto-translated {len(translated)} dynamic catalog items to UA+EN.")
    except Exception as e:
        print(f"[scheduler] ⚠️ Startup retranslation skipped: {redact(e)}")


# ---------------------------------------------------------------------------
# Зчитування конфігурації розкладу з env
# ---------------------------------------------------------------------------

_DAYS: str   = os.getenv("POST_SCHEDULE_DAYS", "tue,fri")
_HOUR: int   = int(os.getenv("POST_SCHEDULE_HOUR", "12"))
_MINUTE: int = int(os.getenv("POST_SCHEDULE_MINUTE", "0"))
_TZ_NAME: str = os.getenv("POST_SCHEDULE_TZ", "Europe/Kyiv")

# Автосинхронізація світових ринків doTERRA (дефолт: 2 рази на добу — о 04:00 та 16:00 за Києвом)
_CATALOG_SYNC_ENABLED: bool = os.getenv("ENABLE_CATALOG_SYNC", "1").strip().lower() not in ("0", "false", "no")
_CATALOG_SYNC_DAY: str = os.getenv("CATALOG_SYNC_DAY", "*")
_CATALOG_SYNC_HOURS: str = os.getenv("CATALOG_SYNC_HOURS", os.getenv("CATALOG_SYNC_HOUR", "4,16"))


async def _initial_catalog_sync_if_empty(bot: Bot) -> None:
    """Одноразовий стартовий прогін після першого деплою, якщо ще не було жодної синхронізації."""
    try:
        status = get_catalog_stats()
        if status.get("last_run"):
            print("[scheduler] ℹ️ Global catalog sync already has run history — skipping startup bootstrap.")
            return
    except Exception:
        pass
    print("[scheduler] 🌍 No prior catalog sync runs found — starting initial global sync...")
    await _scheduled_catalog_sync(bot)


async def _scheduled_catalog_sync(bot: Bot) -> None:
    """Фонова автосинхронізація каталогу doTERRA по всіх ринках + простий звіт лише для тебе та Наталії."""
    recipients = _get_report_recipients()
    try:
        report = await run_catalog_sync(write_files=False, save_db=True)
        has_visible_changes = bool(
            report.get("added")
            or report.get("restored")
            or report.get("archived")
        )
        if has_visible_changes and recipients:
            text = format_sync_report_html(report)
            for chat_id in recipients:
                try:
                    await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
                except Exception:
                    pass
    except Exception as e:
        print(f"[scheduler] ❌ Catalog auto-sync error: {redact(e)}")
        for chat_id in recipients:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text="⚠️ Не вдалося автоматично перевірити оновлення каталогу doTERRA. Спробуємо ще раз за розкладом.",
                    parse_mode="HTML",
                )
            except Exception:
                pass


def _resolve_timezone():
    """Часовий пояс розкладу. Якщо база tzdata не знайшла назву — UTC (години тоді рахуються за UTC)."""
    for name in (_TZ_NAME, "Europe/Kiev"):
        try:
            return ZoneInfo(name)
        except Exception:
            continue
    print(f"[scheduler] ⚠️ Часовий пояс {_TZ_NAME!r} не знайдено, використовую UTC")
    return timezone.utc


# ---------------------------------------------------------------------------
# Налаштування планувальника
# ---------------------------------------------------------------------------

def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Створює та налаштовує AsyncIOScheduler із задачею публікації постів.

    Args:
        bot: Aiogram Bot instance — передається у publish_channel_post.

    Returns:
        Налаштований AsyncIOScheduler (ще не запущений).

    Schedule:
        Cron-тригер: POST_SCHEDULE_DAYS о POST_SCHEDULE_HOUR:POST_SCHEDULE_MINUTE за POST_SCHEDULE_TZ.
        Дефолт: вівторок + п'ятниця о 12:00 за Києвом (і влітку, і взимку).
    """
    tz = _resolve_timezone()
    scheduler = AsyncIOScheduler(timezone=tz)

    trigger = CronTrigger(
        day_of_week=_DAYS,
        hour=_HOUR,
        minute=_MINUTE,
        timezone=tz,
    )

    scheduler.add_job(
        func=publish_channel_post,
        trigger=trigger,
        args=[bot],
        id="channel_post_publisher",
        name="Auto-publish doTERRA post to channel",
        misfire_grace_time=300,   # 5 хвилин допуску при пропуску
        replace_existing=True,
    )

    if _CATALOG_SYNC_ENABLED:
        catalog_trigger = CronTrigger(
            day_of_week=_CATALOG_SYNC_DAY,
            hour=_CATALOG_SYNC_HOURS,
            minute=0,
            timezone=tz,
        )
        scheduler.add_job(
            func=_scheduled_catalog_sync,
            trigger=catalog_trigger,
            args=[bot],
            id="global_catalog_sync",
            name="Auto-sync doTERRA global markets catalog",
            misfire_grace_time=3600,
            replace_existing=True,
        )
        # Перший автозапуск через 90 секунд після старту, якщо ще не було жодного прогону в БД
        scheduler.add_job(
            func=_initial_catalog_sync_if_empty,
            trigger=DateTrigger(run_date=datetime.now(tz) + timedelta(seconds=90)),
            args=[bot],
            id="global_catalog_sync_bootstrap",
            name="Initial catalog sync bootstrap if never run",
            misfire_grace_time=300,
            replace_existing=True,
        )
        # Разовий автопереклад неперекладених позицій (JP/KR/MX/EN-only) через 25 секунд після старту
        scheduler.add_job(
            func=_startup_retranslate_overrides,
            trigger=DateTrigger(run_date=datetime.now(tz) + timedelta(seconds=25)),
            id="catalog_retranslate_startup",
            name="Auto-translate foreign/EN-only dynamic catalog items to UA+EN",
            misfire_grace_time=300,
            replace_existing=True,
        )
        print(
            f"[scheduler] 🌍 Global catalog auto-sync configured: "
            f"day={_CATALOG_SYNC_DAY!r}, hours={_CATALOG_SYNC_HOURS!r} {tz} (+ startup bootstrap if empty)"
        )

    print(
        f"[scheduler] ⏰ Scheduler configured: "
        f"days={_DAYS!r}, hour={_HOUR:02d}, minute={_MINUTE:02d} {tz}"
    )

    return scheduler
