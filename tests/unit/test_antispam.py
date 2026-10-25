"""Тесты антиспам-защиты.

Проверяется стратегия «только вход»:
- is_allowed() вызывается в start_send_code и handle_unknown_message;
- внутри визарда (send_code) проверок нет;
- /start и /restart снимают блокировку через reset().
"""
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

import src.handlers.global_handlers as gh_module
import src.handlers.send_code as sc_module
import src.handlers.start as start_module
import src.utils.antispam as antispam_module
from src.utils.antispam import (
    ANTISPAM_BLOCKED_MESSAGE,
    ANTISPAM_BLOCKED_NOTIFICATION,
    AntiSpamManager,
)
from src.utils.config_loader import ConfigLoader


CONFIG_STRICT = {
    "antispam": {
        "min_interval_seconds": 0,
        "max_messages_per_window": 3,
        "window_seconds": 60,
    }
}


@pytest.fixture(autouse=True)
def reset_config_cache(monkeypatch):
    """Сбрасываем кэш ConfigLoader перед каждым тестом."""
    monkeypatch.setenv("DEV", "true")
    monkeypatch.setattr(ConfigLoader, "_cache", {})
    monkeypatch.setattr(ConfigLoader, "_last_load", datetime.min)


@pytest.fixture
def manager(monkeypatch):
    """Свежий менеджер с предсказуемым конфигом."""
    monkeypatch.setattr(
        antispam_module.ConfigLoader, "get_config", lambda: CONFIG_STRICT
    )
    return AntiSpamManager()


def _answer_text(call) -> str:
    """Текст вызова answer — независимо от того, передан он позиционно или как text=."""
    return call.kwargs.get("text") or (call.args[0] if call.args else "")


def _make_callback_event(user_id: int = 99999):
    event = MagicMock()
    event.callback = MagicMock()
    event.callback.callback_id = "cb-1"
    event.callback.payload = "office_Ex.One"
    event.callback.user = MagicMock()
    event.callback.user.user_id = user_id
    event.bot = MagicMock()
    event.bot.send_callback = AsyncMock()
    event.message = MagicMock()
    event.message.answer = AsyncMock()
    return event


def _make_message_event(user_id: int = 99999):
    event = MagicMock()
    event.message = MagicMock()
    event.message.sender = MagicMock()
    event.message.sender.user_id = user_id
    event.message.answer = AsyncMock()
    return event


# ─────────────────────────────────────────────
# AntiSpamManager: окно и интервал
# ─────────────────────────────────────────────

class TestAntiSpamManager:
    """Поведение самого менеджера."""

    def test_first_message_allowed(self, manager):
        """Первое сообщение всегда разрешено."""
        assert manager.is_allowed(12345) is True

    def test_window_limit_enforced(self, manager):
        """Лимит сообщений в окне соблюдается."""
        assert manager.is_allowed(12345) is True   # 1
        assert manager.is_allowed(12345) is True   # 2
        assert manager.is_allowed(12345) is True   # 3
        assert manager.is_allowed(12345) is False  # 4 — перебор

    def test_min_interval_zero_does_not_block(self, manager):
        """При min_interval_seconds=0 быстрые повторы не блокируются."""
        for _ in range(3):
            assert manager.is_allowed(12345) is True

    def test_min_interval_blocks_when_configured(self, monkeypatch):
        """Если интервал задан явно, быстрый повтор блокируется."""
        monkeypatch.setattr(
            antispam_module.ConfigLoader,
            "get_config",
            lambda: {
                "antispam": {
                    "min_interval_seconds": 10,
                    "max_messages_per_window": 100,
                    "window_seconds": 60,
                }
            },
        )
        manager = AntiSpamManager()

        assert manager.is_allowed(12345) is True
        assert manager.is_allowed(12345) is False

    def test_window_resets_after_expiry(self, manager):
        """По истечении окна счётчик обнуляется."""
        for _ in range(3):
            manager.is_allowed(12345)
        assert manager.is_allowed(12345) is False

        # Сдвигаем начало окна в прошлое — окно истекло
        manager.last_reset_time[12345] = time.time() - 61

        assert manager.is_allowed(12345) is True

    def test_counter_is_capped(self, manager):
        """Счётчик не растёт неограниченно при спаме."""
        for _ in range(50):
            manager.is_allowed(12345)

        max_messages = CONFIG_STRICT["antispam"]["max_messages_per_window"]
        assert manager.message_count_window[12345] <= max_messages + 1

    def test_reset_clears_state(self, manager):
        """Сброс состояния позволяет отправлять снова."""
        assert manager.is_allowed(12345) is True
        assert manager.is_allowed(12345) is True
        assert manager.is_allowed(12345) is True
        assert manager.is_allowed(12345) is False

        manager.reset(12345)

        assert manager.is_allowed(12345) is True

    def test_different_users_independent(self, monkeypatch):
        """Разные пользователи не влияют друг на друга."""
        monkeypatch.setattr(
            antispam_module.ConfigLoader,
            "get_config",
            lambda: {
                "antispam": {
                    "min_interval_seconds": 0,
                    "max_messages_per_window": 1,
                    "window_seconds": 60,
                }
            },
        )
        manager = AntiSpamManager()

        assert manager.is_allowed(111) is True
        assert manager.is_allowed(111) is False
        # Другой пользователь не затронут
        assert manager.is_allowed(222) is True

    def test_cleanup_removes_stale_entries(self, manager):
        """Очистка удаляет устаревшие записи."""
        assert manager.is_allowed(111) is True
        assert 111 in manager.user_last_message_time

        # Имитируем устаревшую запись и просроченную очистку
        manager.user_last_message_time[111] = time.time() - 700   # > MAX_ENTRY_AGE
        manager._last_cleanup = time.time() - 4000               # > CLEANUP_INTERVAL

        assert manager.is_allowed(222) is True

        assert 111 not in manager.user_last_message_time
        assert 111 not in manager.message_count_window
        assert 111 not in manager.last_reset_time


