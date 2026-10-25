"""Кастомные исключения для MAX-бота."""


class SpamDetectedException(Exception):
    """Исключение, возникающее при обнаружении спама или флуда."""
    pass