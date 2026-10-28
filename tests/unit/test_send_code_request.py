"""Тесты отправки примера фото в _send_code_request."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.handlers import send_code
from src.handlers.send_code import _send_code_request, get_schedule_message
from src.utils import example_photo_cache as cache_module


@pytest.fixture(autouse=True)
def clean_example_cache():
    cache_module._clear_cache()
    yield
    cache_module._clear_cache()


def _make_event():
    """Создаёт мокированный MessageCallback."""
    event = MagicMock()
    event.message = MagicMock()
    event.message.answer = AsyncMock()
    return event


@pytest.mark.asyncio
async def test_sends_photo_when_file_exists(tmp_path):
    """Если файл-пример существует, отправляется фото с текстом."""
    # Создаём временный файл
    fake_image = tmp_path / "ozon-ok.jpg"
    fake_image.write_bytes(b"\x89PNG\r\n\x1a\nfake_image_data")

    event = _make_event()

    with patch(
        "src.handlers.send_code.get_example_image_path",
        return_value=fake_image,
    ), patch(
        "src.handlers.send_code.get_store_description",
        return_value="штрих-код (баркод)",
    ):
        await _send_code_request(event, "store_ozon")

    # Сообщение должно быть отправлено один раз
    event.message.answer.assert_called_once()
    call_kwargs = event.message.answer.call_args[1]

    # Должен быть текст
    assert "Отправьте скриншот" in call_kwargs["text"]
    # Должно быть вложение
    assert call_kwargs.get("attachments") is not None
    assert len(call_kwargs["attachments"]) == 1


@pytest.mark.asyncio
async def test_sends_text_only_when_file_missing():
    """Если файла нет, отправляется только текст."""
    event = _make_event()

    with patch(
        "src.handlers.send_code.get_example_image_path",
        return_value=None,
    ), patch(
        "src.handlers.send_code.get_store_description",
        return_value="QR-код",
    ):
        await _send_code_request(event, "store_wildberries")

    event.message.answer.assert_called_once()
    call_kwargs = event.message.answer.call_args[1]
    assert "Отправьте скриншот" in call_kwargs["text"]
    # Вложений быть не должно
    assert call_kwargs.get("attachments") is None


@pytest.mark.asyncio
async def test_fallback_to_text_on_read_error(tmp_path):
    """При ошибке чтения файла отправляется только текст."""
    event = _make_event()
    nonexistent_path = tmp_path / "does_not_exist.jpg"

    with patch(
        "src.handlers.send_code.get_example_image_path",
        return_value=nonexistent_path,
    ), patch(
        "src.handlers.send_code.get_store_description",
        return_value="штрих-код (баркод)",
    ):
        # Не должно упасть, должен сработать fallback
        await _send_code_request(event, "store_ozon")

    event.message.answer.assert_called_once()
    call_kwargs = event.message.answer.call_args[1]
    assert "Отправьте скриншот" in call_kwargs["text"]
    assert call_kwargs.get("attachments") is None


@pytest.mark.asyncio
async def test_uses_cached_attachment_when_available():
    """При наличии кеша файл с диска не читается."""
    event = _make_event()
    cached_attachment = MagicMock(name="cached_attachment")

    with patch(
        "src.handlers.send_code.get_cached_example",
        return_value=cached_attachment,
    ), patch(
        "src.handlers.send_code.get_store_description",
        return_value="штрих-код",
    ), patch(
        "src.handlers.send_code.aiofiles.open",
    ) as mock_open:
        await _send_code_request(event, "store_ozon")

    # Отправка произошла с кешированным вложением
    event.message.answer.assert_called_once()
    call_kwargs = event.message.answer.call_args[1]
    assert call_kwargs["attachments"] == [cached_attachment]
    # Файл с диска НЕ читался
    mock_open.assert_not_called()

# ─────────────────────────────────────────────
# get_schedule_message
# ─────────────────────────────────────────────

class TestGetScheduleMessage:
    """Сообщение о закрытом приёме кодов."""

    def test_contains_title_and_schedule(self):
        """Сообщение содержит заголовок и расписание."""
        message = get_schedule_message()

        assert message.startswith(send_code.SCHEDULE_CLOSED_TITLE)
        assert "Расписание приёма кодов" in message

    def test_no_stray_backslash_or_extra_indent(self):
        """В тексте нет лишних обратных слэшей и отступов от переноса строки."""
        message = get_schedule_message()
        schedule_part = message.split("\n", 1)[1]
        backslash = chr(92)

        assert backslash not in message
        assert schedule_part == schedule_part.lstrip()

    def test_schedule_is_read_on_each_call(self, monkeypatch):
        """Расписание не «замораживается» на импорте — читается при каждом вызове."""
        monkeypatch.setattr(
            send_code, "format_working_hours_message", lambda: "ПЕРВОЕ"
        )
        assert get_schedule_message().endswith("ПЕРВОЕ")

        monkeypatch.setattr(
            send_code, "format_working_hours_message", lambda: "ВТОРОЕ"
        )
        assert get_schedule_message().endswith("ВТОРОЕ")
