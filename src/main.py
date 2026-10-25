import asyncio
import logging

from maxapi import Bot, Dispatcher

from src.config.settings import settings
from src.webhook_setup import register_webhook
from src.utils.bot_commands import setup_bot_commands
from src.handlers.start import register_start_handlers
from src.handlers.send_code import register_send_code_handlers
from src.handlers.global_handlers import register_global_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

bot = Bot(token=settings.bot_token)
dp = Dispatcher()

register_start_handlers(dp)
register_send_code_handlers(dp)
register_global_handlers(dp)


async def main() -> None:
    logger.info("Starting MAX Bot in %s mode...", settings.environment)
    logger.info("Webhook URL: %s", settings.webhook_url)

    # 0. Регистрируем команды в меню бота
    await setup_bot_commands(bot)

    # 1. Поднимаем webhook-сервер
    serve_task = asyncio.create_task(
        dp.handle_webhook(
            bot=bot,
            host="0.0.0.0",
            port=settings.webhook_port,
            path=settings.webhook_path,
            secret=settings.webhook_secret,
        )
    )

    # 2. Даём серверу время подняться
    await asyncio.sleep(3)

    # 3. Регистрируем подписку в MAX
    await register_webhook(bot)

    # 4. Ждём завершения сервера
    await serve_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")