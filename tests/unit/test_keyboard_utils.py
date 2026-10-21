"""Тесты для клавиатур MAX-бота."""
from datetime import datetime

import pytest

from src.utils.config_loader import ConfigLoader
from src.utils.keyboard_utils import (
    get_main_menu,
    get_store_selection_keyboard,
    get_office_keyboard,
    get_back_to_menu_keyboard,
)


@pytest.fixture(autouse=True)
def reset_config_cache(monkeypatch):
    """Сбрасываем кэш ConfigLoader перед каждым тестом."""
    monkeypatch.setenv("DEV", "true")
    monkeypatch.setattr(ConfigLoader, "_cache", {})
    monkeypatch.setattr(ConfigLoader, "_last_load", datetime.min)


def _get_all_buttons(markup):
    """Извлекает все кнопки из разметки в плоский список."""
    return [btn for row in markup.payload.buttons for btn in row]


def _get_button_texts(markup):
    """Возвращает список текстов всех кнопок."""
    return [btn.text for btn in _get_all_buttons(markup)]


def _get_button_payloads(markup):
    """Возвращает список payload'ов всех кнопок."""
    return [btn.payload for btn in _get_all_buttons(markup)]


# ─────────────────────────────────────────────
# Главное меню
# ─────────────────────────────────────────────

class TestGetMainMenu:
    """Тесты главного меню."""

    def test_contains_send_code_button(self):
        """В главном меню есть кнопка 'Отправить код'."""
        markup = get_main_menu()
        payloads = _get_button_payloads(markup)
        assert "send_code" in payloads

    def test_contains_restart_button(self):
        """В главном меню есть кнопка 'Перезапустить'."""
        markup = get_main_menu()
        payloads = _get_button_payloads(markup)
        assert "restart" in payloads

    def test_button_texts_are_readable(self):
        """Тексты кнопок содержат эмодзи и понятные подписи."""
        markup = get_main_menu()
        texts = _get_button_texts(markup)
        assert any("Отправить код" in t for t in texts)
        assert any("Перезапустить" in t for t in texts)

    def test_exactly_two_buttons(self):
        """В главном меню ровно две кнопки."""
        markup = get_main_menu()
        assert len(_get_all_buttons(markup)) == 2


# ─────────────────────────────────────────────
# Выбор магазина
# ─────────────────────────────────────────────

class TestGetStoreSelectionKeyboard:
    """Тесты клавиатуры выбора магазина."""

    def test_contains_ozon_and_wb(self):
        """Есть кнопки для обоих магазинов."""
        markup = get_store_selection_keyboard()
        payloads = _get_button_payloads(markup)
        assert "store_ozon" in payloads
        assert "store_wildberries" in payloads

    def test_exactly_two_buttons(self):
        """Ровно две кнопки — по одной на магазин."""
        markup = get_store_selection_keyboard()
        assert len(_get_all_buttons(markup)) == 2

    def test_button_texts(self):
        """Тексты кнопок содержат названия магазинов."""
        markup = get_store_selection_keyboard()
        texts = _get_button_texts(markup)
        assert any("OZON" in t for t in texts)
        assert any("Wildberries" in t for t in texts)

    def test_payloads_match_config_keys(self):
        """Payload'ы совпадают с ключами в code_validation_rules."""
        markup = get_store_selection_keyboard()
        payloads = set(_get_button_payloads(markup))
        expected = {"store_ozon", "store_wildberries"}
        assert payloads == expected


# ─────────────────────────────────────────────
# Выбор офиса
# ─────────────────────────────────────────────

class TestGetOfficeKeyboard:
    """Тесты клавиатуры выбора офиса."""

    def test_office_buttons_match_config(self, monkeypatch):
        """Кнопки офисов соответствуют офисам из конфига."""
        offices = [
            {"id": "Ex.One", "name": "Центр", "address": "ул. Университетская 39А, рядом"},
            {"id": "Ex.Two", "name": "Гора", "address": "проспект Восточный 100, двор"},
        ]
        monkeypatch.setattr(
            "src.utils.keyboard_utils.ConfigLoader.get_config",
            lambda: {"offices": offices},
        )

        markup = get_office_keyboard()
        payloads = _get_button_payloads(markup)

        # Кнопки офисов с префиксом office_
        office_payloads = [p for p in payloads if p.startswith("office_")]
        assert "office_Ex.One" in office_payloads
        assert "office_Ex.Two" in office_payloads

    def test_office_button_text_contains_name_and_address(self, monkeypatch):
        """Текст кнопки офиса содержит название и сокращённый адрес."""
        offices = [
            {"id": "Ex.One", "name": "Центр", "address": "ул. Университетская 39А, рядом с парком"},
        ]
        monkeypatch.setattr(
            "src.utils.keyboard_utils.ConfigLoader.get_config",
            lambda: {"offices": offices},
        )

        markup = get_office_keyboard()
        texts = _get_button_texts(markup)

        # Ищем кнопку офиса (не навигационные)
        office_texts = [t for t in texts if "Центр" in t]
        assert len(office_texts) == 1
        # Адрес обрезается до первой запятой
        assert "ул. Университетская 39А" in office_texts[0]
        assert "рядом с парком" not in office_texts[0]

    def test_has_back_and_menu_buttons(self, monkeypatch):
        """Есть кнопки навигации: назад и в меню."""
        monkeypatch.setattr(
            "src.utils.keyboard_utils.ConfigLoader.get_config",
            lambda: {"offices": []},
        )

        markup = get_office_keyboard()
        payloads = _get_button_payloads(markup)

        assert "back_to_store_choice" in payloads
        assert "back_to_menu" in payloads

    def test_office_with_hash_in_id(self, monkeypatch):
        """Офисы с '#' в ID генерируют корректные payload'ы."""
        offices = [
            {"id": "Ex.One#5", "name": "Ж/Д", "address": "проспект Восточный 214"},
        ]
        monkeypatch.setattr(
            "src.utils.keyboard_utils.ConfigLoader.get_config",
            lambda: {"offices": offices},
        )

        markup = get_office_keyboard()
        payloads = _get_button_payloads(markup)
        assert "office_Ex.One#5" in payloads

    def test_empty_offices_only_nav_buttons(self, monkeypatch):
        """Если офисов нет, остаются только кнопки навигации."""
        monkeypatch.setattr(
            "src.utils.keyboard_utils.ConfigLoader.get_config",
            lambda: {"offices": []},
        )

        markup = get_office_keyboard()
        payloads = _get_button_payloads(markup)

        office_payloads = [p for p in payloads if p.startswith("office_")]
        assert office_payloads == []
        assert len(payloads) == 2  # только back_to_store_choice и back_to_menu


# ─────────────────────────────────────────────
# Кнопка "В меню"
# ─────────────────────────────────────────────

class TestGetBackToMenuKeyboard:
    """Тесты кнопки возврата в меню."""

    def test_single_button(self):
        """Ровно одна кнопка."""
        markup = get_back_to_menu_keyboard()
        assert len(_get_all_buttons(markup)) == 1

    def test_button_payload(self):
        """Payload кнопки — back_to_menu."""
        markup = get_back_to_menu_keyboard()
        payloads = _get_button_payloads(markup)
        assert payloads == ["back_to_menu"]

    def test_button_text(self):
        """Текст кнопки содержит 'В меню'."""
        markup = get_back_to_menu_keyboard()
        texts = _get_button_texts(markup)
        assert any("В меню" in t for t in texts)