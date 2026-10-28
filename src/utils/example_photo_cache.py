"""Кеш токенов примеров фото для быстрой отправки клиентам.

Проблема: при каждом нажатии кнопки выбора магазина бот заново загружал
один и тот же файл примера на серверы MAX (~2200 мс).

Решение: при старте бота загружаем оба примера один раз, кешируем токены
и отправляем уже готовые вложения за ~75-85 мс.

Структура вложения (проверена экспериментально):
    Attachment(
        type=UploadType.IMAGE,
        payload=AttachmentUpload(
            type=UploadType.IMAGE,
            payload=AttachmentPayload(token=...),
        ),
    )
"""
import asyncio
import json
import logging
from typing import Dict, Optional

import aiofiles
from maxapi import Bot
from maxapi.types import Attachment
from maxapi.types.attachments.upload import AttachmentPayload, AttachmentUpload
from maxapi.enums.upload_type import UploadType

from src.utils.code_validator import get_example_image_path

logger = logging.getLogger(__name__)

STORES_TO_PRELOAD = ("store_ozon", "store_wildberries")

# Кеш: store_key -> готовый Attachment для отправки
_cache: Dict[str, Attachment] = {}
_lock = asyncio.Lock()


def _build_attachment(token: str) -> Attachment:
    """Собирает вложение из токена загруженного фото."""
    return Attachment(
        type=UploadType.IMAGE,
        payload=AttachmentUpload(
            type=UploadType.IMAGE,
            payload=AttachmentPayload(token=token),
        ),
    )


async def _upload_example_photo(bot: Bot, store_key: str) -> Optional[Attachment]:
    """Загружает один пример фото и возвращает готовое вложение."""
    photo_path = get_example_image_path(store_key)
    if photo_path is None:
        logger.warning("Example photo path not found for %s", store_key)
        return None

    try:
        async with aiofiles.open(photo_path, "rb") as f:
            photo_bytes = await f.read()

        upload_info = await bot.get_upload_url(type=UploadType.IMAGE)

        response_text = await bot.upload_file_buffer(
            filename=photo_path.name,
            url=upload_info.url,
            buffer=photo_bytes,
            type=UploadType.IMAGE,
        )

        upload_data = json.loads(response_text)
        photos = upload_data.get("photos", {})
        first_photo = next(iter(photos.values()), None)
        token = first_photo.get("token") if first_photo else None

        if not token:
            logger.error(
                "No token in upload response for %s: %s", store_key, response_text
            )
            return None

        logger.info("Preloaded example photo for %s", store_key)
        return _build_attachment(token)

    except Exception:
        logger.exception("Failed to preload example photo for %s", store_key)
        return None


async def preload_example_photos(bot: Bot) -> None:
    """
    Предзагружает примеры фото при старте бота.
    Не роняет бота при ошибках — просто логирует.
    """
    async with _lock:
        for store_key in STORES_TO_PRELOAD:
            attachment = await _upload_example_photo(bot, store_key)
            if attachment is not None:
                _cache[store_key] = attachment

    logger.info("Example photo cache ready: %d entries", len(_cache))


def get_cached_example(store_key: str) -> Optional[Attachment]:
    """Возвращает кешированное вложение или None, если кеш пуст."""
    return _cache.get(store_key)


async def refresh_example_photo(bot: Bot, store_key: str) -> Optional[Attachment]:
    """
    Перезагружает пример фото (например, при истечении токена).
    Обновляет кеш и возвращает новое вложение.
    """
    async with _lock:
        attachment = await _upload_example_photo(bot, store_key)
        if attachment is not None:
            _cache[store_key] = attachment
        return attachment


def _clear_cache() -> None:
    """Очищает кеш. Используется в тестах."""
    _cache.clear()