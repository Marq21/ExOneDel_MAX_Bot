import pytest
from datetime import datetime

from src.utils.code_validator import (
    is_code_valid_for_store,
    get_store_description,
    get_example_image_path,
)
from src.utils.config_loader import ConfigLoader


@pytest.fixture(autouse=True)
def reset_config_cache(monkeypatch):
    """
    Изолирует глобальное состояние ConfigLoader перед каждым тестом:
    включает dev-режим и сбрасывает кэш конфига.
    monkeypatch автоматически откатит все подмены после теста,
    даже если тест упадёт с исключением.
    """
    monkeypatch.setenv("DEV", "true")
    monkeypatch.setattr(ConfigLoader, "_cache", {})
    monkeypatch.setattr(ConfigLoader, "_last_load", datetime.min)


# ─────────────────────────────────────────────
# Ozon: валидация
# ─────────────────────────────────────────────

def test_ozon_code_validation_valid():
    """Валидный Ozon-код (символ *) проходит валидацию."""
    assert is_code_valid_for_store("12345*6789", "store_ozon") is True
    assert is_code_valid_for_store("ABC*DEF", "store_ozon") is True


def test_ozon_code_validation_invalid():
    """Невалидный Ozon-код (без * или с _) не проходит валидацию."""
    assert is_code_valid_for_store("12345_6789", "store_ozon") is False
    assert is_code_valid_for_store("123456789", "store_ozon") is False


# ─────────────────────────────────────────────
# Wildberries: валидация
# ─────────────────────────────────────────────

def test_wb_code_validation_valid():
    """Валидный WB-код (символ _) проходит валидацию."""
    assert is_code_valid_for_store("12345_6789", "store_wildberries") is True
    assert is_code_valid_for_store("ABC_DEF", "store_wildberries") is True


def test_wb_code_validation_invalid():
    """Невалидный WB-код (без _ или с *) не проходит валидацию."""
    assert is_code_valid_for_store("12345*6789", "store_wildberries") is False
    assert is_code_valid_for_store("123456789", "store_wildberries") is False


# ─────────────────────────────────────────────
# Граничные случаи
# ─────────────────────────────────────────────

@pytest.mark.parametrize("store", ["store_ozon", "store_wildberries"])
def test_empty_code_is_invalid(store):
    """
    Пустая строка не должна проходить валидацию ни для одного магазина.
    Правило Ozon (*) и правило WB (_) требуют наличия хотя бы одного
    соответствующего символа, поэтому пустой код → False.
    """
    assert is_code_valid_for_store("", store) is False


@pytest.mark.parametrize("store", ["store_ozon", "store_wildberries"])
def test_whitespace_only_code_is_invalid(store):
    """
    Строка из одних пробелов не должна проходить валидацию:
    пробелы не являются ни *, ни _, поэтому False.
    """
    assert is_code_valid_for_store("   ", store) is False


def test_none_code_is_invalid():
    """
    None вместо строки не должен ломать валидатор:
    функция должна вернуть False, а не упасть с TypeError/AttributeError.
    """
    assert is_code_valid_for_store(None, "store_ozon") is False
    assert is_code_valid_for_store(None, "store_wildberries") is False


@pytest.mark.parametrize("store", ["STORE_OZON", "Store_Ozon", "store_OZON"])
def test_store_name_case_insensitive(store):
    """
    Название магазина не должно зависеть от регистра:
    'STORE_OZON', 'Store_Ozon', 'store_OZON' — тот же магазин.
    Валидный Ozon-код с * должен проходить.
    """
    assert is_code_valid_for_store("12345*6789", store) is True
    assert is_code_valid_for_store("12345_6789", store) is False


@pytest.mark.parametrize("store", ["STORE_WILDBERRIES", "Store_Wildberries", "store_WILDBERRIES"])
def test_wb_store_name_case_insensitive(store):
    """То же для WB: регистр названия магазина не важен."""
    assert is_code_valid_for_store("12345_6789", store) is True


# ─────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────

def test_get_store_description():
    """Описание магазинов содержит нужные ключевые слова."""
    ozon_desc = get_store_description("store_ozon")
    assert "штрих-код" in ozon_desc.lower() or "баркод" in ozon_desc.lower()

    wb_desc = get_store_description("store_wildberries")
    assert "qr" in wb_desc.lower()


def test_get_example_image_path_not_found(tmp_path, monkeypatch):
    """
    Если файла-примера нет, функция должна вернуть None.
    Подменяем директорию с изображениями на пустую tmp_path,
    чтобы тест не зависел от состояния реальной папки images/.
    """
    monkeypatch.setattr(
        "src.utils.code_validator.IMAGES_DIR",
        tmp_path,
        raising=False,
    )
    assert get_example_image_path("store_ozon") is None
    assert get_example_image_path("store_wildberries") is None


def test_unknown_store_validation():
    """
    Для неизвестного магазина правил нет — валидатор пропускает любой код.
    Это сознательное поведение: не блокировать сценарии, о которых
    валидатор ничего не знает.
    """
    assert is_code_valid_for_store("any_code", "unknown_store") is True
    assert is_code_valid_for_store("", "unknown_store") is True
    assert is_code_valid_for_store(None, "unknown_store") is True