"""Обработчики сценария отправки кода: магазин, фото, офис, ФИО, телефон."""

import logging
import aiofiles
import time

from maxapi import Dispatcher, F
from maxapi.context import MemoryContext
from maxapi.types import Attachment, MessageCallback, MessageCreated, PhotoAttachmentPayload
from maxapi.enums.parse_mode import ParseMode
from maxapi.types.input_media import InputMediaBuffer

from src.services.code_photo_processing import process_final_code_photo
from src.services.code_processing import process_final_order_data
from src.states.code_states import CodeStates
from src.utils.code_validator import get_example_image_path, get_store_description
from src.utils.keyboard_utils import get_main_menu, get_store_selection_keyboard
from src.utils.chat_utils import is_private_chat
from src.utils.antispam import ANTISPAM_BLOCKED_NOTIFICATION, antispam_manager
from src.utils.example_photo_cache import get_cached_example, refresh_example_photo
from src.utils.code_acceptance_schedule import (
    format_working_hours_message,
    is_session_allowed_to_proceed,
)


logger = logging.getLogger(__name__)

STORE_PROMPT = "🛍 <b>Выберите маркетплейс:</b>"
PHONE_PROMPT = "📱 <b>Введите ваш номер телефона:</b>\n<i>Формат: +7 XXX XXX-XX-XX</i>"
SCHEDULE_CLOSED_TITLE = "🕗<b>К сожалению, приём кодов сейчас закрыт.</b>"


def get_schedule_message() -> str:
    """
    Собирает сообщение о закрытом приёме кодов с актуальным расписанием.

    Расписание читается из конфига при каждом вызове, поэтому изменения
    в конфиге сразу попадают в сообщение (не «замораживаются» на импорте).
    """
    return f"{SCHEDULE_CLOSED_TITLE}\n{format_working_hours_message()}"


def _find_photo_attachment(attachments: list) -> Attachment | None:
    """Возвращает первое вложение с фотографией."""
    for attachment in attachments:
        payload = getattr(attachment, "payload", None)
        if isinstance(payload, PhotoAttachmentPayload):
            return attachment
    return None


async def _send_code_request(event: MessageCallback, store: str) -> None:
    """Отправляет инструкцию и пример скриншота для выбранного магазина."""
    caption = (
        "📸 <b>Отправьте скриншот с кодом выдачи</b>\n"
        f"{get_store_description(store)}\n"
        "<i>Убедитесь, что код хорошо виден на фото</i>"
    )

    # 1. Быстрый путь: готовое вложение из кеша (~80 мс)
    cached = get_cached_example(store)
    if cached is not None:
        try:
            await event.message.answer(
                text=caption,
                attachments=[cached],
                parse_mode=ParseMode.HTML,
            )
            logger.debug("Sent cached example photo for %s", store)
            return
        except Exception:
            # Токен мог истечь — перезагружаем и пробуем ещё раз
            logger.warning("Cached example photo failed for %s, refreshing", store)
            refreshed = await refresh_example_photo(event.bot, store)
            if refreshed is not None:
                try:
                    await event.message.answer(
                        text=caption,
                        attachments=[refreshed],
                        parse_mode=ParseMode.HTML,
                    )
                    logger.debug("Sent refreshed example photo for %s", store)
                    return
                except Exception:
                    logger.exception("Refreshed example photo also failed for %s", store)

    # 2. Медленный путь: читаем файл и загружаем заново (~2200 мс)
    photo_path = get_example_image_path(store)
    if photo_path is not None:
        try:
            async with aiofiles.open(photo_path, "rb") as f:
                photo_bytes = await f.read()

            media = InputMediaBuffer(
                buffer=photo_bytes,
                filename=photo_path.name
            )

            await event.message.answer(
                text=caption,
                attachments=[media],
                parse_mode=ParseMode.HTML
            )
            logger.debug("Sent example photo via upload: %s", photo_path)
            return
        except Exception:
            logger.exception("Error sending example photo: %s", photo_path)

    # 3. Fallback: только текст
    await event.message.answer(text=caption, parse_mode=ParseMode.HTML)
    logger.warning("Example photo not sent for store: %s", store)


async def start_send_code(event: MessageCallback, context: MemoryContext) -> None:
    """Запуск сценария — выбор маркетплейса."""
    user_id = event.callback.user.user_id
    
    # Антиспам-проверка
    if not antispam_manager.is_allowed(user_id):
        await event.bot.send_callback(
            callback_id=event.callback.callback_id,
            notification=ANTISPAM_BLOCKED_NOTIFICATION
        )
        return
    
    logger.debug("Callback 'send_code' from user %s", user_id)
    await event.bot.send_callback(
        callback_id=event.callback.callback_id,
        notification="Проверка расписания..."
    )
    
    await context.clear()
    
    if not is_session_allowed_to_proceed(user_id=user_id):
        await event.message.answer(
            get_schedule_message(),
            parse_mode=ParseMode.HTML
        )
        return
    
    await context.update_data(session_start_timestamp=int(time.time()))
    await context.set_state(CodeStates.CHOOSING_STORE)
    await event.message.answer(
        text=STORE_PROMPT,
        attachments=[get_store_selection_keyboard()],
        parse_mode=ParseMode.HTML
    )


