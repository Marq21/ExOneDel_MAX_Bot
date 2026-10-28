"""Тесты кеша токенов примеров фото."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils import example_photo_cache as cache_module
from src.utils.example_photo_cache import (
    _build_attachment,
    _clear_cache,
    get_cached_example,
    preload_example_photos,
    refresh_example_photo,
)


@pytest.fixture(autouse=True)
def clean_cache():
    """Очищаем кеш до и после каждого теста."""
    _clear_cache()
    yield
    _clear_cache()


def _mock_bot(token: str = "test_token_abc"):
    """Создаёт мок бота, возвращающего заданный токен при загрузке."""
    bot = AsyncMock()
    bot.get_upload_url = AsyncMock(return_value=MagicMock(url="https://upload.example.com"))
    bot.upload_file_buffer = AsyncMock(
        return_value=json.dumps({"photos": {"0": {"token": token}}})
    )
    return bot


class TestBuildAttachment:
    def test_builds_valid_structure(self):
        """Вложение имеет правильную вложенную структуру."""
        attachment = _build_attachment("my_token")
        dumped = attachment.model_dump()
        assert dumped["type"] == "image"
        assert dumped["payload"]["payload"]["token"] == "my_token"


class TestGetCachedExample:
    def test_returns_none_when_cache_empty(self):
        """Пустой кеш возвращает None."""
        assert get_cached_example("store_ozon") is None

    def test_returns_attachment_after_preload(self):
        """После предзагрузки возвращает вложение."""
        cache_module._cache["store_ozon"] = _build_attachment("tok")
        assert get_cached_example("store_ozon") is not None


class TestPreloadExamplePhotos:
    @pytest.mark.asyncio
    async def test_preloads_both_stores(self):
        """Предзагрузка заполняет кеш для обоих магазинов."""
        bot = _mock_bot()

        with patch.object(
            cache_module, "get_example_image_path",
            return_value=MagicMock(name="ozon-ok.jpg", read=lambda: b"fake"),
        ), patch("builtins.open", MagicMock()):
            # Подменяем чтение файла
            with patch.object(cache_module, "open", create=True):
                pass

        # Проще: мокаем _upload_example_photo напрямую
        with patch.object(
            cache_module, "_upload_example_photo",
            new=AsyncMock(return_value=_build_attachment("tok")),
        ):
            await preload_example_photos(bot)

        assert get_cached_example("store_ozon") is not None
        assert get_cached_example("store_wildberries") is not None

    @pytest.mark.asyncio
    async def test_preload_failure_does_not_raise(self):
        """Ошибка предзагрузки не роняет бота."""
        bot = _mock_bot()

        with patch.object(
            cache_module, "_upload_example_photo",
            new=AsyncMock(return_value=None),
        ):
            # Не должно бросить исключение
            await preload_example_photos(bot)

        assert get_cached_example("store_ozon") is None


class TestRefreshExamplePhoto:
    @pytest.mark.asyncio
    async def test_refresh_updates_cache(self):
        """Перезагрузка обновляет кеш."""
        bot = _mock_bot(token="new_token")
        cache_module._cache["store_ozon"] = _build_attachment("old_token")

        with patch.object(
            cache_module, "_upload_example_photo",
            new=AsyncMock(return_value=_build_attachment("new_token")),
        ):
            result = await refresh_example_photo(bot, "store_ozon")

        assert result is not None
        updated = get_cached_example("store_ozon")
        assert updated.model_dump()["payload"]["payload"]["token"] == "new_token"

    @pytest.mark.asyncio
    async def test_refresh_failure_keeps_old_cache(self):
        """При ошибке перезагрузки старый кеш сохраняется."""
        bot = _mock_bot()
        old_attachment = _build_attachment("old_token")
        cache_module._cache["store_ozon"] = old_attachment

        with patch.object(
            cache_module, "_upload_example_photo",
            new=AsyncMock(return_value=None),
        ):
            result = await refresh_example_photo(bot, "store_ozon")

        assert result is None
        # Старый кеш не затёрт
        assert get_cached_example("store_ozon") is old_attachment