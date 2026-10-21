"""Обработка фото с кодом: скачивание, распознавание, валидация."""

import logging

from maxapi import Bot
from maxapi.types import MessageCreated, PhotoAttachmentPayload

from src.utils.image_utils import extract_code_from_image_async
from src.utils.code_validator import is_code_valid_for_store
from src.utils.store_utils import get_readable_store_name
from src.states.code_states import CodeStates
from src.utils.keyboard_utils import get_office_keyboard

logger = logging.getLogger(__name__)


async def process_final_code_photo(
    event: MessageCreated,
    context,
    bot: Bot,
    photo_attachment
):
    """
    Основная функция обработки фото с кодом.
    """
    processing_msg = await event.message.answer("🔍 Обрабатываю изображение...")
    
    try:
        # === ШАГ 1: Скачивание фото ===
        photo_url = photo_attachment.payload.url
        logger.debug(f"Downloading photo from {photo_url}")
        
        # Скачиваем фото через bot.download_bytes
        image_bytes = await bot.download_bytes(photo_url)
        
        if not image_bytes:
            await event.message.answer("❌ Не удалось скачать изображение. Попробуйте ещё раз.")
            await bot.delete_message(message_id=processing_msg.body.mid)
            return
        
        # === ШАГ 2: Распознавание кода ===
        code = await extract_code_from_image_async(image_bytes)
        
        if not code:
            await bot.delete_message(message_id=processing_msg.body.mid)
            await event.message.answer(
                "❌ <b>Не удалось распознать код</b>\n"
                "Возможные причины:\n"
                "• Слишком темное/светлое фото\n"
                "• Код не в фокусе\n"
                "• Часть кода обрезана\n"
                "Попробуйте сделать более четкий скриншот."
            )
            return
        
        # === ШАГ 3: Валидация кода ===
        data = await context.get_data()
        current_store = data.get('store')
        
        if not is_code_valid_for_store(code, current_store):
            # Определяем, откуда на самом деле код
            if is_code_valid_for_store(code, "store_ozon"):
                actual_store = "OZON"
            elif is_code_valid_for_store(code, "store_wildberries"):
                actual_store = "Wildberries"
            else:
                actual_store = "неизвестный магазин"
            
            selected_store = get_readable_store_name(current_store)
            
            await bot.delete_message(message_id=processing_msg.body.mid)
            await event.message.answer(
                f"❌ <b>Ошибка!</b>\n"
                f"Вы выбрали <b>{selected_store}</b>, но отправили код от <b>{actual_store}</b>.\n"
                f"Пожалуйста, отправьте правильный код."
            )
            return
        
        # === ШАГ 4: Успех — показываем выбор офиса ===
        await context.update_data(code=code)
        await bot.delete_message(message_id=processing_msg.body.mid)
        
        await event.message.answer(
            text=f"✅ <b>Код распознан!</b>\n<code>{code}</code>\n"
                 f"Теперь выберите офис, где планируете забрать заказ:",
            attachments=[get_office_keyboard()]
        )
        
        await context.set_state(CodeStates.CHOOSING_OFFICE)
        
    except Exception as e:
        logger.exception(f"Error in process_final_code_photo")
        try:
            await bot.delete_message(message_id=processing_msg.body.mid)
        except:
            pass
        await event.message.answer("❌ Произошла ошибка при обработке фото. Попробуйте еще раз.")