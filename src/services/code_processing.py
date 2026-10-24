"""Финальная обработка заказа: генерация кода, отправка в чат."""

import logging
import re
import json

from maxapi import Bot
from maxapi.enums import ParseMode
from maxapi.types import MessageCreated
from maxapi.enums.upload_type import UploadType
from maxapi.types import PhotoAttachmentRequestPayload

from src.utils.generate_codes import generate_barcode_image_async, generate_qr_code_async
from src.utils.config_loader import ConfigLoader
from src.utils.office_utils import get_office_by_id
from src.utils.keyboard_utils import get_main_menu

logger = logging.getLogger(__name__)


def validate_phone(phone_text: str) -> tuple[bool, str | None]:
    """
    Проверяет и нормализует российский номер телефона.
    Принимает форматы: +79991234567, 89991234567, 79991234567, 
    9991234567, +7 (999) 123-45-67 и т.д.
    """
    if not phone_text:
        return False, None

    # Оставляем только цифры
    digits = re.sub(r'\D', '', phone_text)

    # Нормализуем длину и код страны
    if len(digits) == 11:
        if digits.startswith('8'):
            digits = '7' + digits[1:]
        elif not digits.startswith('7'):
            return False, None
    elif len(digits) == 10:
        # 10 цифр без кода страны (обычно мобильные начинаются с 9)
        if digits.startswith('9'):
            digits = '7' + digits
        else:
            return False, None
    else:
        return False, None

    # Финальная проверка: должно быть 11 цифр, начинаться с 7
    if len(digits) != 11 or not digits.startswith('7'):
        return False, None

    formatted_phone = f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return True, formatted_phone


def get_target_chat(store: str, office_id: str, ozon_pvz_id: str = None) -> str | None:
    """Определяет целевой чат для отправки кода."""
    config = ConfigLoader.get_config()
    
    if store == "store_ozon":
        # Для OZON используем специфичные чаты по ПВЗ
        pvz_id = ozon_pvz_id or "trolleibusnaya"
        chat_key = f"ozon_{pvz_id}"
        target_chat = config["chats_config"].get(office_id, {}).get(chat_key)
    else:  # WB
        target_chat = config["chats_config"].get(office_id, {}).get("wb")
    
    return target_chat


