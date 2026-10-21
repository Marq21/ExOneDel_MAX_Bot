"""Обработчики команды /start и главного меню."""

import logging

from maxapi import Dispatcher
from maxapi.filters.command import CommandStart
from maxapi.types import BotStarted, MessageCreated, MessageCallback

from src.utils.keyboard_utils import get_main_menu

logger = logging.getLogger(__name__)


def register_start_handlers(dp: Dispatcher):
    """Регистрация всех хендлеров из этого модуля."""
    
    @dp.bot_started()
    async def on_bot_started(event: BotStarted):
        """Срабатывает при первом открытии бота."""
        logger.info(f"bot_started | chat_id={event.chat_id}")
        await event.bot.send_message(
            chat_id=event.chat_id,
            text="👋 Привет! Я бот для приёма кодов выдачи заказов.",
            attachments=[get_main_menu()]
        )
    
    @dp.message_created(CommandStart())
    async def on_start(event: MessageCreated):
        """Обработчик команды /start."""
        logger.info("message_created /start")
        await event.message.answer(
            text="👋 Привет! Я бот для работы с кодами выдачи заказов.\nВыберите действие:",
            attachments=[get_main_menu()]
        )
    
    @dp.message_callback(lambda cb: cb.payload == "restart")
    async def on_restart(event: MessageCallback):
        """Перезапуск бота (сброс состояния)."""
        logger.info("message_callback | restart")
        await event.send_callback(notification="🔄 Перезапуск...")
        await event.message.answer(
            text="👋 Привет! Выберите действие:",
            attachments=[get_main_menu()]
        )