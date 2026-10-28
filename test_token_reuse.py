"""Проверка: можно ли переиспользовать один токен для нескольких отправок."""
import asyncio
import json
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

    # === Шаг 1: Получаем URL и токен ===
    upload_info = await bot.get_upload_url(type=UploadType.IMAGE)
    print(f"[1] get_upload_url вернул:")
    print(f"    url: {upload_info.url[:60]}...")
    
    # Проверяем, есть ли token в upload_info
    if hasattr(upload_info, 'token'):
        print(f"    token: {upload_info.token[:30]}...")
        token = upload_info.token
    else:
        print(f"    token: НЕ НАЙДЕН в upload_info, проверяем структуру...")
        print(f"    Атрибуты: {[a for a in dir(upload_info) if not a.startswith('_')]}")
        return

    # === Шаг 2: Загружаем байты на URL ===
    response_text = await bot.upload_file_buffer(
        filename=photo_path.name,
        url=upload_info.url,
        buffer=photo_bytes,
        type=UploadType.IMAGE,
    )
    print(f"[2] upload_file_buffer: OK")
    print(f"    Ответ: {response_text[:100]}...")

    # === Шаг 3: Отправляем ОДНИМ И ТЕМ ЖЕ токеном ДВАЖДЫ ===
    attachment = Attachment(
        type=AttachmentType.IMAGE,
        payload=PhotoAttachmentRequestPayload(token=token),
    )

    for attempt in (1, 2):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"⏱ Тест переиспользования токена, отправка #{attempt}",
                attachments=[attachment],
                parse_mode=ParseMode.HTML,
            )
            print(f"[3] send_message #{attempt}: УСПЕХ")
        except Exception as exc:
            print(f"[3] send_message #{attempt}: ОШИБКА: {exc}")
            break

    print("=" * 70)
    print("Если обе отправки успешны — токен переиспользуется, кеш работает!")


if __name__ == "__main__":
    asyncio.run(main())