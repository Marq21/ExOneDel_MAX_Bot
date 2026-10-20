import os
import json
from pathlib import Path
from datetime import datetime, timedelta


class ConfigLoader:
    _cache = {}
    _last_load = datetime.min
    _ttl_seconds = 30

    @classmethod
    def _get_config_path(cls):
        dev_value = os.getenv("DEV", "NOT_SET")
        if dev_value.lower() == "true":
            return Path(__file__).parent.parent / "config" / "constants_dev.json"
        return Path(__file__).parent.parent / "config" / "constants.json"

    @classmethod
    def _load_from_file(cls):
        path = cls._get_config_path()
        if not path.exists():
            raise FileNotFoundError(f"Конфигурационный файл не найден: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def get_config(cls):
        now = datetime.now()
        if now - cls._last_load > timedelta(seconds=cls._ttl_seconds):
            cls._cache = cls._load_from_file()
            cls._last_load = now
        return cls._cache

    @classmethod
    def get(cls, key, default=None):
        return cls.get_config().get(key, default)