# ─────────────────────────────────────────────
# Точки входа с проверкой
# ─────────────────────────────────────────────

class TestAntispamEntryPoints:
    """is_allowed вызывается только на входе в сценарий и в глобальном хендлере."""

    @pytest.mark.asyncio
    async def test_start_send_code_blocks_and_notifies(self, monkeypatch):
        """Кнопка «Отправить код» при блокировке отдаёт уведомление из константы."""
        sentinel = "SENTINEL-NOTIFICATION"
        monkeypatch.setattr(sc_module, "ANTISPAM_BLOCKED_NOTIFICATION", sentinel)

        blocking_manager = MagicMock()
        blocking_manager.is_allowed = MagicMock(return_value=False)
        monkeypatch.setattr(sc_module, "antispam_manager", blocking_manager)

        event = _make_callback_event()
        await sc_module.start_send_code(event, AsyncMock())

        blocking_manager.is_allowed.assert_called_once_with(99999)
        event.bot.send_callback.assert_awaited_once()
        assert event.bot.send_callback.call_args.kwargs["notification"] == sentinel
        # До показа выбора магазина дело не дошло
        event.message.answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_send_code_allows_and_continues(self, monkeypatch):
        """Разрешённый пользователь проходит к выбору маркетплейса."""
        allowing_manager = MagicMock()
        allowing_manager.is_allowed = MagicMock(return_value=True)
        monkeypatch.setattr(sc_module, "antispam_manager", allowing_manager)
        monkeypatch.setattr(
            sc_module, "is_session_allowed_to_proceed", lambda *a: True
        )

        event = _make_callback_event()
        context = AsyncMock()
        await sc_module.start_send_code(event, context)

        allowing_manager.is_allowed.assert_called_once_with(99999)
        event.message.answer.assert_awaited_once()
        context.set_state.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_global_handler_respects_antispam(self, monkeypatch):
        """Глобальный хендлер блокирует флуд и уведомляет пользователя."""
        sentinel = "SENTINEL-BLOCKED-MESSAGE"
        monkeypatch.setattr(gh_module, "ANTISPAM_BLOCKED_MESSAGE", sentinel)
        monkeypatch.setattr(gh_module, "is_private_chat", lambda message: True)
        monkeypatch.setattr(
            antispam_module.ConfigLoader, "get_config", lambda: CONFIG_STRICT
        )
        monkeypatch.setattr(gh_module, "antispam_manager", AntiSpamManager())

        event = _make_message_event()

        # Первые три сообщения укладываются в окно (лимит 3)
        for _ in range(3):
            await gh_module.handle_unknown_message(event)

        assert event.message.answer.await_count == 3
        assert "не понимаю" in _answer_text(event.message.answer.call_args_list[0])

        # Четвёртое — перебор окна, приходит текст блокировки из константы
        await gh_module.handle_unknown_message(event)

        assert event.message.answer.await_count == 4
        assert _answer_text(event.message.answer.call_args_list[3]) == sentinel

    @pytest.mark.asyncio
    async def test_wizard_handlers_do_not_call_antispam(self, monkeypatch):
        """Внутри визарда is_allowed не вызывается — проверка была на входе."""
        sentinel_manager = MagicMock()
        sentinel_manager.is_allowed = MagicMock(
            side_effect=AssertionError("is_allowed не должен вызываться в визарде")
        )
        monkeypatch.setattr(sc_module, "antispam_manager", sentinel_manager)

        monkeypatch.setattr(sc_module, "is_private_chat", lambda message: True)
        monkeypatch.setattr(sc_module, "get_example_image_path", lambda store: None)
        monkeypatch.setattr(sc_module, "get_store_description", lambda store: "описание")
        monkeypatch.setattr(sc_module, "is_session_allowed_to_proceed", lambda *a: True)
        monkeypatch.setattr(sc_module, "process_final_code_photo", AsyncMock())
        monkeypatch.setattr(sc_module, "process_final_order_data", AsyncMock())

        callback_event = _make_callback_event()
        callback_event.callback.payload = "store_wildberries"

        message_event = _make_message_event()
        message_event.message.body.text = "Иванов Иван Иванович"
        message_event.message.body.attachments = [MagicMock(payload=None)]

        context = AsyncMock()
        context.get_data = AsyncMock(return_value={"store": "store_ozon"})

        # Колбэки визарда
        await sc_module.process_store_choice(callback_event, context)
        await sc_module.process_office_choice(callback_event, context)
        await sc_module.back_to_store_choice(callback_event, context)
        await sc_module.back_to_menu(callback_event, context)

        # Сообщения визарда
        await sc_module.process_code_photo(message_event, context)
        await sc_module.process_name_input(message_event, context)
        await sc_module.process_phone_input(message_event, context)

        sentinel_manager.is_allowed.assert_not_called()


