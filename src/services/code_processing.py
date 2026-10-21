"""Финальная обработка заказа: генерация кода, отправка в чат."""

import logging
from io import BytesIO

from maxapi import Bot
from maxapi.types import MessageCreated, InputMedia, PhotoAttachmentRequestPayload

from src.utils.generate_codes import generate_barcode_image_async, generate_qr_code_async
from src.utils.config_loader import ConfigLoader
from src.utils.office_utils import get_office_by_id
from src.utils.keyboard_utils import get_main_menu

logger = logging.getLogger(__name__)


def validate_phone(phone_text: str) -> tuple[bool, str | None]:
    """Проверяет формат телефона."""
    cleaned_phone = ''.join(filter(str.isdigit, phone_text))
    if not cleaned_phone.startswith('7') or len(cleaned_phone) != 11:
        return False, None
    formatted_phone = f"+7 ({cleaned_phone[1:4]}) {cleaned_phone[4:7]}-{cleaned_phone[7:9]}-{cleaned_phone[9:11]}"
    return True, formatted_phone


async def get_target_chat(store: str, office_id: str, ozon_pvz_id: str = None) -> str | None:
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
    
    # === ШАГ 1: Валидация телефона ===
    is_valid, formatted_phone = validate_phone(phone_text)
    if not is_valid:
        await event.message.answer(
            "❌ <b>Неверный формат номера</b>\n"
            "• Начинаться с 7\n"
            "• Содержать 11 цифр\n"
            "• Пример: +7 XXX XXX-XX-XX\n"
            "Пожалуйста, введите корректный номер:"
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
    target_chat = await get_target_chat(store, office_id, data.get("ozon_pvz_id"))
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
            await bot.delete_message(message_id=progress_msg.body.mid)
            await event.message.answer("❌ Ошибка: не удалось сгенерировать изображение кода.")
            await context.clear()
            return
        
        # === ШАГ 7: Загрузка фото в MAX ===
        # TODO: Реализовать загрузку фото через get_upload_url
        # Пока отправляем только текст
        await bot.send_message(
            chat_id=int(target_chat),
            text=f"📦 {caption}\n\n⚠️ (Фото временно недоступно)"
        )
        
        logger.info(f"Code sent to chat {target_chat}")
        
        # === ШАГ 8: Уведомление пользователя ===
        await bot.delete_message(message_id=progress_msg.body.mid)
        await event.message.answer(
            f"✅ <b>Код успешно отправлен на {office_name}!</b>\n",
            attachments=[get_main_menu()]
        )
        
        # === ШАГ 9: Очистка FSM ===
        await context.clear()
        
    except Exception as e:
        logger.exception(f"Error in process_final_order_data")
        try:
            await bot.delete_message(message_id=progress_msg.body.mid)
        except:
            pass
        await event.message.answer("❌ Произошла ошибка при отправке. Попробуйте позже.")
        await context.clear()