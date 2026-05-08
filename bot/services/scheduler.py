import logging
from datetime import date, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import SUMMARY_TIME, TIMEZONE, MESSAGE_RETENTION_DAYS
from bot.services.summarizer import deliver_summaries
from bot.services.database import purge_old_messages
from bot.services.yandex_disk import process_upload_queue

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _parse_time(time_str: str) -> tuple[int, int]:
    h, m = time_str.split(":")
    return int(h), int(m)


async def _daily_job(app) -> None:
    today = date.today()
    logger.info("Running daily summary job for %s", today)
    await deliver_summaries(app, today)
    await process_upload_queue()
    if MESSAGE_RETENTION_DAYS > 0:
        await purge_old_messages(MESSAGE_RETENTION_DAYS)
    logger.info("Daily job finished")


def start_scheduler(app) -> AsyncIOScheduler:
    global _scheduler
    hour, minute = _parse_time(SUMMARY_TIME)
    _scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    _scheduler.add_job(
        _daily_job,
        CronTrigger(hour=hour, minute=minute, timezone=TIMEZONE),
        args=[app],
        id="daily_summary",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started; daily job at %02d:%02d %s", hour, minute, TIMEZONE)
    return _scheduler


def stop_scheduler() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