# ─────────────────────────────────────────────
# reset() на явном перезапуске
# ─────────────────────────────────────────────

class TestResetOnRestart:
    """/start и /restart снимают блокировку антиспама."""

    def _register(self, monkeypatch):
        """Регистрирует хендлеры start.py и возвращает их по имени."""
        captured = {}

        class FakeDispatcher:
            def message_created(self, *args, **kwargs):
                def decorator(func):
                    captured[func.__name__] = func
                    return func
                return decorator

            def message_callback(self, *args, **kwargs):
                def decorator(func):
                    captured[func.__name__] = func
                    return func
                return decorator

            def bot_started(self, *args, **kwargs):
                def decorator(func):
                    captured[func.__name__] = func
                    return func
                return decorator

        monkeypatch.setattr(start_module, "is_private_chat", lambda message: True)
        start_module.register_start_handlers(FakeDispatcher())
        return captured

    @pytest.mark.asyncio
    async def test_on_start_calls_reset(self, monkeypatch):
        """/start снимает блокировку."""
        fake_manager = MagicMock()
        monkeypatch.setattr(start_module, "antispam_manager", fake_manager)

        handlers = self._register(monkeypatch)
        event = _make_message_event()

        await handlers["on_start"](event)

        fake_manager.reset.assert_called_once_with(99999)
        event.message.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_on_restart_calls_reset(self, monkeypatch):
        """Кнопка «Перезапустить» снимает блокировку."""
        fake_manager = MagicMock()
        monkeypatch.setattr(start_module, "antispam_manager", fake_manager)

        handlers = self._register(monkeypatch)
        event = _make_callback_event()

        await handlers["on_restart"](event)

        fake_manager.reset.assert_called_once_with(99999)

    @pytest.mark.asyncio
    async def test_help_does_not_consult_antispam(self, monkeypatch):
        """/help больше не проверяет антиспам — осталось два входа."""
        fake_manager = MagicMock()
        fake_manager.is_allowed = MagicMock(
            side_effect=AssertionError("is_allowed не должен вызываться в /help")
        )
        monkeypatch.setattr(start_module, "antispam_manager", fake_manager)

        handlers = self._register(monkeypatch)
        event = _make_message_event()

        await handlers["on_help"](event)

        fake_manager.is_allowed.assert_not_called()
        event.message.answer.assert_awaited_once()


# ─────────────────────────────────────────────
# Конфигурация
# ─────────────────────────────────────────────

def test_min_interval_is_zero_in_config():
    """Интервальная защита отключена — основную работу делает окно."""
    assert ConfigLoader.get_config()["antispam"]["min_interval_seconds"] == 0
