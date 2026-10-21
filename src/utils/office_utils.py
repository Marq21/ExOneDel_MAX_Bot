"""Утилиты для работы с офисами."""

import logging
from typing import Optional

from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


def get_available_offices() -> list[dict]:
    """
    Возвращает список офисов, доступных для выбора.
    Сейчас офис считается доступным, если он просто есть в конфиге.
    Если позже мы захотим вернуть флаг active, то фильтрация будет здесь:
    return [
        office
        for office in config.get("offices", [])
        if office.get("active", True)
    ]
    """
    config = ConfigLoader.get_config()
    return config.get("offices", [])


def get_office_by_id(office_id: str) -> Optional[dict]:
    """
    Возвращает офис по ID или None, если офис не найден.
    """
    return next(
        (
            office
            for office in get_available_offices()
            if office.get("id") == office_id
        ),
        None
    )


def is_office_available(office_id: str) -> bool:
    """
    Проверяет, доступен ли офис для выбора.
    """
    return get_office_by_id(office_id) is not None