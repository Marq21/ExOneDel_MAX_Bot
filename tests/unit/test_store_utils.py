from src.utils.store_utils import get_readable_store_name


class TestGetReadableStoreName:
    """Тесты преобразования технического имени магазина в читаемое."""

    def test_ozon_key(self):
        """store_ozon преобразуется в OZON."""
        assert get_readable_store_name("store_ozon") == "OZON"

    def test_wildberries_key(self):
        """store_wildberries преобразуется в Wildberries."""
        assert get_readable_store_name("store_wildberries") == "Wildberries"

    def test_unknown_store_returns_as_is(self):
        """Неизвестный магазин возвращается как есть."""
        assert get_readable_store_name("store_lamoda") == "store_lamoda"
        assert get_readable_store_name("some_random_key") == "some_random_key"

    def test_empty_string_returns_as_is(self):
        """Пустая строка возвращается как есть, не падает."""
        assert get_readable_store_name("") == ""

    def test_case_sensitive(self):
        """Функция чувствительна к регистру (ключи в нижнем регистре)."""
        # Если передать ключ в другом регистре, он не найдётся в маппинге
        # и вернётся как есть
        assert get_readable_store_name("STORE_OZON") == "STORE_OZON"
        assert get_readable_store_name("Store_Ozon") == "Store_Ozon"