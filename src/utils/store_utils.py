"""Утилиты для работы с магазинами."""


def get_readable_store_name(store_key: str) -> str:
    """
    Преобразует техническое имя магазина в читаемое.
    
    Args:
        store_key (str): Техническое имя (например, "store_ozon", "store_wildberries").
    
    Returns:
        str: Читаемое название (например, "OZON", "Wildberries").
    """
    store_map = {
        "store_ozon": "OZON",
        "store_wildberries": "Wildberries"
    }
    return store_map.get(store_key, store_key)