from datetime import date, datetime, timedelta

import pytest

from studyroom import (
    BookingError,
    cancel_booking,
    check_in,
    create_booking,
    rules,
    store,
    sweep_no_shows,
)


def moment(day: int, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, second)


def book(
    student_id: str,
    room_code: str,
    start: datetime,
    now: datetime,
    hours: int = 1,
    members: list[str] | None = None,
):
    return create_booking(
        student_id,
        room_code,
        start,
        hours=hours,
        members=members,
        now=now,
    )


WINDOW_CASES = [
    ("TC-BB-01", moment(3, 10), moment(4, 7), "Α-1", 1, False),
    ("TC-BB-02", moment(3, 10), moment(4, 8), "Α-1", 1, True),
    ("TC-BB-03", moment(3, 10), moment(6, 21), "Α-1", 1, True),
    ("TC-BB-04", moment(3, 10), moment(6, 22), "Α-1", 1, False),
    ("TC-BB-05", moment(3, 10), moment(7, 9), "Α-1", 1, False),
    ("TC-BB-06", moment(3, 10), moment(7, 10), "Α-1", 1, True),
    ("TC-BB-07", moment(3, 10), moment(7, 17), "Α-1", 1, True),
    ("TC-BB-08", moment(3, 10), moment(7, 17), "Α-1", 2, False),
    ("TC-BB-09", moment(3, 10), moment(8, 10), "Α-1", 1, False),
    ("TC-BB-10", moment(3, 10), moment(4, 10, 30), "Α-1", 1, False),
    ("TC-BB-11", moment(3, 10), moment(4, 10), "Α-1", 0, False),
    ("TC-BB-12", moment(3, 10), moment(4, 10), "Α-1", 1, True),
    ("TC-BB-13", moment(3, 10), moment(4, 10), "Α-1", 2, True),
    ("TC-BB-14", moment(3, 10), moment(4, 10), "Α-1", 3, False),
    ("TC-BB-15", moment(3, 10), moment(3, 9), "Α-1", 1, False),
    ("TC-BB-16", moment(2, 7, 59, 59), moment(9, 8), "Α-1", 1, False),
    ("TC-BB-17", moment(2, 8), moment(9, 8), "Α-1", 1, True),
    ("TC-BB-18", moment(2, 8), moment(14, 10), "Α-1", 1, True),
]


@pytest.mark.parametrize(
    "tc_id,now,start,room,hours,accepted",
    WINDOW_CASES,
    ids=[case[0] for case in WINDOW_CASES],
)
def test_hours_duration_and_booking_window(tc_id, now, start, room, hours, accepted):
    before = len(store.all_bookings())
    if accepted:
        result = book("1001", room, start, now, hours)
        assert result.status == "active"
        assert len(store.all_bookings()) == before + 1
    else:
        with pytest.raises(BookingError):
            book("1001", room, start, now, hours)
        assert len(store.all_bookings()) == before


def test_TC_BB_56_booking_beyond_block_remains_active():
    initial = moment(2, 8)
    _record_no_show("1001", 3, initial)
    _record_no_show("1001", 4, moment(3, 10, 15, 1))
    after_block = book("1001", "Α-2", moment(12, 11), moment(4, 10, 15, 1))
    book("1001", "Α-1", moment(5, 10), moment(4, 10, 15, 1))
    sweep_no_shows(now=moment(5, 10, 15, 1))
    assert store.get_student("1001").blocked_until == moment(5, 10, 15, 1) + timedelta(days=7)
    assert after_block.status == "active"


ACCESS_CASES = [
    ("TC-BB-19", moment(5, 23, 59, 59), moment(9, 8), "1004", False),
    ("TC-BB-20", moment(6, 0), moment(9, 8), "1004", True),
    ("TC-BB-21", moment(3, 10), moment(7, 10), "1001", True),
]


@pytest.mark.parametrize(
    "tc_id,now,start,student_id,accepted",
    ACCESS_CASES,
    ids=[case[0] for case in ACCESS_CASES],
)
def test_accessible_room_advance_booking(tc_id, now, start, student_id, accepted):
    before = len(store.all_bookings())
    if accepted:
        book(student_id, "Α-ΙΣ", start, now)
        assert len(store.all_bookings()) == before + 1
    else:
        with pytest.raises(BookingError):
            book(student_id, "Α-ΙΣ", start, now)
        assert len(store.all_bookings()) == before


