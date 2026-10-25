"""Регистрация команд бота в меню MAX."""
import logging

from maxapi import Bot
from maxapi.types import BotCommand

logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot) -> None:
    """
    Устанавливает список команд, отображаемых в меню бота.
    Вызывается один раз при старте приложения.
    
    Использует bot.set_commands() (PATCH /me/commands).
    """
    commands = [
        BotCommand(name="start", description="Главное меню"),
        BotCommand(name="help", description="Справка по работе с ботом"),
    ]
    
    try:
        # Распаковываем список через * — метод принимает *commands, не list
        await bot.set_commands(*commands)
        logger.info("Bot commands registered successfully")
    except Exception:
        # Не роняем бота из-за неудачной регистрации команд
        logger.exception("Failed to register bot commands")