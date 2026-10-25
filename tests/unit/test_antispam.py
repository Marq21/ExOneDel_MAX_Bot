"""Тесты антиспам-менеджера."""
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from src.utils.antispam import (
    ANTISPAM_BLOCKED_MESSAGE,
    ANTISPAM_BLOCKED_NOTIFICATION,
    AntiSpamManager,
)


def _answer_text(call) -> str:
    """Текст вызова answer — независимо от того, передан он позиционно или как text=."""
    return call.kwargs.get("text") or (call.args[0] if call.args else "")


class TestAntiSpamManager:
    
    def test_first_message_allowed(self):
        """Первое сообщение всегда разрешено."""
        manager = AntiSpamManager()
        assert manager.is_allowed(12345) is True
    
    def test_rapid_messages_blocked(self):
        """Быстрые повторные сообщения блокируются."""
        manager = AntiSpamManager()
        # Мокаем конфиг: минимальный интервал 10 секунд
        import src.utils.antispam as antispam_module
        original_get_config = antispam_module.ConfigLoader.get_config
        antispam_module.ConfigLoader.get_config = lambda: {
            "antispam": {
                "min_interval_seconds": 10,
                "max_messages_per_window": 100,
                "window_seconds": 60,
            }
        }
        try:
            assert manager.is_allowed(12345) is True
            # Сразу второе сообщение — должно быть заблокировано
            assert manager.is_allowed(12345) is False
        finally:
            antispam_module.ConfigLoader.get_config = original_get_config
    
    def test_window_limit_enforced(self):
        """Лимит сообщений в окне соблюдается."""
        manager = AntiSpamManager()
        import src.utils.antispam as antispam_module
        original_get_config = antispam_module.ConfigLoader.get_config
        antispam_module.ConfigLoader.get_config = lambda: {
            "antispam": {
                "min_interval_seconds": 0,
                "max_messages_per_window": 3,
                "window_seconds": 60,
            }
        }
        try:
            assert manager.is_allowed(12345) is True  # 1
            assert manager.is_allowed(12345) is True  # 2
            assert manager.is_allowed(12345) is True  # 3
            assert manager.is_allowed(12345) is False # 4 — перебор
        finally:
            antispam_module.ConfigLoader.get_config = original_get_config
    
    def test_reset_clears_state(self):
        """Сброс состояния позволяет отправлять снова."""
        manager = AntiSpamManager()
        import src.utils.antispam as antispam_module
        original_get_config = antispam_module.ConfigLoader.get_config
        antispam_module.ConfigLoader.get_config = lambda: {
            "antispam": {
                "min_interval_seconds": 100,
                "max_messages_per_window": 1,
                "window_seconds": 60,
            }
        }
        try:
            assert manager.is_allowed(12345) is True
            assert manager.is_allowed(12345) is False
            manager.reset(12345)
            assert manager.is_allowed(12345) is True
        finally:
            antispam_module.ConfigLoader.get_config = original_get_config
    
    def test_different_users_independent(self):
        """Разные пользователи не влияют друг на друга."""
        manager = AntiSpamManager()
        import src.utils.antispam as antispam_module
        original_get_config = antispam_module.ConfigLoader.get_config
        antispam_module.ConfigLoader.get_config = lambda: {
            "antispam": {
                "min_interval_seconds": 100,
                "max_messages_per_window": 1,
                "window_seconds": 60,
            }
        }
        try:
            assert manager.is_allowed(111) is True
            assert manager.is_allowed(111) is False
            # Другой пользователь не затронут
            assert manager.is_allowed(222) is True
        finally:
            antispam_module.ConfigLoader.get_config = original_get_config


    @pytest.mark.asyncio
    async def test_global_handler_respects_antispam(self, monkeypatch):
        """Глобальный хендлер блокирует флуд и уведомляет пользователя."""
        from src.handlers.global_handlers import handle_unknown_message
        from src.utils.antispam import AntiSpamManager
        import src.handlers.global_handlers as gh_module
        import src.utils.antispam as antispam_module

        # Создаём отдельный менеджер с жёсткими настройками
        test_manager = AntiSpamManager()
        
        # Подменяем менеджер в модуле, где он ИСПОЛЬЗУЕТСЯ (global_handlers)
        original_gh_manager = gh_module.antispam_manager
        gh_module.antispam_manager = test_manager

        # Sentinel вместо константы: ловит захардкоженный литерал в хендлере
        sentinel = "SENTINEL-BLOCKED-MESSAGE"
        monkeypatch.setattr(gh_module, "ANTISPAM_BLOCKED_MESSAGE", sentinel)

        original_get_config = antispam_module.ConfigLoader.get_config
        antispam_module.ConfigLoader.get_config = lambda: {
            "antispam": {
                "min_interval_seconds": 100,
                "max_messages_per_window": 1,
                "window_seconds": 60,
            }
        }

        try:
            event = MagicMock()
            event.message = MagicMock()
            event.message.sender = MagicMock()
            event.message.sender.user_id = 99999
            event.message.recipient = MagicMock()
            event.message.answer = AsyncMock()

            with patch("src.handlers.global_handlers.is_private_chat", return_value=True):
                # Первое сообщение проходит — отправляется "❓ Я вас не понимаю"
                await handle_unknown_message(event)
                assert event.message.answer.call_count == 1
                first_call_text = _answer_text(event.message.answer.call_args_list[0])
                assert "не понимаю" in first_call_text

                # Второе блокируется — отправляется текст блокировки из константы
                await handle_unknown_message(event)
                assert event.message.answer.call_count == 2  # УВЕЛИЧИЛОСЬ!
                second_call_text = _answer_text(event.message.answer.call_args_list[1])
                assert second_call_text == sentinel
        finally:
            gh_module.antispam_manager = original_gh_manager
            antispam_module.ConfigLoader.get_config = original_get_config

    @pytest.mark.asyncio
    async def test_callback_handlers_use_blocked_notification_constant(self, monkeypatch):
        """
        Колбэк-хендлеры берут уведомление из константы, а не из литерала.
        Подменяем константу в модуле-потребителе: если где-то остался
        захардкоженный текст, он не совпадёт с sentinel-значением.
        """
        import src.handlers.send_code as sc_module
        import src.utils.antispam as antispam_module

        sentinel = "SENTINEL-NOTIFICATION"
        monkeypatch.setattr(sc_module, "ANTISPAM_BLOCKED_NOTIFICATION", sentinel)

        blocking_manager = MagicMock()
        blocking_manager.is_allowed = MagicMock(return_value=False)
        monkeypatch.setattr(sc_module, "antispam_manager", blocking_manager)

        event = MagicMock()
        event.callback = MagicMock()
        event.callback.callback_id = "cb-1"
        event.callback.user = MagicMock()
        event.callback.user.user_id = 99999
        event.bot = MagicMock()
        event.bot.send_callback = AsyncMock()

        handlers = [
            sc_module.start_send_code,
            sc_module.process_office_choice,
            sc_module.back_to_store_choice,
            sc_module.back_to_menu,
        ]

        for handler in handlers:
            event.bot.send_callback.reset_mock()
            await handler(event, AsyncMock())

            event.bot.send_callback.assert_awaited_once()
            assert (
                event.bot.send_callback.call_args.kwargs["notification"] == sentinel
            ), f"{handler.__name__} использует литерал вместо ANTISPAM_BLOCKED_NOTIFICATION"




    def test_cleanup_removes_stale_entries(self):
        """Очистка удаляет устаревшие записи."""
        manager = AntiSpamManager()
        import src.utils.antispam as antispam_module
        original_get_config = antispam_module.ConfigLoader.get_config
        antispam_module.ConfigLoader.get_config = lambda: {
            "antispam": {
                "min_interval_seconds": 0,
                "max_messages_per_window": 100,
                "window_seconds": 60,
            }
        }
        try:
            # Создаём запись
            assert manager.is_allowed(111) is True
            assert 111 in manager.user_last_message_time

            # Имитируем, что запись устарела (сдвигаем время назад)
            manager.user_last_message_time[111] = time.time() - 700  # > 600 сек
            manager._last_cleanup = time.time() - 4000  # > 3600 сек назад

            # Следующий вызов должен триггернуть очистку
            assert manager.is_allowed(222) is True

            # Старая запись удалена
            assert 111 not in manager.user_last_message_time
            assert 111 not in manager.message_count_window
            assert 111 not in manager.last_reset_time
        finally:
            antispam_module.ConfigLoader.get_config = original_get_config