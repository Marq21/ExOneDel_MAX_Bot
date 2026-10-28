"""Уведомления администратору о критических ошибках."""
import logging

from maxapi import Bot
from maxapi.enums.parse_mode import ParseMode

from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


async def notify_admin_error(bot: Bot, message: str) -> None:
    """
    Отправляет сообщение об ошибке администратору.

    Args:
        bot: Экземпляр бота для отправки сообщения.
        message: Текст уведомления (поддерживает HTML-разметку).
    """
    try:
        config = ConfigLoader.get_config()
        admin_user_id = config.get("admin_error_chat_id")

        if not admin_user_id:
            logger.warning("Admin error chat ID not configured. Skipping notification.")
            return

        # Ограничиваем длину сообщения (MAX API лимит ~4096 символов)
        if len(message) > 4000:
            message = message[:3997] + "..."

        # admin_error_chat_id содержит user_id админа (не групповой чат),
        # поэтому используем user_id= для отправки личного сообщения
        await bot.send_message(
            user_id=int(admin_user_id),
            text=f"🚨 <b>CRITICAL ERROR</b>\n{message}",
            parse_mode=ParseMode.HTML
        )

        logger.info("Admin error notification sent successfully to user %s", admin_user_id)

    except Exception as e:
        # Не роняем бота из-за ошибки уведомления
        logger.exception("Failed to send admin error notification: %s", e)