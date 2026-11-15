from datetime import date, datetime, timedelta

import pytest

from studyroom import notify, rules, store, sweep_no_shows
from studyroom.models import ACTIVE, AUTO_CANCELLED, CANCELLED, CHECKED_IN, NO_SHOW, Booking
from studyroom.penalties import apply_penalties, count_missed
from studyroom.reports import hourly_grid, student_day_summary, weekly_occupancy

EXPECTED_ONE_HOUR_PERCENT = 1.3
EXPECTED_OCCUPANCY_PERCENT = 3.8
OVER_LIMIT_HOURS = 6


def add_booking(  # noqa: PLR0913
    student_id: str,
    room_code: str,
    start: datetime,
    *,
    hours: int = 1,
    status: str = ACTIVE,
    created_at: datetime | None = None,
    checked_in_at: datetime | None = None,
) -> Booking:
    booking = Booking(
        student_id=student_id,
        room_code=room_code,
        start=start,
        hours=hours,
        members=[],
        created_at=created_at or start,
        status=status,
        checked_in_at=checked_in_at,
    )
    store.add_booking(booking)
    return booking


def add_missed(student_id: str, now: datetime, days_ago: int = 1) -> Booking:
    return add_booking(
        student_id,
        "Α-1",
        now - timedelta(days=days_ago),
        status=NO_SHOW,
    )


def test_TC_WB_01_count_missed_empty_history(now):
    """TC-WB-01 · Ο βρόχος των κρατήσεων εκτελείται μηδέν φορές."""
    assert count_missed("1001", now) == 0


def test_TC_WB_02_count_missed_filters_status_and_includes_boundary(now):
    """TC-WB-02 · Μετρά και τις δύο καταστάσεις χαμένης εντός ορίου, όχι CANCELLED."""
    add_missed("1001", now, days_ago=1)
    add_booking("1001", "Α-2", now - timedelta(days=2), status="late_cancel")
    add_booking("1001", "Β-1", now - timedelta(days=3), status=CANCELLED)
    add_booking(
        "1001",
        "Β-2",
        now - timedelta(days=30),
        status=NO_SHOW,
    )

    assert count_missed("1001", now) == rules.MISSED_LIMIT


@pytest.mark.xfail(strict=True, reason="INC-06")
def test_TC_WB_03_count_missed_excludes_start_outside_thirty_day_window(now):
    """TC-WB-03 · Η έναρξη 30 ημέρες και 1 δευτερόλεπτο πριν είναι εκτός ΚΡ11."""
    add_booking(
        "1001",
        "Α-1",
        now - timedelta(days=30, seconds=1),
        status=NO_SHOW,
    )

    assert count_missed("1001", now) == 0


def test_TC_WB_04_apply_penalties_unknown_or_already_blocked_student(now):
    """TC-WB-04 · Επιστρέφει False για άγνωστο φοιτητή και ενεργό αποκλεισμό."""
    assert apply_penalties("9999", now) is False

    student = store.get_student("1001")
    assert student is not None
    student.blocked_until = now + timedelta(hours=1)
    assert apply_penalties("1001", now) is False


def test_TC_WB_05_apply_penalties_below_threshold_does_not_block(now):
    """TC-WB-05 · Δύο χαμένες δεν αρκούν για αποκλεισμό κατά ΚΡ11."""
    add_missed("1001", now)
    add_missed("1001", now, days_ago=2)

    assert apply_penalties("1001", now) is False
    assert store.get_student("1001").blocked_until is None


