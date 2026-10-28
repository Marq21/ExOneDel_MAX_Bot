"""Проверка: можно ли переиспользовать один токен для нескольких отправок."""
import asyncio
import json
import time
from pathlib import Path

from maxapi import Bot
from maxapi.enums.attachment import AttachmentType
from maxapi.enums.parse_mode import ParseMode
from maxapi.enums.upload_type import UploadType
from maxapi.types.attachments.attachment import Attachment
from maxapi.types.attachments.image import PhotoAttachmentRequestPayload

from src.config.settings import settings
from src.utils.config_loader import ConfigLoader


async def main():
    bot = Bot(token=settings.bot_token)
    chat_id = int(ConfigLoader.get_config()["admin_error_chat_id"])
    photo_path = Path("static/images/ozon-ok.jpg")
    photo_bytes = photo_path.read_bytes()

    print(f"Файл: {photo_path.name}, размер: {len(photo_bytes)} байт")
    print(f"Чат для теста: {chat_id}")
    print("=" * 70)

    # === Шаг 1: Получаем URL для загрузки ===
    t0 = time.perf_counter()
    upload_info = await bot.get_upload_url(type=UploadType.IMAGE)
    print(f"[1] get_upload_url: {(time.perf_counter() - t0) * 1000:.0f} мс")
    print(f"    url: {upload_info.url[:60]}...")

    # === Шаг 2: Загружаем байты на URL ===
    t0 = time.perf_counter()
    response_text = await bot.upload_file_buffer(
        filename=photo_path.name,
        url=upload_info.url,
        buffer=photo_bytes,
        type=UploadType.IMAGE,
    )
    print(f"[2] upload_file_buffer: {(time.perf_counter() - t0) * 1000:.0f} мс")
    print(f"    Ответ: {response_text[:100]}...")

    # Извлекаем токен из ответа
    upload_data = json.loads(response_text)
    photos = upload_data.get("photos", {})
    if not photos:
        print("    ОШИБКА: в ответе нет поля 'photos'")
        return
    
    first_photo = next(iter(photos.values()), None)
    if not first_photo or "token" not in first_photo:
        print(f"    ОШИБКА: в photos нет токена. Структура: {upload_data}")
        return

    token = first_photo["token"]
    print(f"    Токен получен: {token[:40]}...")

    # === Шаг 3: Отправляем ОДНИМ И ТЕМ ЖЕ токеном ДВАЖДЫ ===
    attachment = Attachment(
        type=AttachmentType.IMAGE,
        payload=PhotoAttachmentRequestPayload(token=token),
    )

    for attempt in (1, 2, 3):
        t0 = time.perf_counter()
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"⏱ Тест переиспользования токена, отправка #{attempt}",
                attachments=[attachment],
                parse_mode=ParseMode.HTML,
            )
            elapsed = (time.perf_counter() - t0) * 1000
            print(f"[3] send_message #{attempt}: УСПЕХ за {elapsed:.0f} мс")
        except Exception as exc:
            print(f"[3] send_message #{attempt}: ОШИБКА: {exc}")
            break

    print("=" * 70)
    print("Если все 3 отправки успешны — токен переиспользуется, кеш работает!")


if __name__ == "__main__":
    asyncio.run(main())