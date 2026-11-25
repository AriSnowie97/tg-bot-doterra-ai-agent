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
from datetime import timezone
from zoneinfo import ZoneInfo
# Special
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
# Local
from ..publisher import publish_channel_post
from ..catalog_sync import run_catalog_sync, format_sync_report_html
from ..safety import redact


# ---------------------------------------------------------------------------
# Зчитування конфігурації розкладу з env
# ---------------------------------------------------------------------------

_DAYS: str   = os.getenv("POST_SCHEDULE_DAYS", "tue,fri")
_HOUR: int   = int(os.getenv("POST_SCHEDULE_HOUR", "12"))
_MINUTE: int = int(os.getenv("POST_SCHEDULE_MINUTE", "0"))
_TZ_NAME: str = os.getenv("POST_SCHEDULE_TZ", "Europe/Kyiv")

# Автосинхронізація світових ринків doTERRA (дефолт: щонеділі о 04:00 за Києвом)
_CATALOG_SYNC_ENABLED: bool = os.getenv("ENABLE_CATALOG_SYNC", "1").strip().lower() not in ("0", "false", "no")
_CATALOG_SYNC_DAY: str = os.getenv("CATALOG_SYNC_DAY", "sun")
_CATALOG_SYNC_HOUR: int = int(os.getenv("CATALOG_SYNC_HOUR", "4"))


async def _scheduled_catalog_sync(bot: Bot) -> None:
    """Фонова автосинхронізація каталогу doTERRA по всіх ринках + звіт адмінам."""
    admin_ids = [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
    ]
    try:
        report = await run_catalog_sync(write_files=False, save_db=True)
        has_changes = bool(
            report.get("added")
            or report.get("restored")
            or report.get("archived")
            or report.get("archive_skipped_reason")
        )
        if has_changes and admin_ids:
            text = format_sync_report_html(report)
            for a_id in admin_ids:
                try:
                    await bot.send_message(chat_id=a_id, text=text, parse_mode="HTML")
                except Exception:
                    pass
    except Exception as e:
        print(f"[scheduler] ❌ Catalog auto-sync error: {redact(e)}")
        for a_id in admin_ids:
            try:
                await bot.send_message(
                    chat_id=a_id,
                    text=f"⚠️ <b>Помилка автосинхронізації каталогу doTERRA:</b>\n{redact(e)}",
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
            hour=_CATALOG_SYNC_HOUR,
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
        print(
            f"[scheduler] 🌍 Global catalog auto-sync configured: "
            f"day={_CATALOG_SYNC_DAY!r}, hour={_CATALOG_SYNC_HOUR:02d}:00 {tz}"
        )

    print(
        f"[scheduler] ⏰ Scheduler configured: "
        f"days={_DAYS!r}, hour={_HOUR:02d}, minute={_MINUTE:02d} {tz}"
    )

    return scheduler