def test_TC_WB_06_apply_penalties_blocks_and_cancels_only_in_window(now, monkeypatch):
    """TC-WB-06 · Τρίτη χαμένη επιβάλλει 168 ώρες και ακυρώνει εντός ορίων."""
    for days_ago in (1, 2, 3):
        add_missed("1001", now, days_ago=days_ago)
    at_start = add_booking("1001", "Α-2", now)
    before_start = add_booking("1001", "Β-1", now - timedelta(seconds=1))
    before_expiry = add_booking("1001", "Β-2", now + timedelta(days=7) - timedelta(seconds=1))
    at_expiry = add_booking("1001", "Γ-1", now + timedelta(days=7))
    checked_in = add_booking("1001", "Α-1", now + timedelta(days=1), status=CHECKED_IN)
    notices = []
    monkeypatch.setattr(
        notify,
        "send_block_notice",
        lambda student, cancelled: notices.append((student.id, list(cancelled))),
    )

    assert apply_penalties("1001", now) is True

    blocked_until = now + timedelta(days=7)
    assert store.get_student("1001").blocked_until == blocked_until
    assert at_start.status == AUTO_CANCELLED
    assert before_expiry.status == AUTO_CANCELLED
    assert before_start.status == ACTIVE
    assert at_expiry.status == ACTIVE
    assert checked_in.status == CHECKED_IN
    assert at_start.cancelled_at == before_expiry.cancelled_at == now
    assert notices == [("1001", [at_start, before_expiry])]


def test_TC_WB_07_apply_penalties_allows_threshold_without_future_bookings(now, monkeypatch):
    """TC-WB-07 · Ο βρόχος ενεργών κρατήσεων δεν προσθέτει ακυρώσεις όταν είναι κενός."""
    for days_ago in (1, 2, 3):
        add_missed("1001", now, days_ago=days_ago)
    notices = []
    monkeypatch.setattr(
        notify,
        "send_block_notice",
        lambda student, cancelled: notices.append((student.id, list(cancelled))),
    )

    assert apply_penalties("1001", now) is True
    assert notices == [("1001", [])]


def test_TC_WB_08_sweep_empty_store_returns_no_no_shows(now):
    """TC-WB-08 · Κάλυψη μηδενικών επαναλήψεων και κενού συνόλου φοιτητών."""
    assert sweep_no_shows(now) == []


def test_TC_WB_09_sweep_skips_checkin_and_exact_fifteen_minute_boundary(now):
    """TC-WB-09 · Η ενεργή κράτηση μένει ενεργή ακριβώς στο +15:00· check-in παραλείπεται."""
    checked_in = add_booking(
        "1001",
        "Α-1",
        now - timedelta(minutes=16),
        status=CHECKED_IN,
        checked_in_at=now - timedelta(minutes=1),
    )
    at_boundary = add_booking("1002", "Α-2", now - timedelta(minutes=15))

    assert sweep_no_shows(now) == []
    assert checked_in.status == CHECKED_IN
    assert at_boundary.status == ACTIVE


def test_TC_WB_10_sweep_marks_one_booking_after_deadline(now):
    """TC-WB-10 · Μία ενεργή κράτηση γίνεται NO_SHOW ένα δευτερόλεπτο μετά το +15."""
    booking = add_booking("1001", "Α-1", now - timedelta(minutes=15, seconds=1))

    assert sweep_no_shows(now) == [booking]
    assert booking.status == NO_SHOW


def test_TC_WB_11_sweep_uses_each_student_once_for_penalties(now, monkeypatch):
    """TC-WB-11 · Βρόχοι με πολλές κρατήσεις: η ποινή αποστέλλεται μία φορά ανά φοιτητή."""
    bookings = [
        add_booking("1001", room, now - timedelta(minutes=16))
        for room in ("Α-1", "Α-2", "Β-1")
    ]
    notices = []
    monkeypatch.setattr(
        notify,
        "send_block_notice",
        lambda student, cancelled: notices.append((student.id, list(cancelled))),
    )

    assert sweep_no_shows(now) == bookings
    assert all(booking.status == NO_SHOW for booking in bookings)
    assert store.get_student("1001").blocked_until == now + timedelta(days=7)
    assert len(notices) == 1


