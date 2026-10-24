"""Тесты для финальной обработки заказа."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.code_processing import (
    validate_phone,
    get_target_chat,
    process_final_order_data,
)
from src.utils.config_loader import ConfigLoader


@pytest.fixture(autouse=True)
def reset_config_cache(monkeypatch):
    """Сбрасываем кэш ConfigLoader перед каждым тестом."""
    monkeypatch.setenv("DEV", "true")
    monkeypatch.setattr(ConfigLoader, "_cache", {})
    monkeypatch.setattr(ConfigLoader, "_last_load", datetime.min)


def _mock_chats_config(monkeypatch, chats_config):
    """Подменяет конфиг для тестов get_target_chat."""
    monkeypatch.setattr(
        "src.services.code_processing.ConfigLoader.get_config",
        lambda: {"chats_config": chats_config},
    )


# ─────────────────────────────────────────────
# validate_phone
# ─────────────────────────────────────────────

class TestValidatePhone:
    """Тесты валидации номера телефона."""

    def test_valid_phone_with_formatting(self):
        """Валидный телефон с форматированием."""
        is_valid, formatted = validate_phone("+7 (999) 123-45-67")
        assert is_valid is True
        assert formatted == "+7 (999) 123-45-67"

    def test_valid_phone_without_formatting(self):
        """Валидный телефон без форматирования."""
        is_valid, formatted = validate_phone("79991234567")
        assert is_valid is True
        assert formatted == "+7 (999) 123-45-67"

    def test_valid_phone_with_8_prefix(self):
        """Телефон с префиксом 8 автоматически преобразуется в +7 и проходит."""
        is_valid, formatted = validate_phone("89991234567")
        assert is_valid is True
        assert formatted == "+7 (999) 123-45-67"

    def test_too_short_phone(self):
        """Слишком короткий номер."""
        is_valid, formatted = validate_phone("7999123")
        assert is_valid is False
        assert formatted is None

    def test_too_long_phone(self):
        """Слишком длинный номер."""
        is_valid, formatted = validate_phone("799912345678901")
        assert is_valid is False
        assert formatted is None

    def test_empty_string(self):
        """Пустая строка."""
        is_valid, formatted = validate_phone("")
        assert is_valid is False
        assert formatted is None

    def test_only_letters(self):
        """Только буквы."""
        is_valid, formatted = validate_phone("abcdefghijk")
        assert is_valid is False
        assert formatted is None

    def test_phone_with_extra_text(self):
        """Телефон с лишним текстом вокруг."""
        is_valid, formatted = validate_phone("Мой номер: +7 999 123 45 67 спасибо")
        assert is_valid is True
        assert formatted == "+7 (999) 123-45-67"


# ─────────────────────────────────────────────
# get_target_chat
# ─────────────────────────────────────────────

class TestGetTargetChat:
    """Тесты определения целевого чата."""

    def test_wb_chat(self, monkeypatch):
        """Для WB используется ключ 'wb'."""
        chats = {
            "Ex.One": {
                "ozon_trolleibusnaya": "-100111",
                "ozon_rostselmash": "-100222",
                "wb": "-100333",
            }
        }
        _mock_chats_config(monkeypatch, chats)

        result = get_target_chat("store_wildberries", "Ex.One")
        assert result == "-100333"

    def test_ozon_chat_trolleibusnaya(self, monkeypatch):
        """Для OZON с ПВЗ 'trolleibusnaya' используется соответствующий ключ."""
        chats = {
            "Ex.One": {
                "ozon_trolleibusnaya": "-100111",
                "ozon_rostselmash": "-100222",
                "wb": "-100333",
            }
        }
        _mock_chats_config(monkeypatch, chats)

        result = get_target_chat("store_ozon", "Ex.One", ozon_pvz_id="trolleibusnaya")
        assert result == "-100111"

    def test_ozon_chat_rostselmash(self, monkeypatch):
        """Для OZON с ПВЗ 'rostselmash'."""
        chats = {
            "Ex.One": {
                "ozon_trolleibusnaya": "-100111",
                "ozon_rostselmash": "-100222",
                "wb": "-100333",
            }
        }
        _mock_chats_config(monkeypatch, chats)

        result = get_target_chat("store_ozon", "Ex.One", ozon_pvz_id="rostselmash")
        assert result == "-100222"

    def test_ozon_default_pvz(self, monkeypatch):
        """Для OZON без указания ПВЗ используется 'trolleibusnaya' по умолчанию."""
        chats = {
            "Ex.One": {
                "ozon_trolleibusnaya": "-100111",
                "wb": "-100333",
            }
        }
        _mock_chats_config(monkeypatch, chats)

        result = get_target_chat("store_ozon", "Ex.One", ozon_pvz_id=None)
        assert result == "-100111"

    def test_office_not_in_config(self, monkeypatch):
        """Офис отсутствует в конфиге — возвращает None."""
        chats = {
            "Ex.One": {"wb": "-100333"}
        }
        _mock_chats_config(monkeypatch, chats)

        result = get_target_chat("store_wildberries", "Ex.Nonexistent")
        assert result is None

    def test_store_key_not_in_office(self, monkeypatch):
        """Офис есть, но нужного ключа магазина нет."""
        chats = {
            "Ex.One": {
                "ozon_trolleibusnaya": "-100111",
            }
        }
        _mock_chats_config(monkeypatch, chats)

        result = get_target_chat("store_wildberries", "Ex.One")
        assert result is None

    def test_empty_chats_config(self, monkeypatch):
        """Пустой конфиг чатов."""
        _mock_chats_config(monkeypatch, {})

        result = get_target_chat("store_wildberries", "Ex.One")
        assert result is None


# ─────────────────────────────────────────────
# process_final_order_data — интеграционные тесты
# ─────────────────────────────────────────────

class TestProcessFinalOrderData:
    """Тесты основной функции финальной обработки."""

    def _make_event(self, phone_text: str):
        """Создаёт мокированный event с текстом сообщения."""
        event = MagicMock()
        event.message = MagicMock()
        event.message.body = MagicMock()
        event.message.body.text = phone_text
        event.message.answer = AsyncMock()
        return event

    def _make_context(self, fsm_data: dict):
        """Создаёт мокированный контекст с данными FSM."""
        context = AsyncMock()
        context.get_data = AsyncMock(return_value=fsm_data)
        context.clear = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_invalid_phone_shows_error(self, monkeypatch):
        """Невалидный телефон — показываем ошибку, не отправляем."""
        event = self._make_event("12345")
        context = self._make_context({"store": "store_ozon", "code": "A*1", "office_id": "Ex.One"})
        bot = AsyncMock()

        await process_final_order_data(event, context, bot)

        # Должно быть сообщение об ошибке
        event.message.answer.assert_called_once()
        call_text = event.message.answer.call_args[1].get("text", "") or event.message.answer.call_args[0][0]
        assert "Неверный формат" in call_text
        # Бот не должен отправлять в чат
        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_fsm_data_shows_error(self, monkeypatch):
        """Отсутствуют данные в FSM — показываем ошибку."""
        event = self._make_event("+79991234567")
        # Нет ключа "code"
        context = self._make_context({"store": "store_ozon", "office_id": "Ex.One"})
        bot = AsyncMock()

        await process_final_order_data(event, context, bot)

        event.message.answer.assert_called()
        # Должно быть сообщение об ошибке данных
        last_call_text = str(event.message.answer.call_args)
        assert "Ошибка данных" in last_call_text or "ошибка" in last_call_text.lower()
        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_wb_full_success_flow(self, monkeypatch):
        """Полный успешный сценарий для Wildberries."""
        monkeypatch.setattr(
            "src.services.code_processing.ConfigLoader.get_config",
            lambda: {
                "chats_config": {"Ex.One": {"wb": "-100333"}},
                "offices": [{"id": "Ex.One", "name": "Центр", "address": "ул. Университетская 39А"}],
            },
        )
        monkeypatch.setattr(
            "src.services.code_processing.get_office_by_id",
            lambda oid: {"id": "Ex.One", "name": "Центр", "address": "ул. Университетская 39А"} if oid == "Ex.One" else None,
        )

        event = self._make_event("+79991234567")
        context = self._make_context({
            "store": "store_wildberries",
            "code": "TEST_123_ABC",
            "office_id": "Ex.One",
        })
        
        # Мокируем бота с правильным форматом ответа
        bot = AsyncMock()
        bot.get_upload_url = AsyncMock(return_value=MagicMock(url="https://upload.example.com"))
        bot.upload_file_buffer = AsyncMock(return_value='{"photos": {"0": {"token": "test_token_abc123"}}}')
        bot.send_message = AsyncMock()
        bot.delete_message = AsyncMock()

        await process_final_order_data(event, context, bot)

        bot.get_upload_url.assert_called_once()
        bot.upload_file_buffer.assert_called_once()
        bot.send_message.assert_called_once()
        
        call_kwargs = bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == -100333
        assert "TEST_123_ABC" in call_kwargs["text"]
        assert "+7 (999) 123-45-67" in call_kwargs["text"]
        assert call_kwargs.get("attachments") is not None

        context.clear.assert_called_once()


    @pytest.mark.asyncio
    async def test_ozon_full_success_flow(self, monkeypatch):
        """Полный успешный сценарий для OZON (с ФИО)."""
        monkeypatch.setattr(
            "src.services.code_processing.ConfigLoader.get_config",
            lambda: {
                "chats_config": {"Ex.One": {"ozon_trolleibusnaya": "-100111", "wb": "-100333"}},
                "offices": [{"id": "Ex.One", "name": "Центр", "address": "ул. Университетская 39А"}],
            },
        )
        monkeypatch.setattr(
            "src.services.code_processing.get_office_by_id",
            lambda oid: {"id": "Ex.One", "name": "Центр", "address": "ул. Университетская 39А"} if oid == "Ex.One" else None,
        )

        event = self._make_event("+79991234567")
        context = self._make_context({
            "store": "store_ozon",
            "code": "TEST*123",
            "name": "Иванов Иван Иванович",
            "office_id": "Ex.One",
            "ozon_pvz_id": "trolleibusnaya",
        })
        
        bot = AsyncMock()
        bot.get_upload_url = AsyncMock(return_value=MagicMock(url="https://upload.example.com"))
        bot.upload_file_buffer = AsyncMock(return_value='{"photos": {"0": {"token": "test_token_xyz789"}}}')
        bot.send_message = AsyncMock()
        bot.delete_message = AsyncMock()

        await process_final_order_data(event, context, bot)

        bot.get_upload_url.assert_called_once()
        bot.upload_file_buffer.assert_called_once()
        bot.send_message.assert_called_once()
        
        call_kwargs = bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == -100111
        assert "TEST*123" in call_kwargs["text"]
        assert "Иванов Иван Иванович" in call_kwargs["text"]
        assert call_kwargs.get("attachments") is not None

        context.clear.assert_called_once()


        @pytest.mark.asyncio
        async def test_office_not_found_shows_error(self, monkeypatch):
            """Офис не найден — показываем ошибку."""
            monkeypatch.setattr(
                "src.services.code_processing.get_office_by_id",
                lambda oid: None,
            )

            event = self._make_event("+79991234567")
            context = self._make_context({
                "store": "store_ozon",
                "code": "TEST*123",
                "name": "Иванов",
                "office_id": "Ex.Nonexistent",
            })
            bot = AsyncMock()

            await process_final_order_data(event, context, bot)

            event.message.answer.assert_called()
            bot.send_message.assert_not_called()
            context.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_target_chat_not_found_shows_error(self, monkeypatch):
        """Целевой чат не найден — показываем ошибку."""
        monkeypatch.setattr(
            "src.services.code_processing.ConfigLoader.get_config",
            lambda: {"chats_config": {}},
        )
        monkeypatch.setattr(
            "src.services.code_processing.get_office_by_id",
            lambda oid: {"id": "Ex.One", "name": "Центр", "address": "адрес"},
        )

        event = self._make_event("+79991234567")
        context = self._make_context({
            "store": "store_wildberries",
            "code": "TEST_123",
            "office_id": "Ex.One",
        })
        bot = AsyncMock()

        await process_final_order_data(event, context, bot)

        event.message.answer.assert_called()
        bot.send_message.assert_not_called()
        context.clear.assert_called_once()