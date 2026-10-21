import pytest
from datetime import datetime

from src.utils.config_loader import ConfigLoader
from src.utils import office_utils


@pytest.fixture(autouse=True)
def reset_config_cache(monkeypatch):
    """Сбрасываем кэш ConfigLoader перед каждым тестом."""
    monkeypatch.setenv("DEV", "true")
    monkeypatch.setattr(ConfigLoader, "_cache", {})
    monkeypatch.setattr(ConfigLoader, "_last_load", datetime.min)


def _mock_offices(monkeypatch, offices: list):
    """Подменяет конфиг так, чтобы get_available_offices возвращал заданный список."""
    monkeypatch.setattr(
        "src.utils.office_utils.ConfigLoader.get_config",
        lambda: {"offices": offices},
    )


class TestGetAvailableOffices:
    """Тесты получения списка офисов."""

    def test_returns_offices_from_config(self, monkeypatch):
        """Возвращает список офисов из конфига."""
        offices = [
            {"id": "Ex.One", "name": "Центр", "address": "ул. Университетская 39А"},
            {"id": "Ex.Two", "name": "Гора", "address": "проспект Восточный 100"},
        ]
        _mock_offices(monkeypatch, offices)

        result = office_utils.get_available_offices()
        assert result == offices
        assert len(result) == 2

    def test_returns_empty_list_when_no_offices(self, monkeypatch):
        """Если офисов нет, возвращает пустой список."""
        _mock_offices(monkeypatch, [])

        result = office_utils.get_available_offices()
        assert result == []

    def test_returns_empty_list_when_key_missing(self, monkeypatch):
        """Если ключ 'offices' отсутствует в конфиге, возвращает пустой список."""
        monkeypatch.setattr(
            "src.utils.office_utils.ConfigLoader.get_config",
            lambda: {},
        )

        result = office_utils.get_available_offices()
        assert result == []


class TestGetOfficeById:
    """Тесты получения офиса по ID."""

    def test_found_office(self, monkeypatch):
        """Находит офис по ID."""
        offices = [
            {"id": "Ex.One", "name": "Центр", "address": "ул. Университетская 39А"},
            {"id": "Ex.Two", "name": "Гора", "address": "проспект Восточный 100"},
        ]
        _mock_offices(monkeypatch, offices)

        office = office_utils.get_office_by_id("Ex.Two")
        assert office is not None
        assert office["name"] == "Гора"
        assert office["address"] == "проспект Восточный 100"

    def test_not_found_returns_none(self, monkeypatch):
        """Если офис не найден, возвращает None."""
        offices = [
            {"id": "Ex.One", "name": "Центр", "address": "ул. Университетская 39А"},
        ]
        _mock_offices(monkeypatch, offices)

        assert office_utils.get_office_by_id("Ex.Nonexistent") is None

    def test_empty_offices_returns_none(self, monkeypatch):
        """Если список офисов пуст, возвращает None."""
        _mock_offices(monkeypatch, [])
        assert office_utils.get_office_by_id("Ex.One") is None

    def test_office_with_hash_in_id(self, monkeypatch):
        """Офисы с '#' в ID находятся корректно."""
        offices = [
            {"id": "Ex.One#5", "name": "Ж/Д", "address": "проспект Восточный 214"},
        ]
        _mock_offices(monkeypatch, offices)

        office = office_utils.get_office_by_id("Ex.One#5")
        assert office is not None
        assert office["name"] == "Ж/Д"


class TestIsOfficeAvailable:
    """Тесты проверки доступности офиса."""

    def test_available_office(self, monkeypatch):
        """Существующий офис — доступен."""
        offices = [
            {"id": "Ex.One", "name": "Центр", "address": "ул. Университетская 39А"},
        ]
        _mock_offices(monkeypatch, offices)

        assert office_utils.is_office_available("Ex.One") is True

    def test_unavailable_office(self, monkeypatch):
        """Несуществующий офис — недоступен."""
        offices = [
            {"id": "Ex.One", "name": "Центр", "address": "ул. Университетская 39А"},
        ]
        _mock_offices(monkeypatch, offices)

        assert office_utils.is_office_available("Ex.Nonexistent") is False

    def test_empty_offices_all_unavailable(self, monkeypatch):
        """Если офисов нет, все недоступны."""
        _mock_offices(monkeypatch, [])
        assert office_utils.is_office_available("Ex.One") is False