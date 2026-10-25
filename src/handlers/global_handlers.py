"""Глобальные обработчики для сообщений, не попавших в другие хендлеры."""
import logging

from maxapi import Dispatcher
from maxapi.types import MessageCreated
from maxapi.enums.parse_mode import ParseMode

from src.utils.keyboard_utils import get_main_menu
from src.utils.chat_utils import is_private_chat
from src.utils.antispam import antispam_manager  # <-- ДОБАВЛЕНО

logger = logging.getLogger(__name__)


async def handle_unknown_message(event: MessageCreated) -> None:
    """Обрабатывает все текстовые сообщения, не попавшие в другие хендлеры."""
    if not is_private_chat(event.message):
        return

    user_id = event.message.sender.user_id
    if not antispam_manager.is_allowed(user_id):
        return

    logger.debug("Unknown text message from user %s", user_id)
    await event.message.answer(
        text="❓ Я вас не понимаю.\n"
             "Пожалуйста, воспользуйтесь кнопками меню для навигации.",
        attachments=[get_main_menu()],
        parse_mode=ParseMode.HTML
    )


def register_global_handlers(dp: Dispatcher) -> None:
    """
    Регистрация глобальных хендлеров.
    ВАЖНО: вызывайте ПОСЛЕДНЕЙ среди всех регистраций.
    """
    dp.message_created(state="*")(handle_unknown_message)