async def process_store_choice(event: MessageCallback, context: MemoryContext) -> None:
    """Обработка выбора магазина."""
    user_id = event.callback.user.user_id
    await event.bot.send_callback(
        callback_id=event.callback.callback_id,
        notification="✅"
    )
    store = event.callback.payload
    logger.debug("Store choice: %s from user %s", store, user_id)
    await context.update_data(store=store)
    await _send_code_request(event, store)
    await context.set_state(CodeStates.RECEIVING_CODE)


async def process_code_photo(event: MessageCreated, context: MemoryContext) -> None:
    """Обработка фото с кодом."""
    if not is_private_chat(event.message):
        return
    
    user_id = event.message.sender.user_id
    
    logger.debug("Received photo from user %s", user_id)
    photo_attachment = _find_photo_attachment(event.message.body.attachments)
    if photo_attachment is None:
        await event.message.answer("📸 Я не вижу фото в сообщении. Попробуйте ещё раз.")
        return
    await process_final_code_photo(event, context, event.message.bot, photo_attachment)


async def process_office_choice(event: MessageCallback, context: MemoryContext) -> None:
    user_id = event.callback.user.user_id
    await event.bot.send_callback(
        callback_id=event.callback.callback_id,
        notification="✅"
    )
    office_id = event.callback.payload.replace("office_", "")
    logger.debug("Office choice: %s from user %s", office_id, user_id)
    await context.update_data(office_id=office_id)
    data = await context.get_data()
    store = data.get("store")
    if store == "store_ozon":
        await event.message.answer(
            text="👤 <b>Введите ваше ФИО:</b>\n<i>Фамилия Имя Отчество</i>",
            parse_mode=ParseMode.HTML
        )
        await context.set_state(CodeStates.WAITING_FOR_NAME)
    else:
        await event.message.answer(text=PHONE_PROMPT, parse_mode=ParseMode.HTML)
        await context.set_state(CodeStates.WAITING_FOR_PHONE)


async def process_name_input(event: MessageCreated, context: MemoryContext) -> None:
    if not is_private_chat(event.message):
        return

    name = event.message.body.text.strip()
    if len(name) < 1 or len(name) > 100:
        await event.message.answer(
            "❌ ФИО должно содержать от 1 до 100 символов.\n"
            "Пожалуйста, введите корректное ФИО:",
            parse_mode=ParseMode.HTML
        )
        return
    await context.update_data(name=name)
    await event.message.answer(text=PHONE_PROMPT, parse_mode=ParseMode.HTML)
    await context.set_state(CodeStates.WAITING_FOR_PHONE)


async def process_phone_input(event: MessageCreated, context: MemoryContext) -> None:
    """Обработка ввода телефона и финальная отправка."""
    if not is_private_chat(event.message):
        return
    
    user_id = event.message.sender.user_id
    
    data = await context.get_data()
    session_start = data.get("session_start_timestamp")
    if not is_session_allowed_to_proceed(session_start, user_id=user_id):
        await event.message.answer(
            get_schedule_message(),
            parse_mode=ParseMode.HTML
        )
        await context.clear()
        return
    
    phone_text = event.message.body.text.strip() if event.message.body.text else ""
    logger.info("Phone input received: '%s' from user %s", phone_text, user_id)
    await process_final_order_data(event, context, event.message.bot)


async def back_to_store_choice(event: MessageCallback, context: MemoryContext) -> None:
    await event.bot.send_callback(
        callback_id=event.callback.callback_id,
        notification="✅"
    )
    await context.set_state(CodeStates.CHOOSING_STORE)
    await event.message.answer(
        text=STORE_PROMPT,
        attachments=[get_store_selection_keyboard()],
        parse_mode=ParseMode.HTML
    )


async def back_to_menu(event: MessageCallback, context: MemoryContext) -> None:
    await event.bot.send_callback(
        callback_id=event.callback.callback_id,
        notification="✅"
    )
    await context.clear()
    await event.message.answer(
        text="Выберите действие:",
        attachments=[get_main_menu()],
        parse_mode=ParseMode.HTML
    )


def register_send_code_handlers(dp: Dispatcher) -> None:
    """Регистрация всех хендлеров сценария отправки кода."""
    dp.message_callback(F.callback.payload == "send_code")(start_send_code)
    
    dp.message_callback(
        F.callback.payload.in_(["store_ozon", "store_wildberries"]),
        states=CodeStates.CHOOSING_STORE,
    )(process_store_choice)
    
    dp.message_created(
        F.message.body.attachments,
        states=CodeStates.RECEIVING_CODE,
    )(process_code_photo)
    
    dp.message_callback(
        F.callback.payload.startswith("office_"),
        states=CodeStates.CHOOSING_OFFICE,
    )(process_office_choice)
    
    dp.message_created(
        F.message.body.text,
        states=CodeStates.WAITING_FOR_NAME,
    )(process_name_input)
    
    dp.message_created(
        F.message.body.text,
        states=CodeStates.WAITING_FOR_PHONE,
    )(process_phone_input)
    
    dp.message_callback(
        F.callback.payload == "back_to_store_choice",
        states=CodeStates.CHOOSING_OFFICE,
    )(back_to_store_choice)
    
    dp.message_callback(F.callback.payload == "back_to_menu", states="*")(back_to_menu)
