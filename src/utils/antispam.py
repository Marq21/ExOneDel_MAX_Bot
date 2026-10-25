"""Антиспам-защита: ограничение частоты сообщений от пользователей.

Стратегия «только вход»:
- Проверка is_allowed() применяется к:
  • /help;
  • кнопке «Перезапустить»;
  • кнопке «Отправить код» (вход в сценарий);
  • свободным сообщениям (глобальный обработчик).
- Внутри визарда (магазин → фото → офис → ФИО → телефон) антиспам НЕ применяется.
  Пользователь уже прошёл проверку на входе; дальнейшие шаги — осознанные действия.
- /start — «аварийный выход»: единственное место, где вызывается reset().
  Проверки is_allowed там нет намеренно, иначе пользователь, заблокированный
  на время окна, не смог бы выйти из блокировки вообще.
  Вместо неё — мягкий лимит is_start_allowed(): при спаме /start приветствие
  не отправляется, но блокировка всё равно снимается.
  Важно: в проверяемых хендлерах reset() вызывать нельзя — он обнуляет счётчик
  окна, и защита превращается в фикцию.

Свойства:
- in-memory (сбрасывается при рестарте контейнера);
- periodic cleanup устаревших записей;
- min_interval_seconds по умолчанию 0 (интервальная защита отключена),
  основную защиту даёт окно max_messages_per_window / window_seconds.
"""
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
    """Менеджер антиспам-защиты (стратегия «только вход в сценарий»)."""

    CLEANUP_INTERVAL = 3600   # Проверять очистку раз в 1 час
    MAX_ENTRY_AGE = 600       # Удалять записи старше 10 минут

    def __init__(self):
        self.user_last_message_time: Dict[int, float] = {}
        self.message_count_window: Dict[int, int] = {}
        self.last_reset_time: Dict[int, float] = {}
        # Отдельное окно для /start: reset() его НЕ трогает,
        # иначе спам командой /start был бы бесконечным.
        self.start_count_window: Dict[int, int] = {}
        self.start_window_reset_time: Dict[int, float] = {}
        self._last_cleanup: float = time.time()

    def _cleanup_stale_entries(self) -> None:
        """Удаляет устаревшие записи. Не чаще раза в CLEANUP_INTERVAL."""
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
            self.start_count_window.pop(uid, None)
            self.start_window_reset_time.pop(uid, None)

        if stale:
            logger.debug("AntiSpam cleanup: removed %d stale entries", len(stale))
        self._last_cleanup = now

    def is_allowed(self, user_id: int) -> bool:
        """
        Проверка для ВХОДА в сценарий или СВОБОДНОГО сообщения.

        Возвращает True, если действие разрешено.

        Внутри визарда этот метод НЕ должен вызываться.
        """
        self._cleanup_stale_entries()

        current_time = time.time()
        config = ConfigLoader.get_config()
        antispam_config = config.get("antispam", {})

        min_interval = antispam_config.get("min_interval_seconds", 0)
        max_messages = antispam_config.get("max_messages_per_window", 15)
        window_seconds = antispam_config.get("window_seconds", 60)

        # 1. Минимальный интервал (только если > 0)
        if min_interval > 0 and user_id in self.user_last_message_time:
            elapsed = current_time - self.user_last_message_time[user_id]
            if elapsed < min_interval:
                logger.info(
                    "AntiSpam: user %s blocked (interval %.2fs < %.2fs)",
                    user_id, elapsed, min_interval,
                )
                return False

        self.user_last_message_time[user_id] = current_time

        # 2. Fixed window (30 сообщений / 60 секунд по умолчанию)
        if user_id not in self.last_reset_time:
            self.last_reset_time[user_id] = current_time
            self.message_count_window[user_id] = 0

        if current_time - self.last_reset_time[user_id] > window_seconds:
            self.last_reset_time[user_id] = current_time
            self.message_count_window[user_id] = 0

        # Не даём счётчику расти неограниченно при спаме
        self.message_count_window[user_id] = min(
            self.message_count_window[user_id] + 1,
            max_messages + 1,
        )

        if self.message_count_window[user_id] > max_messages:
            logger.info(
                "AntiSpam: user %s blocked (count %d > %d in window)",
                user_id, self.message_count_window[user_id], max_messages,
            )
            return False

        return True

    def is_start_allowed(self, user_id: int) -> bool:
        """
        Мягкий лимит для /start.

        /start — «аварийный выход» из блокировки, поэтому жёстко блокировать его
        нельзя. Вместо этого ограничиваем частоту ответов на команду: при
        превышении лимита приветствие просто не отправляется (молчаливый выход),
        но блокировка при этом всё равно снимается вызывающим кодом.

        Учёт ведётся в отдельном окне, которое reset() не очищает.
        """
        self._cleanup_stale_entries()

        current_time = time.time()
        config = ConfigLoader.get_config()
        antispam_config = config.get("antispam", {})

        max_starts = antispam_config.get("start_max_per_window", 5)
        window_seconds = antispam_config.get("window_seconds", 60)

        if user_id not in self.start_window_reset_time:
            self.start_window_reset_time[user_id] = current_time
            self.start_count_window[user_id] = 0

        if current_time - self.start_window_reset_time[user_id] > window_seconds:
            self.start_window_reset_time[user_id] = current_time
            self.start_count_window[user_id] = 0

        # Не даём счётчику расти неограниченно
        self.start_count_window[user_id] = min(
            self.start_count_window[user_id] + 1,
            max_starts + 1,
        )

        if self.start_count_window[user_id] > max_starts:
            logger.info(
                "AntiSpam: /start from user %s suppressed (count %d > %d in window)",
                user_id, self.start_count_window[user_id], max_starts,
            )
            return False

        return True

    def reset(self, user_id: int) -> None:
        """
        Сброс состояния для пользователя.

        Семантика: пользователь явно начал заново (/start) —
        снимаем блокировки. Иначе спамер мог бы «залипнуть» на 60 секунд
        без возможности выйти через перезапуск.

        ВАЖНО: окно /start здесь не очищается — иначе повторные /start
        сбрасывали бы собственный счётчик и мягкий лимит не работал бы.
        """
        self.user_last_message_time.pop(user_id, None)
        self.message_count_window.pop(user_id, None)
        self.last_reset_time.pop(user_id, None)


# Глобальный экземпляр (один на всё приложение)
antispam_manager = AntiSpamManager()