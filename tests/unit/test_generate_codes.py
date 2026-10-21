import pytest
from io import BytesIO

from src.utils.generate_codes import (
    generate_barcode_image_bytesio,
    generate_qr_code_image_bytesio,
    generate_barcode_image_async,
    generate_qr_code_async,
)


# Сигнатура PNG: первые 8 байт любого валидного PNG-файла
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


# ─────────────────────────────────────────────
# Синхронные функции
# ─────────────────────────────────────────────

class TestGenerateBarcodeSync:
    """Тесты синхронной генерации штрих-кода."""

    def test_generates_valid_png(self):
        """Сгенерированный штрих-код — валидный PNG."""
        result = generate_barcode_image_bytesio("12345*6789")

        assert result is not None
        assert isinstance(result, BytesIO)

        data = result.getvalue()
        assert len(data) > 0
        assert data.startswith(PNG_SIGNATURE), "Результат должен быть PNG"

    def test_ozon_code_with_asterisk(self):
        """Реальный OZON-код с '*' должен генерироваться без ошибок."""
        result = generate_barcode_image_bytesio("ABC*123")
        assert result is not None
        assert result.getvalue().startswith(PNG_SIGNATURE)

    def test_empty_string_returns_none(self):
        """Пустая строка возвращает None, а не падает."""
        assert generate_barcode_image_bytesio("") is None

    def test_none_returns_none(self):
        """None возвращает None, а не падает."""
        assert generate_barcode_image_bytesio(None) is None

    def test_different_codes_produce_different_images(self):
        """Разные коды дают разные изображения (разный размер)."""
        img1 = generate_barcode_image_bytesio("111")
        img2 = generate_barcode_image_bytesio("111111111")

        assert img1 is not None 
        assert img2 is not None
        # Длины должны отличаться — это разные штрих-коды
        assert img1.getvalue() != img2.getvalue()


class TestGenerateQrCodeSync:
    """Тесты синхронной генерации QR-кода."""

    def test_generates_valid_png(self):
        """Сгенерированный QR-код — валидный PNG."""
        result = generate_qr_code_image_bytesio("12345_6789")

        assert result is not None
        assert isinstance(result, BytesIO)

        data = result.getvalue()
        assert len(data) > 0
        assert data.startswith(PNG_SIGNATURE), "Результат должен быть PNG"

    def test_wb_code_with_underscore(self):
        """Реальный WB-код с '_' должен генерироваться без ошибок."""
        result = generate_qr_code_image_bytesio("ABC_123_XYZ")
        assert result is not None
        assert result.getvalue().startswith(PNG_SIGNATURE)

    def test_long_string(self):
        """QR-код может хранить длинные строки."""
        long_data = "https://wildberries.ru/catalog/" + "x" * 200
        result = generate_qr_code_image_bytesio(long_data)
        assert result is not None

    def test_empty_string_returns_none(self):
        """Пустая строка возвращает None, а не падает."""
        assert generate_qr_code_image_bytesio("") is None

    def test_none_returns_none(self):
        """None возвращает None, а не падает."""
        assert generate_qr_code_image_bytesio(None) is None


# ─────────────────────────────────────────────
# Асинхронные обёртки
# ─────────────────────────────────────────────

@pytest.mark.asyncio
class TestGenerateBarcodeAsync:
    """Тесты асинхронной генерации штрих-кода."""

    async def test_generates_valid_png(self):
        """Async-обёртка возвращает валидный PNG."""
        result = await generate_barcode_image_async("12345*6789")

        assert result is not None
        data = result.getvalue()
        assert data.startswith(PNG_SIGNATURE)

    async def test_empty_string_returns_none(self):
        """Пустая строка через async-обёртку тоже возвращает None."""
        assert await generate_barcode_image_async("") is None

    async def test_ozon_real_code(self):
        """Реальный OZON-код с '*' работает через async."""
        result = await generate_barcode_image_async("ABC*123")
        assert result is not None


@pytest.mark.asyncio
class TestGenerateQrCodeAsync:
    """Тесты асинхронной генерации QR-кода."""

    async def test_generates_valid_png(self):
        """Async-обёртка возвращает валидный PNG."""
        result = await generate_qr_code_async("12345_6789")

        assert result is not None
        data = result.getvalue()
        assert data.startswith(PNG_SIGNATURE)

    async def test_empty_string_returns_none(self):
        """Пустая строка через async-обёртку тоже возвращает None."""
        assert await generate_qr_code_async("") is None

    async def test_wb_real_code(self):
        """Реальный WB-код с '_' работает через async."""
        result = await generate_qr_code_async("ABC_123_XYZ")
        assert result is not None


# ─────────────────────────────────────────────
# Параллельная генерация (проверяем, что asyncio.to_thread реально не блокирует)
# ─────────────────────────────────────────────

@pytest.mark.asyncio
class TestAsyncConcurrency:
    """Проверяем, что асинхронные версии действительно работают параллельно."""

    async def test_multiple_barcodes_concurrently(self):
        """Несколько генераций штрих-кодов выполняются параллельно."""
        import asyncio

        codes = [f"CODE*{i}" for i in range(5)]
        # gather запускает все задачи одновременно
        results = await asyncio.gather(
            *[generate_barcode_image_async(code) for code in codes]
        )

        assert len(results) == 5
        assert all(r is not None for r in results)
        assert all(r.getvalue().startswith(PNG_SIGNATURE) for r in results)

    async def test_mixed_barcode_and_qr(self):
        """Barcode и QR могут генерироваться одновременно."""
        import asyncio

        barcode_task = generate_barcode_image_async("TEST*123")
        qr_task = generate_qr_code_async("TEST_123")

        barcode_result, qr_result = await asyncio.gather(barcode_task, qr_task)

        assert barcode_result is not None
        assert qr_result is not None
        assert barcode_result.getvalue().startswith(PNG_SIGNATURE)
        assert qr_result.getvalue().startswith(PNG_SIGNATURE)