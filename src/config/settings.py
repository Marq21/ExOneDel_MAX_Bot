from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки MAX-бота."""

    bot_token: str
    webhook_domain: str      # например: max.example.ru (БЕЗ https:// и без путей)
    webhook_secret: str      # только A-Z a-z 0-9 и дефис, 5..256 символов
    webhook_path: str = "/max/webhook"
    webhook_port: int = 8080
    environment: str = "dev"

    @property
    def webhook_url(self) -> str:
        """Полный URL, который регистрируем в MAX. Порт 443 не указывается."""
        return f"https://{self.webhook_domain}{self.webhook_path}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()