def test_TC_BB_22_daily_limit_regular_day_accepts_two_hours(now):
    book("1001", "Α-1", moment(3, 11), now, 1)
    result = book("1001", "Α-2", moment(3, 12), now, 1)
    assert result.status == "active"


def test_TC_BB_23_daily_limit_regular_day_rejects_third_hour(now):
    book("1001", "Α-1", moment(3, 11), now, 2)
    before = len(store.all_bookings())
    with pytest.raises(BookingError):
        book("1001", "Α-2", moment(3, 13), now, 1)
    assert len(store.all_bookings()) == before


def test_TC_BB_24_exam_day_allows_three_hours_and_rejects_fourth(now):
    rules.EXAM_PERIODS.append((date(2026, 11, 3), date(2026, 11, 3)))
    book("1001", "Α-1", moment(3, 11), now, 2)
    book("1001", "Α-2", moment(3, 13), now, 1)
    before = len(store.all_bookings())
    with pytest.raises(BookingError):
        book("1001", "Α-1", moment(3, 14), now, 1)
    assert len(store.all_bookings()) == before


def test_TC_BB_25_accessibility_entitlement_allows_three_hours_outside_exam(now):
    book("1004", "Α-1", moment(3, 11), now, 2)
    result = book("1004", "Α-2", moment(3, 13), now, 1)
    assert result.status == "active"


def test_TC_BB_26_daily_limit_uses_date_of_use_not_booking_creation(now):
    book("1001", "Α-1", moment(5, 8), now)
    book("1001", "Α-2", moment(5, 9), now)
    before = len(store.all_bookings())
    with pytest.raises(BookingError):
        book("1001", "Α-1", moment(5, 10), now)
    assert len(store.bookings_for_student("1001")) == before


DECISION_CASES = [
    ("TC-BB-27", "blocked", 1, "reject"),
    ("TC-BB-28", "group-exceeds-capacity", 0, "reject"),
    ("TC-BB-29", "daily-limit-exceeded", 0, "reject"),
    ("TC-BB-30", "all-conditions-valid", 0, "accept"),
]


@pytest.mark.parametrize(
    "tc_id,rule,blocked,expected",
    DECISION_CASES,
    ids=[case[0] for case in DECISION_CASES],
)
def test_decision_table_rules(tc_id, rule, blocked, expected, now):
    student = store.get_student("1001")
    if blocked:
        student.blocked_until = now + timedelta(days=1)
    if rule == "daily-limit-exceeded":
        book("1001", "Α-1", moment(3, 11), now, 2)
        attempted = ("Α-2", moment(3, 13), 1, [])
    elif rule == "group-exceeds-capacity":
        attempted = ("Α-1", moment(4, 10), 1, ["1002", "1003"])
    elif rule == "all-conditions-valid":
        attempted = ("Γ-1", moment(4, 10), 1, ["1002", "1003"])
    else:
        attempted = ("Α-1", moment(4, 10), 1, [])
    before = len(store.all_bookings())
    if expected == "accept":
        result = book("1001", attempted[0], attempted[1], now, attempted[2], attempted[3])
        assert result.status == "active"
        assert len(store.all_bookings()) == before + 1
    else:
        with pytest.raises(BookingError):
            book("1001", attempted[0], attempted[1], now, attempted[2], attempted[3])
        assert len(store.all_bookings()) == before


def test_TC_BB_31_six_person_room_requires_three_people(now):
    before = len(store.all_bookings())
    with pytest.raises(BookingError):
        book("1001", "Γ-1", moment(4, 10), now, members=["1002"])
    assert len(store.all_bookings()) == before


def test_TC_BB_32_six_person_room_accepts_three_distinct_students(now):
    result = book("1001", "Γ-1", moment(4, 10), now, members=["1002", "1003"])
    assert result.status == "active"


def test_TC_BB_33_capacity_two_accepts_two_people(now):
    result = book("1001", "Α-1", moment(4, 10), now, members=["1002"])
    assert result.status == "active"


@pytest.mark.parametrize(
    "tc_id,members,room",
    [
        ("TC-BB-34", ["9999"], "Α-1"),
        ("TC-BB-35", ["1002", "1002"], "Γ-1"),
    ],
    ids=["TC-BB-34", "TC-BB-35"],
)
def test_invalid_or_duplicate_group_members_are_rejected(tc_id, members, room, now):
    before = len(store.all_bookings())
    with pytest.raises(BookingError):
        book("1001", room, moment(4, 10), now, members=members)
    assert len(store.all_bookings()) == before


