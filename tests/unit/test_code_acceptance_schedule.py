"""Тесты проверки расписания приёма кодов."""
from datetime import datetime, timedelta

import pytest

from src.utils import code_acceptance_schedule as schedule
from src.utils.code_acceptance_schedule import (
    DAY_NAMES,
    WEEKDAY_MAP,
    format_working_hours_message,
    is_session_allowed_to_proceed,
)

WORKING_HOURS = {
    "monday": 16,
    "tuesday": 16,
    "wednesday": 16,
    "thursday": 16,
    "friday": 16,
    "saturday": 16,
}

RU_WEEKDAYS = (
    "Понедельник", "Вторник", "Среда", "Четверг",
    "Пятница", "Суббота", "Воскресенье",
)


def _mock_config(monkeypatch, working_hours):
    """Подменяет конфиг на заданные рабочие часы."""
    monkeypatch.setattr(
        schedule.ConfigLoader,
        "get_config",
        lambda: {"working_hours": working_hours},
    )


def _mock_now(monkeypatch, weekday: int, hour: int, minute: int = 0):
    """
    Подменяет 'сейчас' на заданный день недели и время.
    Заодно имитирует русскую локаль: strftime('%A') возвращает русское имя,
    как на машине разработчика (на CI локаль обычно C и даёт 'Monday').
    """
    real_datetime = datetime

    class _FrozenDatetime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            # 2026-10-26 — понедельник
            base = cls(2026, 10, 26, hour, minute, tzinfo=tz)
            return base + timedelta(days=weekday)

        def strftime(self, fmt: str) -> str:
            if "%A" in fmt:
                fmt = fmt.replace("%A", RU_WEEKDAYS[self.weekday()])
            return real_datetime.strftime(self, fmt)

    monkeypatch.setattr(schedule, "datetime", _FrozenDatetime)


# ─────────────────────────────────────────────
# format_working_hours_message
# ─────────────────────────────────────────────

class TestFormatWorkingHoursMessage:
    """Форматирование расписания."""

    def test_marks_current_day_by_weekday_number(self, monkeypatch):
        """Метка '(сейчас)' ставится по номеру дня, а не по локали."""
        _mock_config(monkeypatch, WORKING_HOURS)
        _mock_now(monkeypatch, weekday=2, hour=10)  # среда
        message = format_working_hours_message()
        assert "<b>Среда</b>: до 16:00 (сейчас)" in message
        assert message.count("(сейчас)") == 1

    def test_monday_is_current_day(self, monkeypatch):
        """Понедельник определяется корректно (регресс: локаль давала 'Понедельник')."""
        _mock_config(monkeypatch, WORKING_HOURS)
        _mock_now(monkeypatch, weekday=0, hour=9)
        assert "<b>Понедельник</b>: до 16:00 (сейчас)" in format_working_hours_message()

    def test_day_without_hours_shows_not_working(self, monkeypatch):
        """День без часов в конфиге помечается как нерабочий."""
        _mock_config(monkeypatch, WORKING_HOURS)  # воскресенья нет
        _mock_now(monkeypatch, weekday=6, hour=12)  # воскресенье
        message = format_working_hours_message()
        assert "<b>Воскресенье</b>: не работает" in message
        assert "(сейчас)" not in message

    def test_all_days_listed(self, monkeypatch):
        """В сообщении присутствуют все семь дней."""
        _mock_config(monkeypatch, WORKING_HOURS)
        _mock_now(monkeypatch, weekday=0, hour=9)
        message = format_working_hours_message()
        for readable_name in DAY_NAMES.values():
            assert readable_name in message


# ─────────────────────────────────────────────
# is_session_allowed_to_proceed
# ─────────────────────────────────────────────

