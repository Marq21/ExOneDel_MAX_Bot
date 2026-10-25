import time
import logging
from typing import Dict

from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


class AntiSpamManager:
    """
    Менеджер антиспам-защиты.
    Хранит состояние в памяти (сбрасывается при перезапуске контейнера).
    """
    def __init__(self):
        self.user_last_message_time: Dict[int, float] = {}
        self.message_count_window: Dict[int, int] = {}
        self.last_reset_time: Dict[int, float] = {}

    def is_allowed(self, user_id: int) -> bool:
        """
        Проверяет, разрешено ли пользователю отправить сообщение.
        Возвращает True, если сообщение разрешено, False — если заблокировано.
        """
        current_time = time.time()
        config = ConfigLoader.get_config()
        antispam_config = config.get("antispam", {})

        min_interval = antispam_config.get("min_interval_seconds", 1)
        max_messages = antispam_config.get("max_messages_per_window", 5)
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

        # Сбрасываем окно, если оно истекло
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

antispam_manager = AntiSpamManager()