def test_TC_BB_36_room_overlap_is_rejected_without_mutation(now):
    original = book("1001", "Α-1", moment(4, 10), now, hours=2)
    before = len(store.all_bookings())
    with pytest.raises(BookingError):
        book("1002", "Α-1", moment(4, 11), now)
    assert len(store.all_bookings()) == before
    assert original.status == "active"


def test_TC_BB_37_adjacent_room_bookings_are_allowed(now):
    first = book("1001", "Α-1", moment(4, 10), now)
    second = book("1002", "Α-1", moment(4, 11), now)
    assert first.status == second.status == "active"


def test_TC_BB_38_owner_overlap_in_different_rooms_is_rejected(now):
    first = book("1001", "Α-1", moment(4, 10), now, hours=2)
    before = len(store.all_bookings())
    with pytest.raises(BookingError):
        book("1001", "Α-2", moment(4, 11), now)
    assert len(store.all_bookings()) == before
    assert first.status == "active"


def test_TC_BB_39_checkin_at_ten_minutes_before_is_allowed(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    result = check_in(booking.id, "1001", now=moment(4, 11, 50))
    assert result.status == "checked_in"
    assert result.checked_in_at == moment(4, 11, 50)


def test_TC_BB_40_checkin_one_second_before_window_is_rejected_unchanged(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    with pytest.raises(BookingError):
        check_in(booking.id, "1001", now=moment(4, 11, 49, 59))
    assert booking.status == "active"
    assert booking.checked_in_at is None


def test_TC_BB_41_checkin_at_fifteen_minutes_is_allowed(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    result = check_in(booking.id, "1001", now=moment(4, 12, 15))
    assert result.status == "checked_in"
    assert result.checked_in_at == moment(4, 12, 15)


def test_TC_BB_42_checkin_one_second_after_window_is_rejected_unchanged(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    with pytest.raises(BookingError):
        check_in(booking.id, "1001", now=moment(4, 12, 15, 1))
    assert booking.status == "active"
    assert booking.checked_in_at is None


def test_TC_BB_43_declared_member_can_check_in(now):
    booking = book("1001", "Α-1", moment(4, 12), now, members=["1002"])
    result = check_in(booking.id, "1002", now=moment(4, 12))
    assert result.status == "checked_in"
    assert result.checked_in_by == "1002"


def test_TC_BB_44_nonmember_checkin_is_rejected_without_mutation(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    before = len(store.all_bookings())
    with pytest.raises(BookingError):
        check_in(booking.id, "1003", now=moment(4, 12))
    assert len(store.all_bookings()) == before
    assert booking.status == "active"
    assert booking.checked_in_at is None


def test_TC_BB_45_student_cannot_use_staff_checkin_flag(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    student = store.get_student("1002")
    assert student.role == "student"
    with pytest.raises(BookingError):
        check_in(booking.id, student.id, now=moment(4, 12), by_staff=True)
    assert booking.status == "active"
    assert booking.checked_in_at is None


def test_TC_BB_46_cancellation_exactly_sixty_minutes_early_is_not_missed(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    result = cancel_booking(booking.id, "1001", now=moment(4, 11))
    assert result.status == "cancelled"
    assert result.cancelled_at == moment(4, 11)


def test_TC_BB_47_cancellation_fifty_nine_minutes_fifty_nine_seconds_early_is_missed(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    result = cancel_booking(booking.id, "1001", now=moment(4, 11, 0, 1))
    assert result.status == "late_cancel"


def test_TC_BB_48_cancellation_after_start_is_missed(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    result = cancel_booking(booking.id, "1001", now=moment(4, 12, 1))
    assert result.status == "late_cancel"


def test_TC_BB_49_other_student_cannot_cancel_booking(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    before = len(store.all_bookings())
    with pytest.raises(BookingError):
        cancel_booking(booking.id, "1002", now=moment(4, 10))
    assert len(store.all_bookings()) == before
    assert booking.status == "active"
    assert booking.cancelled_at is None


def test_TC_BB_50_checked_in_booking_cannot_be_cancelled(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    check_in(booking.id, "1001", now=moment(4, 11, 50))
    with pytest.raises(BookingError):
        cancel_booking(booking.id, "1001", now=moment(4, 11, 55))
    assert booking.status == "checked_in"
    assert booking.cancelled_at is None


def test_TC_BB_51_sweep_at_fifteen_minutes_does_not_mark_no_show(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    missed = sweep_no_shows(now=moment(4, 12, 15))
    assert booking.status == "active"
    assert booking not in missed


def test_TC_BB_52_sweep_after_fifteen_minutes_marks_no_show(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    missed = sweep_no_shows(now=moment(4, 12, 15, 1))
    assert booking.status == "no_show"
    assert booking in missed


def _record_no_show(student_id: str, booking_day: int, creation_time: datetime) -> None:
    booking = book(student_id, "Α-1", moment(booking_day, 10), creation_time)
    sweep_no_shows(now=moment(booking_day, 10, 15, 1))


def _make_auto_cancelled_booking():
    initial = moment(2, 8)
    _record_no_show("1001", 3, initial)
    _record_no_show("1001", 4, moment(3, 10, 15, 1))
    third_creation = moment(4, 10, 15, 1)
    target = book("1001", "Α-2", moment(6, 10), third_creation)
    book("1001", "Α-1", moment(5, 10), third_creation)
    sweep_no_shows(now=moment(5, 10, 15, 1))
    return target, moment(5, 10, 15, 1)


def test_TC_BB_53_third_miss_blocks_student_and_cancels_bookings_in_period():
    initial = moment(2, 8)
    _record_no_show("1001", 3, initial)
    _record_no_show("1001", 4, moment(3, 10, 15, 1))
    target = book("1001", "Α-2", moment(6, 10), moment(4, 10, 15, 1))
    third = book("1001", "Α-1", moment(5, 10), moment(4, 10, 15, 1))
    sweep_no_shows(now=moment(5, 10, 15, 1))
    student = store.get_student("1001")
    assert third.status == "no_show"
    assert student.blocked_until == moment(5, 10, 15, 1) + timedelta(days=7)
    assert target.status == "auto_cancelled"


def test_TC_BB_54_booking_is_allowed_at_exact_block_expiry():
    initial = moment(2, 8)
    _record_no_show("1001", 3, initial)
    _record_no_show("1001", 4, moment(3, 10, 15, 1))
    _record_no_show("1001", 5, moment(4, 10, 15, 1))
    blocked_until = store.get_student("1001").blocked_until
    assert blocked_until is not None
    result = book("1001", "Α-2", moment(12, 11), blocked_until)
    assert result.status == "active"


def test_TC_BB_55_miss_older_than_thirty_days_does_not_count():
    first_start = moment(2, 10)
    first = book("1001", "Α-1", first_start, moment(2, 8))
    sweep_no_shows(now=first_start + timedelta(minutes=15, seconds=1))
    second_start = first_start + timedelta(days=30)
    second = book("1001", "Α-2", second_start, moment(23, 8))
    sweep_no_shows(now=second_start + timedelta(minutes=15, seconds=1))
    third_start = first_start + timedelta(days=31)
    third = book("1001", "Α-1", third_start, moment(23, 8))
    before = len(store.all_bookings())
    cancel_booking(third.id, "1001", now=third.start)
    assert first.status == "no_show"
    assert second.status == "no_show"
    assert store.get_student("1001").blocked_until is None
    assert len(store.all_bookings()) == before


STATE_REJECTION_CASES = [
    ("TC-BB-57", "checked_in", "late"),
    ("TC-BB-58", "cancelled", "early"),
    ("TC-BB-59", "cancelled", "late"),
    ("TC-BB-60", "late_cancel", "late"),
    ("TC-BB-61", "no_show", "late"),
    ("TC-BB-62", "auto_cancelled", "early"),
    ("TC-BB-63", "auto_cancelled", "late"),
]


def _booking_in_state(state: str, now: datetime):
    start = moment(4, 12)
    booking = book("1001", "Α-1", start, now)
    if state == "checked_in":
        check_in(booking.id, "1001", now=start - timedelta(minutes=10))
    elif state == "cancelled":
        cancel_booking(booking.id, "1001", now=start - timedelta(hours=3))
    elif state == "late_cancel":
        cancel_booking(booking.id, "1001", now=start - timedelta(minutes=30))
    elif state == "no_show":
        sweep_no_shows(now=start + timedelta(minutes=16))
    elif state == "auto_cancelled":
        return _make_auto_cancelled_booking()
    return booking, start


@pytest.mark.parametrize(
    "tc_id,state,attempt",
    STATE_REJECTION_CASES,
    ids=[case[0] for case in STATE_REJECTION_CASES],
)
def test_cancellation_from_nonactive_state_is_rejected(tc_id, state, attempt, now):
    booking, start = _booking_in_state(state, now)
    before_count = len(store.all_bookings())
    before_status = booking.status
    before_cancelled_at = booking.cancelled_at
    if state == "auto_cancelled":
        attempt_now = moment(5, 10, 15, 1) if attempt == "early" else moment(6, 9, 30)
    elif state == "cancelled":
        attempt_now = start - timedelta(hours=2) if attempt == "early" else start - timedelta(minutes=30)
    elif state == "checked_in":
        attempt_now = start - timedelta(minutes=5)
    elif state == "late_cancel":
        attempt_now = start - timedelta(minutes=29)
    else:
        attempt_now = start + timedelta(minutes=17)
    with pytest.raises(BookingError):
        cancel_booking(booking.id, "1001", now=attempt_now)
    assert len(store.all_bookings()) == before_count
    assert booking.status == before_status
    assert booking.cancelled_at == before_cancelled_at


def test_TC_BB_64_one_switch_checkin_then_no_show_sweep(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    check_in(booking.id, "1001", now=moment(4, 11, 50))
    missed = sweep_no_shows(now=moment(4, 12, 16))
    assert booking.status == "checked_in"
    assert booking not in missed


def test_TC_BB_65_one_switch_active_late_cancel_then_time_does_not_change_state(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    cancel_booking(booking.id, "1001", now=moment(4, 11, 30))
    missed = sweep_no_shows(now=moment(4, 12, 16))
    assert booking.status == "late_cancel"
    assert booking not in missed


def test_TC_BB_66_non_entitled_student_cannot_book_accessible_room_beyond_five_days():
    before = len(store.all_bookings())
    with pytest.raises(BookingError):
        book("1001", "Α-ΙΣ", datetime(2026, 11, 16, 10), datetime(2026, 11, 9, 8))
    assert len(store.all_bookings()) == before


def test_TC_BB_67_unknown_student_cannot_create_booking(now):
    before = len(store.all_bookings())
    with pytest.raises(BookingError):
        book("9999", "Α-1", moment(4, 12), now)
    assert len(store.all_bookings()) == before


def test_TC_BB_68_unknown_room_cannot_create_booking(now):
    before = len(store.all_bookings())
    with pytest.raises(BookingError):
        book("1001", "X-9", moment(4, 12), now)
    assert len(store.all_bookings()) == before


def test_TC_BB_69_unknown_booking_cannot_be_cancelled(now):
    before = len(store.all_bookings())
    with pytest.raises(BookingError):
        cancel_booking("missing-booking", "1001", now=now)
    assert len(store.all_bookings()) == before


def test_TC_BB_70_unknown_booking_cannot_be_checked_in(now):
    before = len(store.all_bookings())
    with pytest.raises(BookingError):
        check_in("missing-booking", "1001", now=now)
    assert len(store.all_bookings()) == before


def test_TC_BB_71_nonstaff_actor_cannot_use_staff_checkin_fallback(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    before = len(store.all_bookings())
    with pytest.raises(BookingError):
        check_in(booking.id, "9999", now=moment(4, 12), by_staff=True)
    assert len(store.all_bookings()) == before
    assert booking.status == "active"
    assert booking.checked_in_at is None


def test_TC_BB_72_authorized_staff_can_record_fallback_checkin(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    result = check_in(booking.id, "9001", now=moment(4, 12), by_staff=True)
    assert result.status == "checked_in"
    assert result.checked_in_by == "9001"


def test_TC_BB_73_booking_is_rejected_one_second_before_block_expiry():
    initial = moment(2, 8)
    _record_no_show("1001", 3, initial)
    _record_no_show("1001", 4, moment(3, 10, 15, 1))
    _record_no_show("1001", 5, moment(4, 10, 15, 1))
    blocked_until = store.get_student("1001").blocked_until
    assert blocked_until is not None
    before = len(store.all_bookings())
    with pytest.raises(BookingError):
        book(
            "1001",
            "Α-2",
            moment(13, 11),
            blocked_until - timedelta(seconds=1),
        )
    assert len(store.all_bookings()) == before


def test_TC_BB_74_unknown_student_cannot_cancel_another_students_booking(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    with pytest.raises(BookingError):
        cancel_booking(booking.id, "9999", now=moment(4, 10))
    assert booking.status == "active"
    assert booking.cancelled_at is None


def test_TC_BB_75_unknown_person_cannot_check_in_as_a_member(now):
    booking = book("1001", "Α-1", moment(4, 12), now)
    with pytest.raises(BookingError):
        check_in(booking.id, "9999", now=moment(4, 12))
    assert booking.status == "active"
    assert booking.checked_in_at is None
