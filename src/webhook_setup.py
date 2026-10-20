import logging

from maxapi import Bot

from config.settings import settings

logger = logging.getLogger(__name__)


async def register_webhook(bot: Bot) -> None:
    """
    (Пере)регистрирует webhook-подписку в MAX.

    Зачем вызывать при каждом старте:
      1. MAX сам отписывает бота после 8 часов без успешного ответа 200 OK.
      2. MAX не заменяет подписки, а копит их — старые удаляем явно.
    """
    try:
        current = await bot.get_subscriptions()
        existing = [s.url for s in (current.subscriptions or [])]

        if existing:
            logger.info("Найдены старые подписки %s — удаляем", existing)
            await bot.delete_webhook()

        result = await bot.subscribe_webhook(
            url=settings.webhook_url,
            secret=settings.webhook_secret,
        )
        logger.info("Webhook зарегистрирован: %s | ответ: %s", settings.webhook_url, result)

    except Exception as exc:
        # Не роняем бота: сервер должен подняться даже если MAX API недоступен.
        # При следующем рестарте контейнера попытка повторится.
        logger.exception("Не удалось зарегистрировать webhook: %s", exc)