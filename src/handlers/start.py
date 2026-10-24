import logging
from maxapi import Dispatcher, F
from maxapi.filters.command import CommandStart
from maxapi.types import BotStarted, MessageCreated, MessageCallback
from src.utils.keyboard_utils import get_main_menu

logger = logging.getLogger(__name__)

def register_start_handlers(dp: Dispatcher):
    @dp.bot_started()
    async def on_bot_started(event: BotStarted):
        logger.info(f"bot_started | chat_id={event.chat_id}")
        await event.bot.send_message(
            chat_id=event.chat_id,
            text="👋 Привет! Я бот для приёма кодов выдачи заказов.",
            attachments=[get_main_menu()]
        )
    
    @dp.message_created(CommandStart())
    async def on_start(event: MessageCreated):
        logger.info("message_created /start")
        await event.message.answer(
            text="👋 Привет! Я бот для работы с кодами выдачи заказов.\nВыберите действие:",
            attachments=[get_main_menu()]
        )
    
    @dp.message_callback(F.callback.payload == "restart")
    async def on_restart(event: MessageCallback):
        logger.info("message_callback | restart")
        
        # Отвечаем на callback через метод бота
        await event.bot.send_callback(
            callback_id=event.callback.callback_id,
            notification="🔄 Перезапуск..."
        )
        
        await event.message.answer(
            text="👋 Привет! Выберите действие:",
            attachments=[get_main_menu()]
        )