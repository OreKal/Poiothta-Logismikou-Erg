"""Tests για τις ενέργειες του πάγκου (PR-01)."""

from datetime import datetime

from studyroom import create_booking
from studyroom.desk import change_members, desk_check_in


def test_desk_check_in_sets_status(now):
    b = create_booking("1001", "Β-1", datetime(2026, 11, 4, 10, 0), 1, now=now)
    desk_check_in(b.id, "9001", "Χαλασμένο QR", at=datetime(2026, 11, 4, 10, 5))
    assert b.status == "checked_in"


def test_desk_check_in_runs(now):
    b = create_booking("1002", "Β-2", datetime(2026, 11, 4, 11, 0), 1, now=now)
    desk_check_in(b.id, "9001", "Χαλασμένο QR", at=datetime(2026, 11, 4, 11, 2))


def test_change_members(now):
    b = create_booking("1001", "Γ-1", datetime(2026, 11, 5, 12, 0), 1, members=["1002", "1003"], now=now)
    change_members(b.id, "1001", ["1002", "1003", "1004"], now=now)
    assert len(b.members) == 3
