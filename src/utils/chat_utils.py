"""Утилиты для проверки типа чата."""
from maxapi.enums.chat_type import ChatType


def is_private_chat(message) -> bool:
    """
    Проверяет, является ли сообщение личным диалогом (1-на-1).
    В рабочих чатах доставки бот не должен реагировать на команды.
    """
    try:
        return message.recipient.chat_type == ChatType.DIALOG
    except (AttributeError, TypeError):
        return False