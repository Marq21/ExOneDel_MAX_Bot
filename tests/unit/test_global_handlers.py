"""Тесты глобального обработчика неизвестных сообщений."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.handlers.global_handlers import handle_unknown_message


@pytest.mark.asyncio
async def test_unknown_message_sends_reply():
    """Неизвестное сообщение получает ответ с меню."""
    event = MagicMock()
    event.message = MagicMock()
    event.message.sender = MagicMock()
    event.message.sender.user_id = 12345
    event.message.recipient = MagicMock()
    event.message.recipient.chat_type = MagicMock()
    event.message.answer = AsyncMock()

    with patch(
        "src.handlers.global_handlers.is_private_chat",
        return_value=True,
    ):
        await handle_unknown_message(event)

    event.message.answer.assert_called_once()
    call_kwargs = event.message.answer.call_args[1]
    assert "не понимаю" in call_kwargs["text"]
    assert call_kwargs.get("attachments") is not None


@pytest.mark.asyncio
async def test_unknown_message_ignored_in_group():
    """В групповом чате неизвестное сообщение игнорируется."""
    event = MagicMock()
    event.message = MagicMock()
    event.message.sender = MagicMock()
    event.message.sender.user_id = 12345
    event.message.recipient = MagicMock()
    event.message.recipient.chat_type = MagicMock()
    event.message.answer = AsyncMock()

    with patch(
        "src.handlers.global_handlers.is_private_chat",
        return_value=False,
    ):
        await handle_unknown_message(event)

    event.message.answer.assert_not_called()