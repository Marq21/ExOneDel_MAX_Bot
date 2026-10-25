"""Тесты антиспам-защиты.

Проверяется стратегия «только вход»:
- is_allowed() вызывается в start_send_code, handle_unknown_message,
  on_help и on_restart;
- внутри визарда (send_code) проверок нет;
- /start — единственная точка reset() («аварийный выход»).
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
        "start_max_per_window": 2,
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
# /start, /help, /restart
# ─────────────────────────────────────────────

class TestStartHelpRestart:
    """/start — аварийный выход, /help и /restart защищены проверкой."""

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

    @pytest.fixture
    def strict_manager(self, monkeypatch):
        """Реальный менеджер с лимитом 3 сообщения за окно."""
        monkeypatch.setattr(
            antispam_module.ConfigLoader, "get_config", lambda: CONFIG_STRICT
        )
        manager = AntiSpamManager()
        monkeypatch.setattr(start_module, "antispam_manager", manager)
        return manager

    @pytest.mark.asyncio
    async def test_on_start_calls_reset(self, monkeypatch):
        """/start снимает блокировку — это единственная точка сброса."""
        fake_manager = MagicMock()
        monkeypatch.setattr(start_module, "antispam_manager", fake_manager)

        handlers = self._register(monkeypatch)
        event = _make_message_event()

        await handlers["on_start"](event)

        fake_manager.reset.assert_called_once_with(99999)
        # Жёсткой проверки is_allowed в /start нет намеренно
        fake_manager.is_allowed.assert_not_called()
        event.message.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_on_start_uses_soft_limit(self, monkeypatch):
        """/start проверяется мягким лимитом, а не жёстким is_allowed."""
        fake_manager = MagicMock()
        fake_manager.is_start_allowed = MagicMock(return_value=True)
        monkeypatch.setattr(start_module, "antispam_manager", fake_manager)

        handlers = self._register(monkeypatch)
        event = _make_message_event()

        await handlers["on_start"](event)

        fake_manager.is_start_allowed.assert_called_once_with(99999)

    @pytest.mark.asyncio
    async def test_start_spam_is_suppressed_but_reset_still_runs(
        self, monkeypatch, strict_manager
    ):
        """
        Спам /start: приветствие перестаёт отправляться,
        но блокировка всё равно снимается (reset вызывается всегда).
        """
        handlers = self._register(monkeypatch)
        event = _make_message_event()

        limit = CONFIG_STRICT["antispam"]["start_max_per_window"]

        # В пределах лимита — отвечаем
        for _ in range(limit):
            await handlers["on_start"](event)
        assert event.message.answer.await_count == limit

        # Сверх лимита — молчим
        await handlers["on_start"](event)
        assert event.message.answer.await_count == limit

        # При этом пользователь не заблокирован: основное окно пустое
        assert 99999 not in strict_manager.message_count_window

    @pytest.mark.asyncio
    async def test_start_soft_limit_survives_reset(self, strict_manager):
        """reset() не обнуляет окно /start — иначе мягкий лимит был бы фикцией."""
        limit = CONFIG_STRICT["antispam"]["start_max_per_window"]

        for _ in range(limit):
            assert strict_manager.is_start_allowed(99999) is True

        strict_manager.reset(99999)

        assert strict_manager.is_start_allowed(99999) is False

    @pytest.mark.asyncio
    async def test_start_limit_resets_after_window(self, strict_manager):
        """По истечении окна /start снова разрешён."""
        limit = CONFIG_STRICT["antispam"]["start_max_per_window"]

        for _ in range(limit):
            strict_manager.is_start_allowed(99999)
        assert strict_manager.is_start_allowed(99999) is False

        # Сдвигаем начало окна /start в прошлое
        strict_manager.start_window_reset_time[99999] = time.time() - 61

        assert strict_manager.is_start_allowed(99999) is True

    @pytest.mark.asyncio
    async def test_start_soft_limit_is_separate_from_main_window(self, monkeypatch):
        """Лимиты /start и остальных действий считаются независимо."""
        monkeypatch.setattr(
            antispam_module.ConfigLoader,
            "get_config",
            lambda: {
                "antispam": {
                    "min_interval_seconds": 0,
                    "max_messages_per_window": 2,
                    "start_max_per_window": 5,
                    "window_seconds": 60,
                }
            },
        )
        manager = AntiSpamManager()

        # Исчерпали основной лимит
        assert manager.is_allowed(99999) is True
        assert manager.is_allowed(99999) is True
        assert manager.is_allowed(99999) is False

        # /start при этом ещё доступен
        assert manager.is_start_allowed(99999) is True

    @pytest.mark.asyncio
    async def test_on_restart_does_not_reset(self, monkeypatch):
        """restart не должен обнулять счётчик — иначе защита бессмысленна."""
        fake_manager = MagicMock()
        monkeypatch.setattr(start_module, "antispam_manager", fake_manager)

        handlers = self._register(monkeypatch)
        event = _make_callback_event()

        await handlers["on_restart"](event)

        fake_manager.is_allowed.assert_called_once_with(99999)
        fake_manager.reset.assert_not_called()

    @pytest.mark.asyncio
    async def test_restart_spam_is_blocked(self, monkeypatch, strict_manager):
        """Спам перезапусками упирается в окно и получает уведомление."""
        sentinel = "SENTINEL-NOTIFICATION"
        monkeypatch.setattr(
            start_module, "ANTISPAM_BLOCKED_NOTIFICATION", sentinel
        )

        handlers = self._register(monkeypatch)
        event = _make_callback_event()

        # Лимит окна — 3, поэтому первые три перезапуска проходят
        for _ in range(3):
            await handlers["on_restart"](event)
        assert event.bot.send_callback.await_count == 3

        # Четвёртый — блокировка с уведомлением, сообщение не отправляется
        answers_before = event.message.answer.await_count
        await handlers["on_restart"](event)

        assert event.bot.send_callback.call_args.kwargs["notification"] == sentinel
        assert event.message.answer.await_count == answers_before

    @pytest.mark.asyncio
    async def test_help_spam_is_blocked(self, monkeypatch, strict_manager):
        """Спам /help упирается в окно и получает текст блокировки."""
        sentinel = "SENTINEL-BLOCKED-MESSAGE"
        monkeypatch.setattr(start_module, "ANTISPAM_BLOCKED_MESSAGE", sentinel)

        handlers = self._register(monkeypatch)
        event = _make_message_event()

        for _ in range(3):
            await handlers["on_help"](event)
        assert event.message.answer.await_count == 3

        await handlers["on_help"](event)

        assert event.message.answer.await_count == 4
        assert _answer_text(event.message.answer.call_args_list[3]) == sentinel

    @pytest.mark.asyncio
    async def test_help_uses_blocked_message_constant(self, monkeypatch):
        """/help берёт текст блокировки из константы, а не из литерала."""
        fake_manager = MagicMock()
        fake_manager.is_allowed = MagicMock(return_value=False)
        monkeypatch.setattr(start_module, "antispam_manager", fake_manager)

        handlers = self._register(monkeypatch)
        event = _make_message_event()

        await handlers["on_help"](event)

        fake_manager.is_allowed.assert_called_once_with(99999)
        event.message.answer.assert_awaited_once()
        assert (
            _answer_text(event.message.answer.call_args_list[0])
            == ANTISPAM_BLOCKED_MESSAGE
        )

    @pytest.mark.asyncio
    async def test_restart_uses_blocked_notification_constant(self, monkeypatch):
        """restart берёт уведомление из константы, а не из литерала."""
        fake_manager = MagicMock()
        fake_manager.is_allowed = MagicMock(return_value=False)
        monkeypatch.setattr(start_module, "antispam_manager", fake_manager)

        handlers = self._register(monkeypatch)
        event = _make_callback_event()

        await handlers["on_restart"](event)

        assert (
            event.bot.send_callback.call_args.kwargs["notification"]
            == ANTISPAM_BLOCKED_NOTIFICATION
        )


# ─────────────────────────────────────────────
# Конфигурация
# ─────────────────────────────────────────────

def test_min_interval_is_zero_in_config():
    """Интервальная защита отключена — основную работу делает окно."""
    assert ConfigLoader.get_config()["antispam"]["min_interval_seconds"] == 0
