import asyncio
import logging
from io import BytesIO
import barcode
from barcode.writer import ImageWriter
import qrcode

logger = logging.getLogger(__name__)


# ============================================================
# СИНХРОННЫЕ ФУНКЦИИ (тяжёлая CPU-работа)
# ============================================================

def generate_barcode_image_bytesio(barcode_string: str | None) -> BytesIO | None:
    """
    Генерирует изображение штрих-кода (CODE128) из строки и возвращает его как BytesIO.

    Args:
        barcode_string (str): Строка, представляющая штрих-код (например, "12345*6789").

    Returns:
        BytesIO | None: Байтовый поток с изображением PNG или None в случае ошибки.
    """
    if not barcode_string:
        logger.error("Barcode string is empty or None.")
        return None

    try:
        # Используем Code128 напрямую — он поддерживает широкий набор символов,
        # включая '*' (который используется в OZON-кодах)
        barcode_obj = barcode.Code128(barcode_string, writer=ImageWriter())
        barcode_image = barcode_obj.render()  # Получаем PIL Image

        barcode_bytes = BytesIO()
        barcode_image.save(barcode_bytes, format='PNG')
        barcode_bytes.seek(0)

        logger.debug("Generated barcode image in memory for code: %s", {barcode_string})
        return barcode_bytes
    except (ValueError, OSError):
        logger.exception("Barcode generation failed for %r", barcode_string)
        return None
    except Exception:
        logger.exception("Unexpected error generating barcode for %r", barcode_string)
        return None


def generate_qr_code_image_bytesio(qr_data: str | None) -> BytesIO | None:
    """
    Генерирует изображение QR-кода из строки и возвращает его как BytesIO.

    Args:
        qr_data (str): Данные для QR-кода (например, "12345_6789").

    Returns:
        BytesIO | None: Байтовый поток с изображением PNG или None в случае ошибки.
    """
    if not qr_data:
        logger.error("QR data string is empty or None.")
        return None

    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        logger.debug("Generated QR code image in memory for data: %s", qr_data)
        return buffer
    except Exception:
        logger.exception("Error generating QR code image for data %r", qr_data)
        return None


# ============================================================
# АСИНХРОННЫЕ ОБЁРТКИ (используются в хендлерах)
# ============================================================

async def generate_barcode_image_async(barcode_string: str | None) -> BytesIO | None:
    """
    Асинхронная обёртка для генерации штрих-кода.

    Выносит CPU-bound работу в отдельный поток через `asyncio.to_thread`,
    чтобы не блокировать event loop webhook-сервера.
    """
    if not barcode_string:
        return None
    return await asyncio.to_thread(generate_barcode_image_bytesio, barcode_string)


async def generate_qr_code_async(qr_data: str | None) -> BytesIO | None:
    """
    Асинхронная обёртка для генерации QR-кода.

    Выносит CPU-bound работу в отдельный поток через `asyncio.to_thread`,
    чтобы не блокировать event loop webhook-сервера.
    """
    if not qr_data:
        return None
    return await asyncio.to_thread(generate_qr_code_image_bytesio, qr_data)