def test_TC_WB_12_weekly_occupancy_empty_week_is_zero_for_each_room():
    """TC-WB-12 · Έξι αίθουσες × έξι ημέρες, χωρίς κρατήσεις, δίνουν 0,0%."""
    result = weekly_occupancy(date(2026, 11, 2))

    assert set(result) == {room.code for room in store.all_rooms()}
    assert all(occupancy == 0.0 for occupancy in result.values())


def test_TC_WB_13_weekly_occupancy_rounds_to_one_decimal():
    """TC-WB-13 · Η εβδομαδιαία αναλογία στρογγυλοποιείται σε ένα δεκαδικό."""
    add_booking("1001", "Α-1", datetime(2026, 11, 2, 8))

    assert weekly_occupancy(date(2026, 11, 2))["Α-1"] == EXPECTED_ONE_HOUR_PERCENT


def test_TC_WB_14_weekly_occupancy_counts_live_and_ignores_missed():
    """TC-WB-14 · Ενεργές/check-in ώρες μετρούν, ακυρωμένες/no-show όχι."""
    add_booking("1001", "Α-1", datetime(2026, 11, 2, 10), hours=2)
    add_booking(
        "1002",
        "Α-1",
        datetime(2026, 11, 3, 10),
        status=CHECKED_IN,
        checked_in_at=datetime(2026, 11, 3, 10),
    )
    add_booking("1003", "Α-1", datetime(2026, 11, 4, 10), status=CANCELLED, hours=2)
    add_booking("1001", "Α-1", datetime(2026, 11, 5, 10), status=NO_SHOW)

    assert weekly_occupancy(date(2026, 11, 2))["Α-1"] == EXPECTED_OCCUPANCY_PERCENT


def test_TC_WB_15_weekly_occupancy_zero_available_hours_is_zero(monkeypatch):
    """TC-WB-15 · Αμυντική διαδρομή με καμία ημέρα λειτουργίας σε έξι ημέρες."""
    monkeypatch.setattr(rules, "opening_hours", lambda _day: None)

    result = weekly_occupancy(date(2026, 11, 2))

    assert all(occupancy == 0.0 for occupancy in result.values())


def test_TC_WB_16_hourly_grid_sunday_is_empty():
    """TC-WB-16 · Την Κυριακή η αναφορά είναι κενή (ΚΡ15)."""
    assert hourly_grid("Α-1", date(2026, 11, 8)) == {}


def test_TC_WB_17_hourly_grid_without_bookings_is_free():
    """TC-WB-17 · Μηδέν κρατήσεις αφήνουν όλες τις ώρες λειτουργίας ελεύθερες."""
    grid = hourly_grid("Α-1", date(2026, 11, 3))

    assert list(grid) == list(range(8, 22))
    assert set(grid.values()) == {"free"}


def test_TC_WB_18_hourly_grid_marks_used_booked_and_other_states_free():
    """TC-WB-18 · Ελέγχει τις τρεις καταστάσεις και διαδοχικές ώρες."""
    add_booking("1001", "Α-1", datetime(2026, 11, 3, 9), hours=2)
    add_booking(
        "1002",
        "Α-1",
        datetime(2026, 11, 3, 11),
        status=CHECKED_IN,
        checked_in_at=datetime(2026, 11, 3, 11),
    )
    add_booking("1003", "Α-1", datetime(2026, 11, 3, 12), status=CANCELLED)

    grid = hourly_grid("Α-1", date(2026, 11, 3))

    assert grid[8] == "free"
    assert grid[9] == grid[10] == "booked"
    assert grid[11] == "used"
    assert grid[12] == "free"


def test_TC_WB_19_student_day_summary_unknown_student_gets_regular_limit():
    """TC-WB-19 · Άγνωστος φοιτητής χωρίς εξεταστική λαμβάνει το γενικό όριο."""
    assert student_day_summary("9999", date(2026, 11, 3)) == {
        "student": "9999",
        "day": "2026-11-03",
        "used": 0,
        "remaining": 2,
    }


