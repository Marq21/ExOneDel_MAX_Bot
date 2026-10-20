from datetime import datetime

import pytest

from src.utils.config_loader import ConfigLoader


@pytest.fixture(autouse=True)
def dev_config(monkeypatch):
    """
    Изолирует глобальное состояние для каждого теста модуля:
    включает dev-конфиг и сбрасывает кэш ConfigLoader.
    После теста monkeypatch автоматически вернёт всё как было.
    """
    monkeypatch.setenv("DEV", "true")
    monkeypatch.setattr(ConfigLoader, "_cache", {})
    monkeypatch.setattr(ConfigLoader, "_last_load", datetime.min)


def test_config_loader_loads_correctly():
    """Тест на корректную загрузку конфигурации."""
    config = ConfigLoader.get_config()
    
    # Проверяем наличие основных разделов
    assert "working_hours" in config
    assert "offices" in config
    assert "chats_config" in config
    assert "office_schedules" in config
    
    # Проверяем типы данных
    assert isinstance(config["offices"], list)
    assert isinstance(config["working_hours"], dict)
    assert len(config["offices"]) > 0
    
    # Проверяем структуру одного офиса
    office = config["offices"][0]
    assert "id" in office
    assert "name" in office
    assert "address" in office


def test_config_loader_caching():
    """Тест на корректную работу кэширования."""
    # Первый вызов загружает из файла
    config1 = ConfigLoader.get_config()
    
    # Второй вызов в пределах TTL возвращает кэш
    config2 = ConfigLoader.get_config()
    
    # Должны быть одним и тем же объектом (кэш работает)
    assert config1 is config2


def test_config_loader_get_method():
    """Тест метода get с default значением."""
    # Существующий ключ
    offices = ConfigLoader.get("offices")
    assert offices is not None
    assert isinstance(offices, list)
    
    # Несуществующий ключ с default
    missing = ConfigLoader.get("nonexistent_key", "default_value")
    assert missing == "default_value"