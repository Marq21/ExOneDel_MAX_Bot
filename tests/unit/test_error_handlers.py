"""Тесты глобального обработчика ошибок."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import src.handlers.error_handlers as eh
from src.exceptions import SpamDetectedException


def _register() -> object:
    """Регистрирует обработчики и возвращает сам error-handler."""
    captured = {}

    class FakeDispatcher:
        def errors(self, *args, **kwargs):
            def decorator(func):
                captured["handler"] = func
                return func
            return decorator

    eh.register_error_handlers(FakeDispatcher())
    return captured["handler"]


def _make_event(exception: Exception, bot=None, user_id: int = 12345):
    """Собирает минимальный ErrorEvent: update.message.sender + bot."""
    message = SimpleNamespace(
        bot=bot,
        sender=SimpleNamespace(user_id=user_id),
    )
    return SimpleNamespace(
        exception=exception,
        update=SimpleNamespace(message=message),
    )


@pytest.mark.asyncio
async def test_spam_exception_not_reported_to_admin(monkeypatch):
    """Спам уже обработан антиспамом — админа не тревожим."""
    notify = AsyncMock()
    monkeypatch.setattr(eh, "notify_admin_error", notify)

    handler = _register()
    await handler(_make_event(SpamDetectedException("flood"), bot=AsyncMock()))

    notify.assert_not_called()


@pytest.mark.asyncio
async def test_transient_network_error_not_reported_to_admin(monkeypatch):
    """Временная сетевая ошибка только логируется."""
    notify = AsyncMock()
    monkeypatch.setattr(eh, "notify_admin_error", notify)

    handler = _register()
    await handler(_make_event(asyncio.TimeoutError(), bot=AsyncMock()))

    notify.assert_not_called()


@pytest.mark.asyncio
async def test_real_error_reported_to_admin(monkeypatch):
    """Реальная ошибка уходит администратору с типом и user_id."""
    notify = AsyncMock()
    monkeypatch.setattr(eh, "notify_admin_error", notify)

    bot = AsyncMock()
    handler = _register()
    await handler(_make_event(ValueError("boom"), bot=bot))

    notify.assert_awaited_once()
    called_bot, called_text = notify.await_args.args
    assert called_bot is bot
    assert "ValueError" in called_text
    assert "boom" in called_text
    assert "12345" in called_text


@pytest.mark.asyncio
async def test_missing_bot_skips_notification(monkeypatch):
    """Если bot не извлекается, обработчик не падает и не шлёт уведомление."""
    notify = AsyncMock()
    monkeypatch.setattr(eh, "notify_admin_error", notify)

    handler = _register()
    await handler(_make_event(ValueError("boom"), bot=None))

    notify.assert_not_called()


@pytest.mark.asyncio
async def test_notification_failure_is_swallowed(monkeypatch):
    """Падение уведомления не должно ронять обработчик ошибок."""
    notify = AsyncMock(side_effect=RuntimeError("network down"))
    monkeypatch.setattr(eh, "notify_admin_error", notify)

    handler = _register()
    # Не должно выбросить исключение
    await handler(_make_event(ValueError("boom"), bot=AsyncMock()))

    notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_handler_returns_none(monkeypatch):
    """
    Обработчик ничего не возвращает: maxapi игнорирует результат
    (Dispatcher.call_error_handler -> None), поэтому возвращать True незачем.
    """
    monkeypatch.setattr(eh, "notify_admin_error", AsyncMock())

    handler = _register()
    result = await handler(_make_event(ValueError("boom"), bot=AsyncMock()))

    assert result is None
