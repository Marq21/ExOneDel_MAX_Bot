import asyncio
import cv2
import numpy as np
from pyzbar import pyzbar
import logging

logger = logging.getLogger(__name__)


# ============================================================
# СИНХРОННАЯ ФУНКЦИЯ (тяжёлая CPU-работа)
# ============================================================

def extract_code_from_image(image_bytes: bytes) -> str | None:
    """
    Извлекает текстовое содержимое штрих-кода (CODE128) или QR-кода из изображения.
    
    Поддерживаемые типы:
    - CODE128 (для OZON)
    - QRCODE (для Wildberries)
    
    Args:
        image_bytes (bytes): Байтовое представление изображения (например, PNG/JPG).
    
    Returns:
        str | None: Распознанный код в виде строки или None, если ничего не найдено.
    """
    try:
        # Декодируем байты в OpenCV-изображение (BGR)
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            logger.warning("Failed to decode image bytes into a valid OpenCV image.")
            return None
        
        # Распознаём все возможные коды на изображении
        decoded_objects = pyzbar.decode(image)
        
        for obj in decoded_objects:
            # Логируем для отладки
            logger.debug(f"Detected barcode type: {obj.type}, data: {obj.data}")
            
            # Поддерживаем только нужные типы
            if obj.type in ('CODE128', 'QRCODE'):
                try:
                    decoded_str = obj.data.decode('utf-8').strip()
                    if decoded_str:
                        logger.info(f"Successfully extracted code: {decoded_str} (type: {obj.type})")
                        return decoded_str
                except UnicodeDecodeError as e:
                    logger.warning(f"Failed to decode barcode data as UTF-8: {e}")
                    continue  # Пропускаем некорректные данные
        
        logger.info("No valid CODE128 or QRCODE found in the image.")
        return None
        
    except Exception as e:
        logger.exception("Unexpected error in extract_code_from_image")
        return None


# ============================================================
# АСИНХРОННАЯ ОБЁРТКА (используется в хендлерах)
# ============================================================

async def extract_code_from_image_async(image_bytes: bytes) -> str | None:
    """
    Асинхронная обёртка для распознавания кодов из изображения.
    
    Выносит CPU-bound работу (OpenCV + pyzbar) в отдельный поток через `asyncio.to_thread`,
    чтобы не блокировать event loop webhook-сервера.
    """
    if not image_bytes:
        return None
    return await asyncio.to_thread(extract_code_from_image, image_bytes)