async def process_final_order_data(event: MessageCreated, context, bot: Bot):
    """
    Основная функция финальной обработки: валидация телефона, генерация кода, отправка.
    """
    phone_text = event.message.body.text.strip()
    
    is_valid, formatted_phone = validate_phone(phone_text)
    logger.info("Phone validation: input='%s' -> valid=%s, formatted='%s'",
                 phone_text, is_valid, formatted_phone)
    
    if not is_valid:
        await event.message.answer(
            "❌ <b>Неверный формат номера</b>\n"
            "Принимаются форматы:\n"
            "• +7 999 123-45-67\n"
            "• 89991234567\n"
            "• 79991234567\n"
            "• 9991234567\n"
            "Пожалуйста, введите корректный номер:",
            parse_mode=ParseMode.HTML
        )
        return
    
    # === ШАГ 2: Получение данных из FSM ===
    data = await context.get_data()
    store = data.get("store")
    code = data.get("code")
    name = data.get("name", "")
    office_id = data.get("office_id")
    
    if not all([store, code, office_id]):
        logger.error(f"Missing data in FSM: store={store}, code={code}, office_id={office_id}")
        await event.message.answer("❌ Ошибка данных. Попробуйте начать заново.")
        await context.clear()
        return
    
    # === ШАГ 3: Получение информации об офисе ===
    office = get_office_by_id(office_id)
    if not office:
        logger.error(f"Office not found: {office_id}")
        await event.message.answer("❌ Офис не найден.")
        await context.clear()
        return
    
    office_name = office["name"]
    
    # === ШАГ 4: Определение целевого чата ===
    target_chat = get_target_chat(store, office_id, data.get("ozon_pvz_id"))
    if not target_chat:
        logger.error(f"Target chat not found for office={office_id}, store={store}")
        await event.message.answer("❌ Ошибка конфигурации чата.")
        await context.clear()
        return
    
    # === ШАГ 5: Показать прогресс ===
    progress_msg = await event.message.answer("🔄 Отправляю данные...")
    
    try:
        # === ШАГ 6: Генерация изображения кода ===
        if store == "store_ozon":
            image_buffer = await generate_barcode_image_async(code)
            caption = (
                f"Код для получения OZON: {code}\n"
                f"ФИО: {name}\n"
                f"Телефон: {formatted_phone}\n"
                f"Пункт: {office_name}"
            )
        else:  # WB
            image_buffer = await generate_qr_code_async(code)
            caption = (
                f"Код для получения Wildberries:\n{code}\n"
                f"Телефон: {formatted_phone}\n"
                f"Пункт: {office_name}"
            )
        
        if not image_buffer:
            logger.error(f"Failed to generate image for code: {code}")
            await bot.delete_message(message_id=progress_msg.message.body.mid)
            await event.message.answer("❌ Ошибка: не удалось сгенерировать изображение кода.")
            await context.clear()
            return
        
        try:
            # 7.1. Получаем URL для загрузки
            upload_info = await bot.get_upload_url(type=UploadType.IMAGE)
            upload_url = upload_info.url
            logger.info("Got upload URL for image")
            
            # 7.2. Загружаем изображение из буфера
            image_bytes = image_buffer.getvalue()
            upload_response_text = await bot.upload_file_buffer(
                filename="code.png",
                url=upload_url,
                buffer=image_bytes,
                type=UploadType.IMAGE
            )
            logger.debug(f"Upload response: {upload_response_text}")
            
            # 7.3. Парсим ответ — получаем токен фото
            upload_data = json.loads(upload_response_text)

            # Извлекаем токен из структуры {'photos': {'0': {'token': '...'}}}
            photos = upload_data.get("photos", {})
            photo_token = None

            if photos:
                # Берём первое фото (обычно оно одно, ключ может быть '0', '640' и т.д.)
                first_photo = next(iter(photos.values()), None)
                if first_photo:
                    photo_token = first_photo.get("token")

            # Fallback на случай, если API вернёт другую структуру
            if not photo_token:
                photo_token = upload_data.get("token") or upload_data.get("photoToken")

            logger.info(f"Upload successful, token found: {photo_token is not None}")

            if not photo_token:
                raise ValueError(f"Upload response missing token: {upload_data}")
            
            # 7.4. Создаём вложение
            photo_payload = PhotoAttachmentRequestPayload(
                token=photo_token,
                url=upload_url
            )
            
            # 7.5. Отправляем сообщение с фото и текстом
            await bot.send_message(
                chat_id=int(target_chat),
                text=f"📦 {caption}",
                attachments=[photo_payload],
                parse_mode=ParseMode.HTML
            )
            
            logger.info(f"Code with image sent to chat {target_chat}")
            
        except Exception as e:
            logger.exception(f"Failed to upload/send image, sending text only: {e}")
            # Fallback: отправляем только текст
            await bot.send_message(
                chat_id=int(target_chat),
                text=f"📦 {caption}\n\n⚠️ (Не удалось загрузить изображение, отправлен только текст)",
                parse_mode=ParseMode.HTML
            )
        
        logger.info(f"Code sent to chat {target_chat}")
        
        # === ШАГ 8: Уведомление пользователя ===
        await bot.delete_message(message_id=progress_msg.message.body.mid)
        await event.message.answer(
            f"✅ <b>Код успешно отправлен на {office_name}!</b>\n",
            attachments=[get_main_menu()],
            parse_mode=ParseMode.HTML
        )
        
        # === ШАГ 9: Очистка FSM ===
        await context.clear()
        
    except Exception:
        logger.exception("Error in process_final_order_data")
        try:
            await bot.delete_message(message_id=progress_msg.message.body.mid)
        except:
            pass
        await event.message.answer("❌ Произошла ошибка при отправке. Попробуйте позже.")
        await context.clear()