import asyncio
import logging

from maxapi import Bot, Dispatcher, F
from maxapi.filters.command import CommandStart
from maxapi.types import BotStarted, MessageCreated

from config.settings import settings
from webhook_setup import register_webhook

# --- Логирование ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# --- Инициализация ---
bot = Bot(token=settings.bot_token)
dp = Dispatcher()


# --- ХЕНДЛЕРЫ ---

@dp.bot_started()
async def on_bot_started(event: BotStarted) -> None:
    """Срабатывает, когда пользователь нажимает «Начать» / впервые открывает бота."""
    logger.info("bot_started | chat_id=%s", event.chat_id)
    await bot.send_message(
        chat_id=event.chat_id,
        text="Привет! Я бот приёма кодов. 📦\nОтправь мне /start, чтобы начать.",
    )


@dp.message_created(CommandStart())
async def on_start(event: MessageCreated) -> None:
    """Команда /start."""
    logger.info("message_created /start")
    await event.message.answer(
        "Привет! Я работаю через Webhook 🚀\n"
        "Напиши мне что-нибудь — я отвечу эхом."
    )


@dp.message_created(F.message.body.text)
async def on_text(event: MessageCreated) -> None:
    """Эхо на любое текстовое сообщение."""
    text = event.message.body.text
    logger.info("message_created | text=%r", text)
    await event.message.answer(f"Вы написали: {text}")


# --- ЗАПУСК ---

async def main() -> None:
    logger.info("Starting MAX Bot in %s mode...", settings.environment)
    logger.info("Webhook URL: %s", settings.webhook_url)

    # 1. Поднимаем webhook-сервер как фоновую задачу.
    #    Сначала именно сервер: к моменту регистрации подписки endpoint
    #    уже должен отвечать, иначе MAX не сможет доставлять события.
    serve_task = asyncio.create_task(
        dp.handle_webhook(
            bot=bot,
            host="0.0.0.0",
            port=settings.webhook_port,
            path=settings.webhook_path,
            secret=settings.webhook_secret,
        )
    )

    # 2. Даём серверу время подняться.
    await asyncio.sleep(3)

    # 3. Регистрируем подписку в MAX.
    await register_webhook(bot)

    # 4. Ждём завершения сервера (блокирует до остановки процесса).
    await serve_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")