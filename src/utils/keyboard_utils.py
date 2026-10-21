"""Утилиты для создания клавиатур в MAX."""

from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.types import CallbackButton

from src.utils.config_loader import ConfigLoader
from src.utils.office_utils import get_available_offices


def get_main_menu():
    """Главное меню с кнопками."""
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="📤 Отправить код", payload="send_code"),
        CallbackButton(text="🔄 Перезапустить", payload="restart")
    )
    return builder.as_markup()


def get_store_selection_keyboard():
    """Клавиатура выбора магазина (OZON/WB)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="📦 OZON", payload="store_ozon"),
        CallbackButton(text="📦 Wildberries", payload="store_wildberries")
    )
    return builder.as_markup()


def get_office_keyboard():
    """Клавиатура выбора офиса."""
    builder = InlineKeyboardBuilder()
    
    offices = get_available_offices()
    for office in offices:
        # Сокращаем адрес для читаемости
        full_address = office['address']
        short_address = full_address.split(',')[0] if ',' in full_address else full_address
        button_text = f"📍 {office['name']} ({short_address})"
        
        builder.row(
            CallbackButton(text=button_text, payload=f"office_{office['id']}")
        )
    
    # Кнопка назад
    builder.row(
        CallbackButton(text="◀️ Назад к магазину", payload="back_to_store_choice"),
        CallbackButton(text="🏠 В меню", payload="back_to_menu")
    )
    
    return builder.as_markup()


def get_back_to_menu_keyboard():
    """Простая клавиатура с кнопкой 'В меню'."""
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="🏠 В меню", payload="back_to_menu")
    )
    return builder.as_markup()