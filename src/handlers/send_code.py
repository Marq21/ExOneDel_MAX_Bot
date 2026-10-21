"""Обработчики сценария отправки кода."""

import logging
from pathlib import Path

from maxapi import Dispatcher, Bot, F
from maxapi.types import MessageCallback, MessageCreated, PhotoAttachmentPayload

from src.states.code_states import CodeStates
from src.utils.keyboard_utils import get_store_selection_keyboard, get_office_keyboard, get_main_menu
from src.utils.code_validator import get_store_description
from src.services.code_photo_processing import process_final_code_photo
from src.services.code_processing import process_final_order_data

logger = logging.getLogger(__name__)


def register_send_code_handlers(dp: Dispatcher, bot: Bot):
    """Регистрация всех хендлеров сценария отправки кода."""
    
    # === Шаг 1: Кнопка "Отправить код" в главном меню ===
    @dp.message_callback(lambda cb: cb.payload == "send_code")
    async def start_send_code(event: MessageCallback, context):
        """Запуск сценария — выбор маркетплейса."""
        logger.debug(f"Callback 'send_code' from user {event.user.user_id}")
        
        await event.send_callback(notification="Выбор магазина...")
        await context.set_state(CodeStates.CHOOSING_STORE)
        
        await event.message.answer(
            text="🛍 <b>Выберите маркетплейс:</b>",
            attachments=[get_store_selection_keyboard()]
        )
    
    # === Шаг 2: Выбор магазина ===
    @dp.message_callback(
        F.payload.in_(["store_ozon", "store_wildberries"]),
        state=CodeStates.CHOOSING_STORE
    )
    async def process_store_choice(event: MessageCallback, context):
        """Обработка выбора магазина."""
        await event.send_callback()
        
        user_id = event.user.user_id
        store = event.payload
        
        logger.debug(f"Store choice: {store} from user {user_id}")
        
        await context.update_data(store=store)
        
        # Получаем описание и путь к примеру
        store_description = get_store_description(store)
        example_image = "ozon-ok.jpg" if store == "store_ozon" else "wb.jpg"
        photo_path = Path("static") / "images" / example_image
        
        caption = (
            f"📸 <b>Отправьте скриншот с кодом выдачи</b>\n"
            f"{store_description}\n"
            "<i>Убедитесь, что код хорошо виден на фото</i>"
        )
        
        # Отправляем пример фото, если есть
        if photo_path.exists():
            try:
                # В MAX нужно сначала загрузить фото, потом отправить
                # TODO: реализовать загрузку фото в MAX
                await event.message.answer(text=caption)
                logger.warning(f"Photo upload not implemented yet: {photo_path}")
            except Exception as e:
                logger.exception(f"Error sending example photo: {e}")
                await event.message.answer(text=caption)
        else:
            await event.message.answer(text=caption)
            logger.warning(f"Example photo not found: {photo_path}")
        
        await context.set_state(CodeStates.RECEIVING_CODE)
    
    # === Шаг 3: Приём фото с кодом ===
    @dp.message_created(
        F.message.body.attachments,
        state=CodeStates.RECEIVING_CODE
    )
    async def process_code_photo(event: MessageCreated, context):
        """Обработка фото с кодом."""
        logger.debug(f"Received photo from user {event.message.sender.user_id}")
        
        # Проверяем, что это фото
        attachments = event.message.body.attachments
        if not attachments:
            await event.message.answer("📸 Пожалуйста, отправьте фото с кодом.")
            return
        
        # Берём первое фото
        photo_attachment = None
        for attachment in attachments:
            if hasattr(attachment, 'payload') and isinstance(attachment.payload, PhotoAttachmentPayload):
                photo_attachment = attachment
                break
        
        if not photo_attachment:
            await event.message.answer("📸 Я не вижу фото в сообщении. Попробуйте ещё раз.")
            return
        
        # Обрабатываем фото (распознавание, валидация)
        await process_final_code_photo(event, context, bot, photo_attachment)
    
    # === Шаг 4: Выбор офиса ===
    @dp.message_callback(
        F.payload.startswith("office_"),
        state=CodeStates.CHOOSING_OFFICE
    )
    async def process_office_choice(event: MessageCallback, context):
        """Обработка выбора офиса."""
        await event.send_callback()
        
        user_id = event.user.user_id
        office_id = event.payload.replace("office_", "")
        
        logger.debug(f"Office choice: {office_id} from user {user_id}")
        
        await context.update_data(office_id=office_id)
        
        # Получаем данные из FSM
        data = await context.get_data()
        store = data.get("store")
        
        if store == "store_ozon":
            await event.message.answer(
                text="👤 <b>Введите ваше ФИО:</b>\n<i>Фамилия Имя Отчество</i>"
            )
            await context.set_state(CodeStates.WAITING_FOR_NAME)
        else:  # WB
            await event.message.answer(
                text="📱 <b>Введите ваш номер телефона:</b>\n<i>Формат: +7 XXX XXX-XX-XX</i>"
            )
            await context.set_state(CodeStates.WAITING_FOR_PHONE)
    
    # === Шаг 5: Ввод ФИО (только для OZON) ===
    @dp.message_created(
        F.message.body.text,
        state=CodeStates.WAITING_FOR_NAME
    )
    async def process_name_input(event: MessageCreated, context):
        """Обработка ввода ФИО."""
        name = event.message.body.text.strip()
        
        if len(name) < 2 or len(name) > 100:
            await event.message.answer(
                "❌ ФИО должно содержать от 2 до 100 символов.\n"
                "Пожалуйста, введите корректное ФИО:"
            )
            return
        
        await context.update_data(name=name)
        
        await event.message.answer(
            text="📱 <b>Введите ваш номер телефона:</b>\n<i>Формат: +7 XXX XXX-XX-XX</i>"
        )
        await context.set_state(CodeStates.WAITING_FOR_PHONE)
    
    # === Шаг 6: Ввод телефона ===
    @dp.message_created(
        F.message.body.text,
        state=CodeStates.WAITING_FOR_PHONE
    )
    async def process_phone_input(event: MessageCreated, context):
        """Обработка ввода телефона и финальная отправка."""
        logger.debug(f"Phone input from user {event.message.sender.user_id}")
        await process_final_order_data(event, context, bot)
    
    # === Глобальные callback'и ===
    @dp.message_callback(F.payload == "back_to_store_choice", state=CodeStates.CHOOSING_OFFICE)
    async def back_to_store_choice(event: MessageCallback, context):
        """Возврат к выбору магазина."""
        await event.send_callback()
        await context.set_state(CodeStates.CHOOSING_STORE)
        await event.message.answer(
            text="🛍 <b>Выберите маркетплейс:</b>",
            attachments=[get_store_selection_keyboard()]
        )
    
    @dp.message_callback(F.payload == "back_to_menu", state="*")
    async def back_to_menu(event: MessageCallback, context):
        """Возврат в главное меню."""
        await event.send_callback()
        await context.clear()
        await event.message.answer(
            text="Выберите действие:",
            attachments=[get_main_menu()]
        )