"""Тесты антиспам-менеджера."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from src.utils.antispam import AntiSpamManager


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
    async def test_global_handler_respects_antispam(self):
        """Глобальный хендлер блокирует флуд."""
        from src.handlers.global_handlers import handle_unknown_message
        from src.utils.antispam import AntiSpamManager
        import src.handlers.global_handlers as gh_module
        import src.utils.antispam as antispam_module

        # Создаём отдельный менеджер с жёсткими настройками
        test_manager = AntiSpamManager()
        original_manager = antispam_module.antispam_manager
        antispam_module.antispam_manager = test_manager

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
                await handle_unknown_message(event)
                assert event.message.answer.call_count == 1

                # Второе блокируется
                await handle_unknown_message(event)
                assert event.message.answer.call_count == 1  # не увеличилось
        finally:
            antispam_module.antispam_manager = original_manager
            antispam_module.ConfigLoader.get_config = original_get_config