class TestIsSessionAllowedToProceed:
    """Проверка доступа к сценарию по расписанию."""

    def test_start_before_limit_allowed(self, monkeypatch):
        """Старт до закрытия — разрешён."""
        _mock_config(monkeypatch, WORKING_HOURS)
        _mock_now(monkeypatch, weekday=0, hour=15, minute=59)
        assert is_session_allowed_to_proceed() is True

    def test_start_after_limit_denied(self, monkeypatch):
        """Старт после закрытия — запрещён."""
        _mock_config(monkeypatch, WORKING_HOURS)
        _mock_now(monkeypatch, weekday=0, hour=16, minute=0)
        assert is_session_allowed_to_proceed() is False

    def test_day_without_hours_denied(self, monkeypatch):
        """День без рабочих часов — запрещено."""
        _mock_config(monkeypatch, WORKING_HOURS)
        _mock_now(monkeypatch, weekday=6, hour=12)  # воскресенье
        assert is_session_allowed_to_proceed() is False

    def test_finish_within_grace_period_allowed(self, monkeypatch):
        """Завершение в пределах grace period разрешено."""
        _mock_config(monkeypatch, WORKING_HOURS)
        _mock_now(monkeypatch, weekday=0, hour=16, minute=10)
        started_at = datetime(2026, 10, 26, 15, 50, tzinfo=schedule.MOSCOW_TZ)
        assert is_session_allowed_to_proceed(int(started_at.timestamp())) is True

    def test_finish_after_grace_period_denied(self, monkeypatch):
        """Завершение после grace period запрещено."""
        _mock_config(monkeypatch, WORKING_HOURS)
        _mock_now(monkeypatch, weekday=0, hour=16, minute=20)
        started_at = datetime(2026, 10, 26, 15, 50, tzinfo=schedule.MOSCOW_TZ)
        assert is_session_allowed_to_proceed(int(started_at.timestamp())) is False

    def test_finish_started_after_limit_denied(self, monkeypatch):
        """Если сессия началась после закрытия — завершение запрещено."""
        _mock_config(monkeypatch, WORKING_HOURS)
        _mock_now(monkeypatch, weekday=0, hour=16, minute=5)
        started_at = datetime(2026, 10, 26, 16, 1, tzinfo=schedule.MOSCOW_TZ)
        assert is_session_allowed_to_proceed(int(started_at.timestamp())) is False

    def test_invalid_timestamp_denied(self, monkeypatch):
        """Некорректный timestamp — запрещено."""
        _mock_config(monkeypatch, WORKING_HOURS)
        _mock_now(monkeypatch, weekday=0, hour=10)
        assert is_session_allowed_to_proceed(10**20) is False

    def test_weekday_map_covers_full_week(self):
        """WEEKDAY_MAP покрывает все дни недели и совпадает с DAY_NAMES."""
        assert sorted(WEEKDAY_MAP) == list(range(7))
        assert set(WEEKDAY_MAP.values()) == set(DAY_NAMES)


# ─────────────────────────────────────────────
# Администраторы обходят расписание
# ─────────────────────────────────────────────

class TestAdminBypass:
    """Администраторы обходят расписание в любое время."""

    def _mock_config_with_admins(self, monkeypatch, working_hours, admin_ids):
        """Подменяет конфиг, добавляя секцию admin_ids."""
        monkeypatch.setattr(
            schedule.ConfigLoader,
            "get_config",
            lambda: {
                "working_hours": working_hours,
                "admin_ids": admin_ids,
            },
        )

    def test_admin_passes_outside_working_hours(self, monkeypatch):
        """Админ проходит даже когда сценарий закрыт для всех."""
        self._mock_config_with_admins(monkeypatch, {"monday": 16}, [999])
        _mock_now(monkeypatch, weekday=0, hour=23, minute=30)

        assert is_session_allowed_to_proceed(user_id=999) is True
        assert is_session_allowed_to_proceed(user_id=123) is False

    def test_admin_passes_finish_after_grace_period(self, monkeypatch):
        """Админ может завершить сценарий после истечения grace period."""
        self._mock_config_with_admins(monkeypatch, {"monday": 16}, [999])
        _mock_now(monkeypatch, weekday=0, hour=17, minute=30)

        started_at = datetime(2026, 10, 26, 15, 50, tzinfo=schedule.MOSCOW_TZ)
        ts = int(started_at.timestamp())

        assert is_session_allowed_to_proceed(ts, user_id=999) is True
        assert is_session_allowed_to_proceed(ts, user_id=123) is False

    def test_non_admin_not_in_list_blocked(self, monkeypatch):
        """Пользователь, не входящий в admin_ids, подчиняется расписанию."""
        self._mock_config_with_admins(monkeypatch, {"monday": 16}, [999])
        _mock_now(monkeypatch, weekday=0, hour=17, minute=0)

        assert is_session_allowed_to_proceed(user_id=123) is False
        assert is_session_allowed_to_proceed(user_id=998) is False

    def test_empty_admin_ids_blocks_everyone(self, monkeypatch):
        """При пустом списке admin_ids все подчиняются расписанию."""
        self._mock_config_with_admins(monkeypatch, {"monday": 16}, [])
        _mock_now(monkeypatch, weekday=0, hour=17, minute=0)

        assert is_session_allowed_to_proceed(user_id=999) is False

    def test_missing_admin_ids_section_blocks_everyone(self, monkeypatch):
        """Если секция admin_ids отсутствует в конфиге — все подчиняются расписанию."""
        _mock_config(monkeypatch, {"monday": 16})
        _mock_now(monkeypatch, weekday=0, hour=17, minute=0)

        assert is_session_allowed_to_proceed(user_id=999) is False

    def test_admin_check_works_without_user_id(self, monkeypatch):
        """Без user_id проверка работает как раньше (по расписанию)."""
        self._mock_config_with_admins(monkeypatch, {"monday": 16}, [999])

        _mock_now(monkeypatch, weekday=0, hour=15, minute=30)
        assert is_session_allowed_to_proceed() is True

        _mock_now(monkeypatch, weekday=0, hour=17, minute=0)
        assert is_session_allowed_to_proceed() is False