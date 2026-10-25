import logging
import re
from dataclasses import dataclass

from maxapi import Bot
from maxapi.enums import ParseMode
from maxapi.types import MessageCreated
from maxapi.types.input_media import InputMediaBuffer

from src.utils.generate_codes import generate_barcode_image_async, generate_qr_code_async
from src.utils.config_loader import ConfigLoader
from src.utils.office_utils import get_office_by_id
from src.utils.keyboard_utils import get_main_menu

logger = logging.getLogger(__name__)

INVALID_PHONE_TEXT = (
    "❌ <b>Неверный формат номера</b>\n"
    "Принимаются форматы:\n"
    "• +7 999 123-45-67\n"
    "• 89991234567\n"
    "• 79991234567\n"
    "• 9991234567\n"
    "Пожалуйста, введите корректный номер:"
)


@dataclass
class OrderData:
    """Все данные заказа, необходимые для отправки кода в чат офиса."""
    store: str
    code: str
    name: str
    phone: str
    office_name: str
    target_chat: str


class CodeGenerationError(Exception):
    """Не удалось сгенерировать изображение кода."""


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


async def _fail(event: MessageCreated, context, text: str) -> None:
    """Сообщает об ошибке пользователю и очищает состояние FSM."""
    await event.message.answer(text, parse_mode=ParseMode.HTML)
    await context.clear()


async def _delete_message_quietly(bot: Bot, message) -> None:
    """Удаляет сообщение, не прерывая сценарий при ошибке удаления."""
    try:
        await bot.delete_message(message_id=message.message.body.mid)
    except Exception:
        logger.warning("Failed to delete message", exc_info=True)


async def _generate_code_image(store: str, code: str):
    """Генерирует штрихкод для OZON или QR-код для WB."""
    if store == "store_ozon":
        return await generate_barcode_image_async(code)
    return await generate_qr_code_async(code)


def _build_caption(store: str, code: str, name: str, phone: str, office_name: str) -> str:
    """Формирует текст сообщения с кодом для чата офиса."""
    if store == "store_ozon":
        return (
            f"{code}\n"
            f"ФИО: {name}\n"
            f"Телефон: {phone}\n"
            f"Пункт: {office_name}"
        )
    return (
        f"{code}\n"
        f"Телефон: {phone}\n"
        f"Пункт: {office_name}"
    )


async def _send_code_to_chat(
    bot: Bot,
    chat_id: str,
    caption: str,
    image_buffer,
) -> None:
    """Отправляет код с изображением в чат офиса, при сбое — только текст."""
    try:
        media = InputMediaBuffer(
            buffer=image_buffer.getvalue(),
            filename="code.png"
        )
        await bot.send_message(
            chat_id=int(chat_id),
            text=f"📦 {caption}",
            attachments=[media],
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.exception(f"Failed to send image, sending text only: {e}")
        await bot.send_message(
            chat_id=int(chat_id),
            text=f"📦 {caption}\n\n⚠️ (Не удалось загрузить изображение, отправлен только текст)",
            parse_mode=ParseMode.HTML
        )


async def _prepare_order(event: MessageCreated, context, phone: str) -> OrderData | None:
    """
    Собирает данные заказа из FSM и конфигурации.
    При ошибке сообщает пользователю и возвращает None.
    """
    data = await context.get_data()
    store = data.get("store")
    code = data.get("code")
    office_id = data.get("office_id")

    if not all([store, code, office_id]):
        logger.error("Missing data in FSM: store=%s, code=%s, office_id=%s", store, code, office_id)
        await _fail(event, context, "❌ Ошибка данных. Попробуйте начать заново.")
        return None

    office = get_office_by_id(office_id)
    if not office:
        logger.error("Office not found: %s", office_id)
        await _fail(event, context, "❌ Офис не найден.")
        return None

    target_chat = get_target_chat(store, office_id, data.get("ozon_pvz_id"))
    if not target_chat:
        logger.error("Target chat not found for office=%s, store=%s", office_id, store)
        await _fail(event, context, "❌ Ошибка конфигурации чата.")
        return None

    return OrderData(
        store=store,
        code=code,
        name=data.get("name", ""),
        phone=phone,
        office_name=office["name"],
        target_chat=target_chat,
    )


async def _deliver_code(bot: Bot, order: OrderData, progress_msg) -> None:
    """Генерирует изображение кода и отправляет его в чат офиса."""
    image_buffer = await _generate_code_image(order.store, order.code)
    if not image_buffer:
        raise CodeGenerationError(order.code)

    caption = _build_caption(order.store, order.code, order.name, order.phone, order.office_name)
    await _send_code_to_chat(bot, order.target_chat, caption, image_buffer)
    logger.info("Code sent to chat %s", order.target_chat)
    await _delete_message_quietly(bot, progress_msg)


async def process_final_order_data(event: MessageCreated, context, bot: Bot):
    """
    Основная функция финальной обработки: валидация телефона, генерация кода, отправка.
    """
    phone_text = event.message.body.text.strip()

    is_valid, formatted_phone = validate_phone(phone_text)
    logger.info("Phone validation: input='%s' -> valid=%s, formatted='%s'",
                 phone_text, is_valid, formatted_phone)

    if not is_valid:
        await event.message.answer(INVALID_PHONE_TEXT, parse_mode=ParseMode.HTML)
        return

    order = await _prepare_order(event, context, formatted_phone)
    if order is None:
        return

    progress_msg = await event.message.answer("🔄 Отправляю данные...")

    try:
        await _deliver_code(bot, order, progress_msg)

        await event.message.answer(
            f"✅ <b>Код успешно отправлен на {order.office_name}!</b>\n",
            attachments=[get_main_menu()],
            parse_mode=ParseMode.HTML
        )
        await context.clear()
    except CodeGenerationError:
        logger.error("Failed to generate image for code: %s", order.code)
        await _delete_message_quietly(bot, progress_msg)
        await _fail(event, context, "❌ Ошибка: не удалось сгенерировать изображение кода.")
    except Exception:
        logger.exception("Error in process_final_order_data")
        await _delete_message_quietly(bot, progress_msg)
        await _fail(event, context, "❌ Произошла ошибка при отправке. Попробуйте позже.")