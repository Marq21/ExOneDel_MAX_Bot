import logging

from maxapi import Bot

from src.config.settings import settings

logger = logging.getLogger(__name__)


def _validate_webhook_settings() -> None:
    """Предупреждает о типичных ошибках в WEBHOOK_DOMAIN."""
    domain = settings.webhook_domain

    if "://" in domain:
        logger.error(
            "WEBHOOK_DOMAIN указан со схемой (%r) — нужен только домен, "
            "например max.example.ru",
            domain,
        )
    if domain.endswith("/"):
        logger.error(
            "WEBHOOK_DOMAIN заканчивается на '/' (%r) — слэш добавит webhook_path",
            domain,
        )


async def register_webhook(bot: Bot) -> None:
    """
    (Пере)регистрирует webhook-подписку в MAX.

    Зачем вызывать при каждом старте:
      1. MAX сам отписывает бота после 8 часов без успешного ответа 200 OK.
      2. MAX не заменяет подписки, а копит их — старые удаляем явно
         (bot.delete_webhook() в maxapi удаляет все подписки по очереди).
    """
    _validate_webhook_settings()

    try:
        current = await bot.get_subscriptions()
        existing = [s.url for s in (current.subscriptions or [])]

        if existing:
            logger.info("Найдены старые подписки %s — удаляем", existing)
            await bot.delete_webhook()
            logger.info("Старые подписки удалены")
        else:
            logger.info("Активных подписок нет")

        result = await bot.subscribe_webhook(
            url=settings.webhook_url,
            secret=settings.webhook_secret,
        )

        if not result.success:
            logger.error(
                "MAX отказал в регистрации webhook %s: %s",
                settings.webhook_url,
                result.message,
            )
            return

        logger.info("Webhook зарегистрирован: %s | ответ: %s", settings.webhook_url, result)

    except Exception as exc:
        # Не роняем бота: сервер должен подняться даже если MAX API недоступен.
        # При следующем рестарте контейнера попытка повторится.
        logger.exception("Не удалось зарегистрировать webhook: %s", exc)