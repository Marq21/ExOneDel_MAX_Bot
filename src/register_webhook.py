# register_webhook.py  (в корне проекта)
import asyncio, sys
sys.path.insert(0, "src")
from maxapi import Bot
from config.settings import settings
from webhook_setup import register_webhook

async def main():
    bot = Bot(token=settings.bot_token)
    await register_webhook(bot)

asyncio.run(main())