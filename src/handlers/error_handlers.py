"""Глобальный обработчик ошибок для MAX-бота."""
import asyncio
import logging

import aiohttp
from maxapi import Dispatcher
from maxapi.dispatcher import ClientConnectorError, AsyncioTimeoutError
from maxapi.types.error_event import ErrorEvent

from src.exceptions import SpamDetectedException
from src.utils.admin_notifier import notify_admin_error

logger = logging.getLogger(__name__)

# Временные сетевые ошибки — не требуют уведомления админа
TRANSIENT_NETWORK_EXCEPTIONS = (
    ClientConnectorError,
    AsyncioTimeoutError,
    asyncio.TimeoutError,
    ConnectionError,
)

TRANSIENT_MESSAGE_MARKERS = (
    "clientconnectorerror",
    "cannot connect to host",
    "connection reset by peer",
    "server disconnected",
    "connection aborted",
    "timeout",
    "network is unreachable",
    "temporary failure in name resolution",
)


def _is_transient_network_error(exception: Exception) -> bool:
    """
    Проверяет, является ли ошибка временной сетевой ошибкой.
    Такие ошибки обычно не требуют уведомления администратора.
    """
    if isinstance(exception, TRANSIENT_NETWORK_EXCEPTIONS):
        return True
    
    exception_text = f"{type(exception).__name__}: {exception}".lower()
    return any(marker in exception_text for marker in TRANSIENT_MESSAGE_MARKERS)


def _extract_user_id(event: ErrorEvent) -> str:
    """Извлекает ID пользователя из события ошибки."""
    try:
        update = event.update
        
        # MessageCreated
        if hasattr(update, "message") and hasattr(update.message, "sender"):
            return str(update.message.sender.user_id)
        
        # MessageCallback
        if hasattr(update, "callback") and hasattr(update.callback, "user"):
            return str(update.callback.user.user_id)
        
        # BotStarted
        if hasattr(update, "chat_id"):
            return f"chat:{update.chat_id}"
        
        return "unknown"
    
    except Exception:
        return "unknown"


def _extract_update_type(event: ErrorEvent) -> str:
    """Извлекает тип события из ErrorEvent."""
    try:
        update = event.update
        return type(update).__name__
    except Exception:
        return "unknown"


def _extract_bot(update):
    """Достаёт Bot из update (message или callback), если он там есть."""
    bot = getattr(getattr(update, "message", None), "bot", None)
    if bot is None:
        bot = getattr(getattr(update, "callback", None), "bot", None)
    return bot


async def _notify_admin(event: ErrorEvent, exception: Exception,
                        user_id: str, update_type: str) -> None:
    """Отправляет администратору карточку ошибки. Сбои уведомления не пробрасывает."""
    error_msg = (
        f"<b>Тип:</b> {type(exception).__name__}\n"
        f"<b>Сообщение:</b> {str(exception)}\n"
        f"<b>User ID:</b> {user_id}\n"
        f"<b>Update type:</b> {update_type}"
    )

    try:
        bot = _extract_bot(event.update)
        if bot:
            await notify_admin_error(bot, error_msg)
        else:
            logger.warning("Cannot extract bot from event, skipping admin notification")

    except Exception as notify_error:
        logger.exception(
            "Failed to notify admin: %s",
            notify_error,
            exc_info=True,
        )


def register_error_handlers(dp: Dispatcher) -> None:
    """Регистрация глобального обработчика ошибок."""
    
    @dp.errors()
    async def global_error_handler(event: ErrorEvent) -> None:
        """
        Глобальный обработчик всех необработанных исключений.

        Ничего не возвращает: maxapi вызывает обработчик и отбрасывает
        результат (Dispatcher.call_error_handler -> None). Факт вызова
        уже означает, что ошибка обработана.
        """
        exception = event.exception
        user_id = _extract_user_id(event)
        update_type = _extract_update_type(event)

        if isinstance(exception, SpamDetectedException):
            # 1. Спам/флуд уже обработан антиспамом — админу не отправляем
            logger.info("Spam attempt was successfully blocked for user %s", user_id)

        elif _is_transient_network_error(exception):
            # 2. Временные сетевые ошибки только логируем
            logger.warning(
                "Transient network error (admin notification skipped): "
                "%s: %s | user=%s",
                type(exception).__name__,
                exception,
                user_id,
            )

        else:
            # 3. Реальные ошибки логируем и отправляем администратору
            logger.error(
                "Unhandled error: %s: %s | user=%s | update_type=%s",
                type(exception).__name__,
                exception,
                user_id,
                update_type,
                exc_info=True,
            )
            await _notify_admin(event, exception, user_id, update_type)