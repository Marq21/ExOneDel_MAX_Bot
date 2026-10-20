import pytest
from src.utils.code_validator import (
    validate_ean13,
    validate_barcode,
    validate_phone,
    # добавьте другие функции из вашего модуля
)


class TestEAN13Validation:
    """Тесты для валидации EAN-13"""

    def test_valid_ean13(self):
        """Валидный EAN-13 должен возвращать True"""
        assert validate_ean13("4607008155441") is True

    def test_invalid_ean13_checksum(self):
        """EAN-13 с неверной контрольной суммой должен возвращать False"""
        assert validate_ean13("4607008155442") is False

    def test_invalid_ean13_length(self):
        """EAN-13 неправильной длины должен возвращать False"""
        assert validate_ean13("460700815544") is False
        assert validate_ean13("46070081554412") is False

    def test_invalid_ean13_non_numeric(self):
        """EAN-13 с нечисловыми символами должен возвращать False"""
        assert validate_ean13("460700815544A") is False
        assert validate_ean13("460700815544!") is False


class TestBarcodeValidation:
    """Тесты для валидации штрих-кодов"""

    def test_valid_barcode(self):
        """Валидный штрих-код должен возвращать True"""
        # Замените на реальные тестовые данные из вашего бота
        assert validate_barcode("123456789012") is True

    def test_invalid_barcode(self):
        """Невалидный штрих-код должен возвращать False"""
        assert validate_barcode("") is False
        assert validate_barcode("abc") is False


class TestPhoneValidation:
    """Тесты для валидации телефонов"""

    def test_valid_russian_phone(self):
        """Валидный российский телефон должен возвращать True"""
        assert validate_phone("+79991234567") is True
        assert validate_phone("89991234567") is True
        assert validate_phone("79991234567") is True

    def test_invalid_phone(self):
        """Невалидный телефон должен возвращать False"""
        assert validate_phone("123456") is False
        assert validate_phone("abc1234567") is False
        assert validate_phone("") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])