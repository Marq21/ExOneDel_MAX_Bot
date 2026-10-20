import pytest
import os
from src.utils.code_validator import (
    is_code_valid_for_store,
    get_store_description,
    get_example_image_path
)
from src.utils.config_loader import ConfigLoader


@pytest.fixture(autouse=True)
def reset_config_cache():
    """Сбрасываем кэш ConfigLoader перед каждым тестом."""
    os.environ["DEV"] = "true"
    ConfigLoader._cache = {}
    from datetime import datetime
    ConfigLoader._last_load = datetime.min
    yield
    ConfigLoader._cache = {}


def test_ozon_code_validation_valid():
    """Тест: валидный OZON код (символ *) должен пройти."""
    assert is_code_valid_for_store("12345*6789", "store_ozon") is True
    assert is_code_valid_for_store("ABC*DEF", "store_ozon") is True


def test_ozon_code_validation_invalid():
    """Тест: невалидный OZON код (без * или с _) должен не пройти."""
    assert is_code_valid_for_store("12345_6789", "store_ozon") is False
    assert is_code_valid_for_store("123456789", "store_ozon") is False


def test_wb_code_validation_valid():
    """Тест: валидный WB код (символ _) должен пройти."""
    assert is_code_valid_for_store("12345_6789", "store_wildberries") is True
    assert is_code_valid_for_store("ABC_DEF", "store_wildberries") is True


def test_wb_code_validation_invalid():
    """Тест: невалидный WB код (без _ или с *) должен не пройти."""
    assert is_code_valid_for_store("12345*6789", "store_wildberries") is False
    assert is_code_valid_for_store("123456789", "store_wildberries") is False


def test_get_store_description():
    """Тест: получение описания магазина."""
    ozon_desc = get_store_description("store_ozon")
    assert "штрих-код" in ozon_desc.lower() or "баркод" in ozon_desc.lower()
    
    wb_desc = get_store_description("store_wildberries")
    assert "qr" in wb_desc.lower()


def test_get_example_image_path_not_found():
    """Тест: путь к примеру изображения (файлы не существуют)."""
    # Файлы ozon-ok.jpg и wb.jpg не существуют, должен вернуть None
    path = get_example_image_path("store_ozon")
    assert path is None


def test_unknown_store_validation():
    """Тест: неизвестный магазин должен пропускать валидацию."""
    # Если правила для магазина нет, валидация должна вернуть True
    result = is_code_valid_for_store("any_code", "unknown_store")
    assert result is True