def test_TC_WB_20_student_day_summary_counts_active_and_checkedin_only():
    """TC-WB-20 · Άθροισμα δύο επιλέξιμων κρατήσεων και αγνόηση CANCELLED."""
    day = date(2026, 11, 3)
    add_booking("1001", "Α-1", datetime(2026, 11, 3, 8), hours=1)
    add_booking("1001", "Α-2", datetime(2026, 11, 3, 9), status=CHECKED_IN, hours=1)
    add_booking("1001", "Β-1", datetime(2026, 11, 3, 10), status=CANCELLED, hours=2)
    add_booking("1001", "Β-2", datetime(2026, 11, 4, 8), hours=1)

    assert student_day_summary("1001", day) == {
        "student": "1001",
        "day": "2026-11-03",
        "used": 2,
        "remaining": 0,
    }


def test_TC_WB_21_student_day_summary_exam_and_accessibility_limits():
    """TC-WB-21 · Εξεταστική ή δικαιούχος αυξάνει το όριο σε τρεις ώρες."""
    day = date(2026, 11, 3)
    rules.EXAM_PERIODS.append((day, day))
    add_booking("1001", "Α-1", datetime(2026, 11, 3, 8), hours=2)
    add_booking("1001", "Α-2", datetime(2026, 11, 3, 10), hours=1)
    add_booking("1004", "Β-1", datetime(2026, 11, 3, 8), hours=2)
    add_booking("1004", "Β-2", datetime(2026, 11, 3, 10), hours=1)

    assert student_day_summary("1001", day)["remaining"] == 0
    assert student_day_summary("1004", day)["remaining"] == 0


@pytest.mark.xfail(strict=True, reason="INC-07")
def test_TC_WB_22_student_day_summary_uses_day_of_use_not_creation():
    """TC-WB-22 · ΚΡ16 ορίζει χρήση ανά ημέρα κράτησης, όχι ημέρα δημιουργίας."""
    add_booking(
        "1001",
        "Α-1",
        datetime(2026, 11, 4, 8),
        created_at=datetime(2026, 11, 3, 10),
    )

    assert student_day_summary("1001", date(2026, 11, 4))["used"] == 1


def test_TC_WB_23_student_day_summary_never_returns_negative_remaining():
    """TC-WB-23 · Το υπόλοιπο περιορίζεται στο μηδέν ακόμη και με υπέρβαση."""
    day = date(2026, 11, 3)
    for hour in (8, 10, 12):
        add_booking("1001", "Α-1", datetime(2026, 11, 3, hour), hours=2)

    summary = student_day_summary("1001", day)

    assert summary["used"] == OVER_LIMIT_HOURS
    assert summary["remaining"] == 0


def test_TC_WB_24_count_missed_ignores_records_older_than_implementation_window(now):
    """TC-WB-24 · Ο παλαιότερος βρόχος κλάδος απορρίπτει εγγραφή πέρα από 31 ημέρες."""
    add_booking("1001", "Α-1", now - timedelta(days=32), status=NO_SHOW)

    assert count_missed("1001", now) == 0


def test_TC_WB_25_apply_penalties_treats_expired_block_as_inactive(now):
    """TC-WB-25 · Όριο blocked_until == now δεν εμποδίζει τον έλεγχο της ποινής."""
    student = store.get_student("1001")
    assert student is not None
    student.blocked_until = now
    add_missed("1001", now)
    add_missed("1001", now, days_ago=2)

    assert apply_penalties("1001", now) is False


def test_TC_WB_26_apply_penalties_allows_new_check_when_block_expires(now):
    """TC-WB-26 · Ακριβώς στη λήξη, νέα χαμένη μπορεί να ενεργοποιήσει νέο αποκλεισμό."""
    for days_ago in (1, 2, 3):
        add_missed("1001", now, days_ago=days_ago)
    student = store.get_student("1001")
    assert student is not None
    student.blocked_until = now

    assert apply_penalties("1001", now) is True
    assert student.blocked_until == now + timedelta(days=7)


