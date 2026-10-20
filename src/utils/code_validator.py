import re
import logging
from pathlib import Path
from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

def is_code_valid_for_store(code: str, store: str) -> bool:
    """
    Проверяет, соответствует ли код формату выбранного магазина.
    
    Args:
        code (str): Распознанный код.
        store (str): Магазин ('store_ozon' или 'store_wildberries').
    
    Returns:
        bool: True, если код валиден для магазина.
    """
    config = ConfigLoader.get_config()
    rules = config.get("code_validation_rules", {})
    store_rule = rules.get(store)
    
    if not store_rule:
        logger.warning(f"No validation rule found for store: {store}. Skipping validation.")
        return True # Если правило не задано, пропускаем проверку
    
    pattern = store_rule.get("regex_pattern")
    if not pattern:
        logger.warning(f"No regex_pattern found for store: {store}. Skipping validation.")
        return True
    
    try:
        is_valid = bool(re.search(pattern, code))
        logger.debug(f"Code validation for store '{store}': code='{code}', pattern='{pattern}', result={is_valid}")
        return is_valid
    except re.error as e:
        logger.error(f"Invalid regex pattern for store '{store}': {e}")
        return True # В случае ошибки в регулярке тоже пропускаем

def get_store_description(store: str) -> str:
    """
    Возвращает описание кода для выбранного магазина из конфига.
    
    Args:
        store (str): Магазин ('store_ozon' или 'store_wildberries').
    
    Returns:
        str: Описание кода.
    """
    config = ConfigLoader.get_config()
    rules = config.get("code_validation_rules", {})
    store_rule = rules.get(store, {})
    return store_rule.get("description", "код выдачи")

def get_example_image_path(store: str) -> Path | None:
    """
    Возвращает путь к примеру изображения для выбранного магазина.
    
    Args:
        store (str): Магазин ('store_ozon' или 'store_wildberries').
    
    Returns:
        Path | None: Путь к файлу изображения или None.
    """
    config = ConfigLoader.get_config()
    rules = config.get("code_validation_rules", {})
    store_rule = rules.get(store, {})
    image_filename = store_rule.get("example_image")
    
    if not image_filename:
        logger.warning(f"No example_image found for store: {store}")
        return None
    
    image_path = Path("static") / "images" / image_filename
    if not image_path.exists():
        logger.warning(f"Example image not found at path: {image_path}")
        return None
        
    return image_path