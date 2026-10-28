"""Проверка расписания приёма кодов."""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

GRACE_PERIOD_MINUTES = 15
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

WEEKDAY_MAP = {
    0: "monday",
    1: "tuesday",
    2: "wednesday",
    3: "thursday",
    4: "friday",
    5: "saturday",
    6: "sunday",
}

DAY_NAMES = {
    "monday": "Понедельник",
    "tuesday": "Вторник",
    "wednesday": "Среда",
    "thursday": "Четверг",
    "friday": "Пятница",
    "saturday": "Суббота",
    "sunday": "Воскресенье",
}


def is_session_allowed_to_proceed(
    session_start_timestamp: int | None = None,
    user_id: int | None = None,
) -> bool:
    """
    Проверяет, может ли пользователь начать или завершить отправку кода.

    Args:
        session_start_timestamp:
            - None → проверка для СТАРТА (обычное рабочее время).
            - int  → проверка для ЗАВЕРШЕНИЯ (рабочее время + grace period).
        user_id:
            ID пользователя. Если он админ — проверка расписания пропускается.

    Returns:
        True, если действие разрешено.
    """
    config = ConfigLoader.get_config()

    # === Админы обходят расписание ===
    if user_id is not None:
        admin_ids = config.get("admin_ids", [])
        if user_id in admin_ids:
            logger.debug(
                "Admin %s bypassed schedule check (timestamp=%s)",
                user_id, session_start_timestamp,
            )
            return True

    now = datetime.now(MOSCOW_TZ)
    current_weekday = now.weekday()
    now_minutes = now.hour * 60 + now.minute

    working_hours = config.get("working_hours", {})
    day_key = WEEKDAY_MAP.get(current_weekday)
    if not day_key:
        logger.warning("Unknown weekday: %s", current_weekday)
        return False

    hour_limit = working_hours.get(day_key)
    if hour_limit is None:
        logger.warning("No working hours defined for %s", day_key)
        return False

    limit_minutes = hour_limit * 60

    # === Случай 1: Проверка для СТАРТА сценария ===
    if session_start_timestamp is None:
        allowed = now_minutes < limit_minutes
        logger.debug(
            "[START] Now: %d min, limit: %d min → allowed: %s",
            now_minutes, limit_minutes, allowed,
        )
        return allowed

    # === Случай 2: Проверка для ЗАВЕРШЕНИЯ сценария ===
    try:
        session_start_dt = datetime.fromtimestamp(
            session_start_timestamp, tz=MOSCOW_TZ
        )
        session_start_minutes = session_start_dt.hour * 60 + session_start_dt.minute
        started_in_time = session_start_minutes < limit_minutes
    except (OSError, ValueError, OverflowError):
        logger.warning("Invalid session_start_timestamp: %s", session_start_timestamp)
        return False

    if not started_in_time:
        logger.info("Session started after working hours — denied.")
        return False

    # Grace period: +15 минут после окончания приёма
    grace_end_minutes = limit_minutes + GRACE_PERIOD_MINUTES
    allowed = now_minutes <= grace_end_minutes
    logger.debug(
        "[FINISH] Started at %d min (in time: %s), now: %d min, "
        "grace end: %d min → allowed: %s",
        session_start_minutes, started_in_time,
        now_minutes, grace_end_minutes, allowed,
    )
    return allowed


def format_working_hours_message() -> str:
    """Форматирует сообщение с расписанием приёма кодов."""
    config = ConfigLoader.get_config()
    working_hours = config.get("working_hours", {})

    today = WEEKDAY_MAP.get(datetime.now(MOSCOW_TZ).weekday())

    lines = ["<b>🕗Расписание приёма кодов:</b>"]
    for config_key, readable_name in DAY_NAMES.items():
        hour_limit = working_hours.get(config_key, "—")
        if hour_limit != "—":
            status = " (сейчас)" if config_key == today else ""
            lines.append(f"• <b>{readable_name}</b>: до {hour_limit}:00{status}")
        else:
            lines.append(f"• <b>{readable_name}</b>: не работает")
    return "\n".join(lines)