def test_TC_WB_27_count_missed_two_records():
    """TC-WB-27 · Δύο επαναλήψεις: η χαμένη μετρά και η CANCELLED αγνοείται."""
    now = datetime(2026, 11, 3, 10)
    add_missed("1001", now)
    add_booking("1001", "Α-2", now - timedelta(days=1), status=CANCELLED)

    assert count_missed("1001", now) == 1


def test_TC_WB_28_sweep_processes_two_different_students(now):
    """TC-WB-28 · Ο βρόχος μοναδικών φοιτητών εκτελείται δύο φορές."""
    first = add_booking("1001", "Α-1", now - timedelta(minutes=16))
    second = add_booking("1002", "Α-2", now - timedelta(minutes=16))

    assert sweep_no_shows(now) == [first, second]
    assert first.status == second.status == NO_SHOW
    assert store.get_student("1001").blocked_until is None
    assert store.get_student("1002").blocked_until is None


def test_TC_WB_29_apply_penalties_cancels_one_eligible_booking(now):
    """TC-WB-29 · Μία κράτηση εντός αποκλεισμού μεταβαίνει σε AUTO_CANCELLED."""
    for days_ago in (1, 2, 3):
        add_missed("1001", now, days_ago=days_ago)
    target = add_booking("1001", "Α-2", now + timedelta(days=1))

    assert apply_penalties("1001", now) is True
    assert target.status == AUTO_CANCELLED


def test_TC_WB_30_hourly_grid_saturday_has_eight_operating_hours():
    """TC-WB-30 · Σάββατο: ο βρόχος ωρών εκτελείται οκτώ φορές (ΚΡ1, ΚΡ15)."""
    grid = hourly_grid("Α-1", date(2026, 11, 7))

    assert list(grid) == list(range(10, 18))
    assert set(grid.values()) == {"free"}


def test_TC_WB_31_accessibility_limit_applies_outside_exam_period():
    """TC-WB-31 · Δικαιούχος έχει όριο τριών ωρών και εκτός εξεταστικής (ΚΡ3, ΚΡ16)."""
    day = date(2026, 11, 4)
    for hour in (8, 10, 12):
        add_booking("1004", "Α-1", datetime(2026, 11, 4, hour))

    assert student_day_summary("1004", day)["remaining"] == 0


def test_TC_WB_32_sweep_three_distinct_students(now):
    """TC-WB-32 · Ο βρόχος ποινών ανά μοναδικό φοιτητή εκτελείται τρεις φορές."""
    bookings = [
        add_booking(student_id, room, now - timedelta(minutes=16))
        for student_id, room in (("1001", "Α-1"), ("1002", "Α-2"), ("1003", "Β-1"))
    ]

    assert sweep_no_shows(now) == bookings
    assert all(booking.status == NO_SHOW for booking in bookings)


def test_TC_WB_33_hourly_grid_single_booking_single_hour():
    """TC-WB-33 · Ο βρόχος κρατήσεων/ωρών εκτελείται μία φορά."""
    add_booking("1001", "Α-1", datetime(2026, 11, 3, 10))

    grid = hourly_grid("Α-1", date(2026, 11, 3))

    assert grid[10] == "booked"
    assert grid[9] == grid[11] == "free"


def test_TC_WB_34_student_day_summary_two_records():
    """TC-WB-34 · Ο βρόχος σύνοψης εκτελεί δύο επαναλήψεις."""
    day = date(2026, 11, 3)
    add_booking("1001", "Α-1", datetime(2026, 11, 3, 8))
    add_booking("1001", "Α-2", datetime(2026, 11, 3, 9), status=CANCELLED)

    assert student_day_summary("1001", day)["used"] == 1
