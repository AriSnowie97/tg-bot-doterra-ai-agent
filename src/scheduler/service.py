"""
Планувальник автопублікацій у Telegram-канал.

Використовує APScheduler (AsyncIOScheduler) із cron-тригером.
Параметри розкладу читаються з .env:

    POST_SCHEDULE_DAYS=tue,fri   # дні тижня (дефолт: вт + пт)
    POST_SCHEDULE_HOUR=9         # година UTC (дефолт: 9 = 12:00 Київ зима)
    POST_SCHEDULE_MINUTE=0       # хвилина (дефолт: 0)

Використання:
    from src.scheduler import setup_scheduler

    scheduler = setup_scheduler(bot)
    scheduler.start()
    ...
    scheduler.shutdown()
"""

# Standard
import os
# Special
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
# Local
from ..publisher import publish_channel_post


# ---------------------------------------------------------------------------
# Зчитування конфігурації розкладу з env
# ---------------------------------------------------------------------------

_DAYS: str   = os.getenv("POST_SCHEDULE_DAYS", "tue,fri")
_HOUR: int   = int(os.getenv("POST_SCHEDULE_HOUR", "9"))
_MINUTE: int = int(os.getenv("POST_SCHEDULE_MINUTE", "0"))


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
        Cron-тригер: POST_SCHEDULE_DAYS о POST_SCHEDULE_HOUR:POST_SCHEDULE_MINUTE UTC.
        Дефолт: вівторок + п'ятниця о 09:00 UTC (12:00 Київ, зима).
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    trigger = CronTrigger(
        day_of_week=_DAYS,
        hour=_HOUR,
        minute=_MINUTE,
        timezone="UTC",
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

    print(
        f"[scheduler] ⏰ Scheduler configured: "
        f"days={_DAYS!r}, hour={_HOUR:02d}, minute={_MINUTE:02d} UTC"
    )

    return scheduler
