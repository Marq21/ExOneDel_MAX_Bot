"""Антиспам-защита: ограничение частоты сообщений от пользователей."""
import time
import logging
from typing import Dict

from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

ANTISPAM_BLOCKED_MESSAGE = (
    "⏳ Вы отправили слишком много сообщений за короткое время.\n"
    "Пожалуйста, подождите немного."
)

# Короткое уведомление для колбэков (всплывающая плашка в MAX ограничена по длине)
ANTISPAM_BLOCKED_NOTIFICATION = "⏳ Слишком часто, подождите..."


class AntiSpamManager:
    """
    Менеджер антиспам-защиты.
    Хранит состояние в памяти (сбрасывается при перезапуске контейнера).
    Периодически очищает устаревшие записи для экономии ОЗУ.
    """
    CLEANUP_INTERVAL = 3600   # Проверять очистку раз в 1 час
    MAX_ENTRY_AGE = 600       # Удалять записи старше 10 минут

    def __init__(self):
        self.user_last_message_time: Dict[int, float] = {}
        self.message_count_window: Dict[int, int] = {}
        self.last_reset_time: Dict[int, float] = {}
        self._last_cleanup: float = time.time()

    def _cleanup_stale_entries(self) -> None:
        """
        Удаляет устаревшие записи из словарей.
        Вызывается не чаще, чем раз в CLEANUP_INTERVAL.
        """
        now = time.time()
        if now - self._last_cleanup < self.CLEANUP_INTERVAL:
            return

        stale = [
            uid for uid, ts in self.user_last_message_time.items()
            if now - ts > self.MAX_ENTRY_AGE
        ]
        for uid in stale:
            self.user_last_message_time.pop(uid, None)
            self.message_count_window.pop(uid, None)
            self.last_reset_time.pop(uid, None)

        if stale:
            logger.debug("AntiSpam cleanup: removed %d stale entries", len(stale))

        self._last_cleanup = now

    def is_allowed(self, user_id: int) -> bool:
        """
        Проверяет, разрешено ли пользователю отправить сообщение.
        Возвращает True, если сообщение разрешено, False — если заблокировано.
        """
        self._cleanup_stale_entries()

        current_time = time.time()
        config = ConfigLoader.get_config()
        antispam_config = config.get("antispam", {})

        min_interval = antispam_config.get("min_interval_seconds", 1)
        max_messages = antispam_config.get("max_messages_per_window", 15)
        window_seconds = antispam_config.get("window_seconds", 60)

        # 1. Проверяем минимальный интервал между сообщениями
        if user_id in self.user_last_message_time:
            elapsed = current_time - self.user_last_message_time[user_id]
            if elapsed < min_interval:
                logger.debug(
                    "AntiSpam: user %s blocked (interval %.2fs < %.2fs)",
                    user_id, elapsed, min_interval
                )
                return False

        self.user_last_message_time[user_id] = current_time

        # 2. Проверяем лимит сообщений в скользящем окне
        if user_id not in self.last_reset_time:
            self.last_reset_time[user_id] = current_time
            self.message_count_window[user_id] = 0

        if current_time - self.last_reset_time[user_id] > window_seconds:
            self.last_reset_time[user_id] = current_time
            self.message_count_window[user_id] = 0

        self.message_count_window[user_id] += 1

        if self.message_count_window[user_id] > max_messages:
            logger.debug(
                "AntiSpam: user %s blocked (count %d > %d in window)",
                user_id, self.message_count_window[user_id], max_messages
            )
            return False

        return True

    def reset(self, user_id: int) -> None:
        """Сбрасывает состояние для пользователя (например, при /start)."""
        self.user_last_message_time.pop(user_id, None)
        self.message_count_window.pop(user_id, None)
        self.last_reset_time.pop(user_id, None)


# Глобальный экземпляр (один на всё приложение)
antispam_manager = AntiSpamManager()