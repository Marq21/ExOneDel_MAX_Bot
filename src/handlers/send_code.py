"""Обработчики сценария отправки кода: магазин, фото, офис, ФИО, телефон."""

import logging

from maxapi import Dispatcher, F
from maxapi.context import MemoryContext
from maxapi.types import Attachment, MessageCallback, MessageCreated, PhotoAttachmentPayload

from src.services.code_photo_processing import process_final_code_photo
from src.services.code_processing import process_final_order_data
from src.states.code_states import CodeStates
from src.utils.code_validator import get_example_image_path, get_store_description
from src.utils.keyboard_utils import get_main_menu, get_store_selection_keyboard

logger = logging.getLogger(__name__)

STORE_PROMPT = "🛍 <b>Выберите маркетплейс:</b>"
PHONE_PROMPT = "📱 <b>Введите ваш номер телефона:</b>\n<i>Формат: +7 XXX XXX-XX-XX</i>"


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

    photo_path = get_example_image_path(store)
    if photo_path is not None:
        # Загрузка фото в MAX пока не реализована — отправляем только текст
        logger.warning("Photo upload not implemented yet: %s", photo_path)

    await event.message.answer(text=caption)


async def start_send_code(event: MessageCallback, context: MemoryContext) -> None:
    """Запуск сценария — выбор маркетплейса."""

    # ВРЕМЕННАЯ ДИАГНОСТИКА — удалить после проверки
    logger.info("DEBUG event attrs: %s", [a for a in dir(event) if not a.startswith('_')])
    logger.info("DEBUG event.callback attrs: %s", [a for a in dir(event.callback) if not a.startswith('_')])
    # удалить


    logger.debug("Callback 'send_code' from user %s", event.user.user_id)

    await event.bot.send_callback(
        callback_id=event.callback.callback_id,
        notification="Выбор магазина..."
    )
    
    await context.set_state(CodeStates.CHOOSING_STORE)
    await event.message.answer(
        text=STORE_PROMPT,
        attachments=[get_store_selection_keyboard()],
    )


async def process_store_choice(event: MessageCallback, context: MemoryContext) -> None:
    """Обработка выбора магазина."""
    await event.bot.send_callback(callback_id=event.callback.callback_id)
    
    store = event.callback.payload
    logger.debug("Store choice: %s from user %s", store, event.callback.user.user_id)
    
    await context.update_data(store=store)
    await _send_code_request(event, store)
    await context.set_state(CodeStates.RECEIVING_CODE)


async def process_code_photo(event: MessageCreated, context: MemoryContext) -> None:
    """Обработка фото с кодом."""
    logger.debug("Received photo from user %s", event.message.sender.user_id)

    photo_attachment = _find_photo_attachment(event.message.body.attachments)
    if photo_attachment is None:
        await event.message.answer("📸 Я не вижу фото в сообщении. Попробуйте ещё раз.")
        return

    # Обрабатываем фото (распознавание, валидация)
    await process_final_code_photo(event, context, event.message.bot, photo_attachment)


async def process_office_choice(event: MessageCallback, context: MemoryContext) -> None:
    """Обработка выбора офиса."""
    await event.bot.send_callback(callback_id=event.callback.callback_id)
    
    office_id = event.callback.payload.replace("office_", "")
    logger.debug("Office choice: %s from user %s", office_id, event.callback.user.user_id)
    
    await context.update_data(office_id=office_id)
    data = await context.get_data()
    store = data.get("store")
    
    if store == "store_ozon":
        await event.message.answer(
            text="👤 <b>Введите ваше ФИО:</b>\n<i>Фамилия Имя Отчество</i>"
        )
        await context.set_state(CodeStates.WAITING_FOR_NAME)
    else:  # WB
        await event.message.answer(text=PHONE_PROMPT)
        await context.set_state(CodeStates.WAITING_FOR_PHONE)


async def process_name_input(event: MessageCreated, context: MemoryContext) -> None:
    """Обработка ввода ФИО."""
    name = event.message.body.text.strip()

    if len(name) < 1 or len(name) > 100:
        await event.message.answer(
            "❌ ФИО должно содержать от 2 до 100 символов.\n"
            "Пожалуйста, введите корректное ФИО:"
        )
        return

    await context.update_data(name=name)
    await event.message.answer(text=PHONE_PROMPT)
    await context.set_state(CodeStates.WAITING_FOR_PHONE)


async def process_phone_input(event: MessageCreated, context: MemoryContext) -> None:
    """Обработка ввода телефона и финальная отправка."""
    logger.debug("Phone input from user %s", event.message.sender.user_id)
    await process_final_order_data(event, context, event.message.bot)


async def back_to_store_choice(event: MessageCallback, context: MemoryContext) -> None:
    """Возврат к выбору магазина."""
    await event.bot.send_callback(callback_id=event.callback.callback_id)
    await context.set_state(CodeStates.CHOOSING_STORE)
    await event.message.answer(
        text=STORE_PROMPT,
        attachments=[get_store_selection_keyboard()],
    )


async def back_to_menu(event: MessageCallback, context: MemoryContext) -> None:
    """Возврат в главное меню."""
    await event.bot.send_callback(callback_id=event.callback.callback_id)
    await context.clear()
    await event.message.answer(
        text="Выберите действие:",
        attachments=[get_main_menu()],
    )


def register_send_code_handlers(dp: Dispatcher) -> None:
    """Регистрация всех хендлеров сценария отправки кода."""
    dp.message_callback(F.callback.payload == "send_code")(start_send_code)
    
    dp.message_callback(
        F.callback.payload.in_(["store_ozon", "store_wildberries"]),
        state=CodeStates.CHOOSING_STORE,
    )(process_store_choice)
    
    dp.message_created(
        F.message.body.attachments,
        state=CodeStates.RECEIVING_CODE,
    )(process_code_photo)
    
    dp.message_callback(
        F.callback.payload.startswith("office_"),
        state=CodeStates.CHOOSING_OFFICE,
    )(process_office_choice)
    
    dp.message_created(
        F.message.body.text,
        state=CodeStates.WAITING_FOR_NAME,
    )(process_name_input)
    
    dp.message_created(
        F.message.body.text,
        state=CodeStates.WAITING_FOR_PHONE,
    )(process_phone_input)
    
    dp.message_callback(
        F.callback.payload == "back_to_store_choice",
        state=CodeStates.CHOOSING_OFFICE,
    )(back_to_store_choice)
    
    dp.message_callback(F.callback.payload == "back_to_menu", state="*")(back_to_menu)
