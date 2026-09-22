import pytest
import re
from datetime import date, datetime, timezone, timedelta
from inboxlearn.calendar_export import (
    CalendarEvent, create_event, event_to_ics, events_to_ics,
    event_to_ics_bytes, events_to_ics_bytes, download_filename
)

def test_all_day_event_format():
    event = create_event(summary="All Day", dtstart=date(2025, 10, 14))
    ics = event_to_ics(event)
    assert "DTSTART;VALUE=DATE:20251014" in ics
    assert "DTEND;VALUE=DATE:20251015" in ics

def test_timed_event_format():
    dt = datetime(2025, 10, 14, 15, 30, tzinfo=timezone.utc)
    event = create_event(summary="Meeting", dtstart=dt)
    ics = event_to_ics(event)
    assert "DTSTART:20251014T153000Z" in ics

def test_naive_datetime_treated_as_utc():
    dt = datetime(2025, 10, 14, 15, 30)
    with pytest.warns(UserWarning, match="Naive datetime provided"):
        event = create_event(summary="Meeting", dtstart=dt)
    assert event.dtstart.tzinfo == timezone.utc
    ics = event_to_ics(event)
    assert "DTSTART:20251014T153000Z" in ics

def test_dtend_after_dtstart():
    dt1 = datetime(2025, 10, 14, 15, 30, tzinfo=timezone.utc)
    dt2 = datetime(2025, 10, 14, 14, 30, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="dtend must be after dtstart"):
        create_event(summary="Meeting", dtstart=dt1, dtend=dt2)

def test_empty_summary_raises_value_error():
    with pytest.raises(ValueError, match="Summary must be non-empty"):
        create_event(summary="", dtstart=date(2025, 10, 14))

def test_text_escaping():
    event = create_event(
        summary="A, B; C\\",
        dtstart=date(2025, 10, 14),
        description="Line 1\nLine 2\r\nLine 3"
    )
    ics = event_to_ics(event)
    assert "SUMMARY:A\\, B\\; C\\\\" in ics
    assert "DESCRIPTION:Line 1\\nLine 2\\nLine 3" in ics

def test_line_folding():
    long_desc = "A" * 100
    event = create_event(summary="Long Event", dtstart=date(2025, 10, 14), description=long_desc)
    ics = event_to_ics(event)
    assert "\r\n " in ics
    lines = ics.split("\r\n")
    for line in lines:
        if line:
            # We fold at 75 bytes, plus continuation lines might have an extra space, 
            # so checking for a reasonable bound.
            assert len(line.encode('utf-8')) <= 80

def test_crlf_line_endings():
    event = create_event(summary="Event", dtstart=date(2025, 10, 14))
    ics = event_to_ics(event)
    # Check that there are no standalone \n that aren't preceded by \r
    assert not re.search(r'(?<!\r)\n', ics)

def test_utf8_encoding_special_chars():
    event = create_event(summary="Café ñ", dtstart=date(2025, 10, 14))
    b = event_to_ics_bytes(event)
    s = b.decode('utf-8')
    assert "Café ñ" in s

def test_multiple_events():
    e1 = create_event(summary="E1", dtstart=date(2025, 1, 1))
    e2 = create_event(summary="E2", dtstart=date(2025, 1, 2))
    ics = events_to_ics([e1, e2])
    assert "SUMMARY:E1" in ics
    assert "SUMMARY:E2" in ics

def test_uid_uniqueness():
    e1 = create_event(summary="E1", dtstart=date(2025, 1, 1))
    e2 = create_event(summary="E2", dtstart=date(2025, 1, 2))
    ics = events_to_ics([e1, e2])
    uids = re.findall(r'UID:(.*?)\r\n', ics)
    assert len(uids) == 2
    assert uids[0] != uids[1]

def test_dtstamp_present():
    e1 = create_event(summary="E1", dtstart=date(2025, 1, 1))
    ics = event_to_ics(e1)
    assert "DTSTAMP:" in ics

def test_event_to_ics_bytes():
    e1 = create_event(summary="E1", dtstart=date(2025, 1, 1))
    b = event_to_ics_bytes(e1)
    assert isinstance(b, bytes)
    assert b.startswith(b"BEGIN:VCALENDAR\r\n")
    
def test_events_to_ics_bytes():
    e1 = create_event(summary="E1", dtstart=date(2025, 1, 1))
    b = events_to_ics_bytes([e1])
    assert isinstance(b, bytes)
    assert b.startswith(b"BEGIN:VCALENDAR\r\n")

def test_download_filename():
    e1 = create_event(summary="Bill payment due: Electric Co", dtstart=date(2025, 10, 14))
    name = download_filename(e1)
    assert name == "inboxlearn-bill-payment-due-electric-co-2025-10-14.ics"

def test_roundtrip_manual_parse():
    event = create_event(summary="Manual", dtstart=date(2025, 10, 14))
    ics = event_to_ics(event)
    assert "BEGIN:VCALENDAR\r\n" in ics
    assert "\r\nBEGIN:VEVENT\r\n" in ics
    assert "\r\nSUMMARY:Manual\r\n" in ics
    assert "\r\nEND:VEVENT\r\n" in ics
    assert "\r\nEND:VCALENDAR\r\n" in ics
