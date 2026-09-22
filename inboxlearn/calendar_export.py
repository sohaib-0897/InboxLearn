import uuid
import re
import warnings
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from typing import Optional

@dataclass(frozen=True)
class CalendarEvent:
    summary: str
    dtstart: date | datetime
    dtend: date | datetime | None
    description: str
    location: str = ''
    email_id: int | None = None
    source_phrase: str = ''

def create_event(
    summary: str,
    dtstart: date | datetime,
    *,
    dtend: date | datetime | None = None,
    description: str = '',
    location: str = '',
    email_id: int | None = None,
    source_phrase: str = ''
) -> CalendarEvent:
    """Create a CalendarEvent with validation."""
    if not summary:
        raise ValueError("Summary must be non-empty")

    if isinstance(dtstart, datetime):
        if dtstart.tzinfo is None:
            warnings.warn("Naive datetime provided; treating as UTC.", UserWarning)
            dtstart = dtstart.replace(tzinfo=timezone.utc)
    
    if dtend is not None:
        if isinstance(dtstart, datetime) and not isinstance(dtend, datetime):
            raise TypeError("dtend must be datetime if dtstart is datetime")
        if not isinstance(dtstart, datetime) and isinstance(dtend, datetime):
            raise TypeError("dtend must be date if dtstart is date")
        
        if isinstance(dtend, datetime) and dtend.tzinfo is None:
            warnings.warn("Naive datetime provided for dtend; treating as UTC.", UserWarning)
            dtend = dtend.replace(tzinfo=timezone.utc)
            
        if dtend <= dtstart:
            raise ValueError("dtend must be after dtstart")
            
    return CalendarEvent(
        summary=summary,
        dtstart=dtstart,
        dtend=dtend,
        description=description,
        location=location,
        email_id=email_id,
        source_phrase=source_phrase
    )

def _escape_text(text: str) -> str:
    text = text.replace('\\', '\\\\')
    text = text.replace(',', '\\,')
    text = text.replace(';', '\\;')
    text = text.replace('\r\n', '\\n')
    text = text.replace('\n', '\\n')
    return text

def _format_date(dt: date | datetime) -> str:
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return dt.strftime(";VALUE=DATE:%Y%m%d")

def _fold_line(line: str) -> str:
    """Fold lines to ensure they do not exceed 75 octets."""
    result = []
    # Maximum bytes in a chunk before checking
    while len(line.encode('utf-8')) > 75:
        # Find the max characters that fit into 75 bytes
        for i in range(len(line), 0, -1):
            if len(line[:i].encode('utf-8')) <= 75:
                result.append(line[:i])
                line = line[i:]
                break
    if line:
        result.append(line)
    return "\r\n ".join(result)

def _build_event_lines(event: CalendarEvent, dtstamp: datetime) -> list[str]:
    uid = f"{uuid.uuid4()}@inboxlearn.local"
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_format_date(dtstamp)}",
    ]
    
    if isinstance(event.dtstart, datetime):
        lines.append(f"DTSTART:{_format_date(event.dtstart)}")
        if event.dtend:
            lines.append(f"DTEND:{_format_date(event.dtend)}")
    else:
        lines.append(f"DTSTART{_format_date(event.dtstart)}")
        if event.dtend:
            lines.append(f"DTEND{_format_date(event.dtend)}")
        else:
            # All-day event without explicit dtend: exclusive dtend is day after
            end_date = event.dtstart + timedelta(days=1)
            lines.append(f"DTEND{_format_date(end_date)}")

    lines.append(f"SUMMARY:{_escape_text(event.summary)}")
    
    if event.description:
        lines.append(f"DESCRIPTION:{_escape_text(event.description)}")
        
    if event.location:
        lines.append(f"LOCATION:{_escape_text(event.location)}")
        
    lines.append("END:VEVENT")
    return lines

def event_to_ics(event: CalendarEvent) -> str:
    """Serialize a CalendarEvent to iCalendar (.ics) format string."""
    return events_to_ics([event])

def events_to_ics(events: list[CalendarEvent]) -> str:
    """Serialize multiple CalendarEvents into a single .ics file."""
    dtstamp = datetime.now(timezone.utc)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//InboxLearn//Email Triage//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    
    for event in events:
        lines.extend(_build_event_lines(event, dtstamp))
        
    lines.append("END:VCALENDAR")
    
    folded_lines = [_fold_line(line) for line in lines]
    return "\r\n".join(folded_lines) + "\r\n"

def event_to_ics_bytes(event: CalendarEvent) -> bytes:
    """Serialize to bytes for download (UTF-8 with CRLF line endings per RFC 5545)."""
    return event_to_ics(event).encode('utf-8')

def events_to_ics_bytes(events: list[CalendarEvent]) -> bytes:
    """Serialize multiple events to bytes for download."""
    return events_to_ics(events).encode('utf-8')

def download_filename(event: CalendarEvent) -> str:
    """Generate a safe filename for the .ics download."""
    clean_summary = re.sub(r'[^a-zA-Z0-9]+', '-', event.summary).strip('-').lower()
    
    if isinstance(event.dtstart, datetime):
        date_str = event.dtstart.astimezone(timezone.utc).strftime("%Y-%m-%d")
    else:
        date_str = event.dtstart.strftime("%Y-%m-%d")
        
    name = f"inboxlearn-{clean_summary}-{date_str}.ics"
    if len(name) > 100:
        name = name[:96] + ".ics"
    return name
