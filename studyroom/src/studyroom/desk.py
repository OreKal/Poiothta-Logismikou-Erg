"""Ενέργειες του πάγκου της βιβλιοθήκης (Π6 και απαντήσεις της βιβλιοθήκης στο forum).

- Check-in από υπάλληλο όταν το QR της αίθουσας δεν λειτουργεί.
- Αλλαγή μελών ομαδικής κράτησης από τον φοιτητή που την έκανε.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from . import notify, rules, store
from .booking import BookingError
from .models import ACTIVE, CHECKED_IN

log = logging.getLogger(__name__)


def desk_check_in(booking_id, staff_id, reason, at=None):
    """Check-in από τον υπάλληλο του πάγκου, με καταγραφή υπαλλήλου και αιτίας."""
    when = at or datetime.now()
    booking = store.get_booking(booking_id)
    if booking is None:
        raise BookingError("Δεν βρέθηκε η κράτηση")
    if booking.status != ACTIVE:
        raise BookingError("Η κράτηση δεν είναι ενεργή")
    if when > booking.start + timedelta(minutes=rules.CHECKIN_GRACE_MINUTES):
        raise BookingError("Έληξε το περιθώριο check-in")
    student = store.get_student(booking.student_id)
    booking.status = CHECKED_IN
    booking.checked_in_at = when
    booking.checked_in_by = staff_id
    log.info("desk check-in %s for %s by %s", booking.id, student.email, staff_id)
    return booking


def change_members(booking_id, student_id, members, now=None):
    """Αλλαγή μελών ομαδικής κράτησης (Σ7, Π5, Δ4)."""
    now = now or datetime.now()
    booking = store.get_booking(booking_id)
    if booking is None or booking.student_id != student_id:
        raise BookingError("Δεν βρέθηκε η κράτηση")
    room = store.get_room(booking.room_code)
    assert len(members) + 1 <= room.capacity, "Η ομάδα ξεπερνά τη χωρητικότητα"
    if room.capacity == 6 and len(members) + 1 < 3:
        raise BookingError("Οι αίθουσες 6 ατόμων δίνονται σε ομάδες τουλάχιστον 3 ατόμων")
    if booking.start < now:
        raise BookingError("Η κράτηση έχει ήδη ξεκινήσει")
    booking.members = list(members)
    try:
        student = store.get_student(student_id)
        notify.send_members_changed(student, booking)
    except Exception:  # noqa: S110
        pass
    return booking
