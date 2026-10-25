"""Тесты регистрации хендлеров /start и /help."""
from unittest.mock import MagicMock

from src.handlers.start import register_start_handlers


def test_register_start_handlers_registers_help():
    """register_start_handlers регистрирует обработчики без ошибок."""
    dp = MagicMock()

    # Декораторы возвращают функцию, а регистрации возвращают None/Mock
    dp.bot_started.return_value = lambda f: f
    dp.message_created.return_value = lambda f: f
    dp.message_callback.return_value = lambda f: f

    # Не должно бросать исключение
    register_start_handlers(dp)

    # message_created должен быть вызван минимум дважды: /start и /help
    assert dp.message_created.call_count >= 2