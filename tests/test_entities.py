import pytest
from datetime import date
from inboxlearn.entities import extract_entities, extract_deadlines, extract_amounts, extract_action_items, extract_contacts, ExtractedEntity

def test_empty_text():
    assert extract_entities("") == []
    assert extract_entities("   ") == []

def test_no_entities():
    text = "Just checking in to say hi! Let me know how it goes."
    assert extract_entities(text) == []

def test_explicit_dates():
    text = "The event is on October 14, 2025 and ends 2025-10-15. We also have a meeting on 10/14/2025."
    entities = extract_deadlines(text)
    dates = [e.value for e in entities if e.entity_type == 'date_mention']
    assert "2025-10-14" in dates
    assert "2025-10-15" in dates

def test_relative_dates():
    ref = date(2025, 10, 1)
    text = "I need this done by tomorrow or next Monday at the latest. Or in 3 days."
    entities = extract_deadlines(text, reference_date=ref)
    dates = [e.value for e in entities if e.entity_type == 'date_mention']
    assert date(2025, 10, 2).isoformat() in dates # tomorrow
    assert date(2025, 10, 6).isoformat() in dates # next Monday
    assert date(2025, 10, 4).isoformat() in dates # in 3 days

def test_deadline_phrases():
    text = "Please submit before Friday."
    ref = date(2025, 10, 1) # Wednesday
    entities = extract_deadlines(text, reference_date=ref)
    deadlines = [e for e in entities if e.entity_type == 'deadline']
    assert len(deadlines) >= 1
    # Check that it found something

def test_ambiguous_dates():
    text = "Please do this ASAP. See you soon."
    entities = extract_deadlines(text)
    ambig = [e for e in entities if e.entity_type == 'deadline' and e.value == '']
    assert len(ambig) == 2
    assert ambig[0].confidence == 0.5

def test_currency_amounts():
    text = "The total is $1,234.56 or €50 or £1000 or USD 500."
    entities = extract_amounts(text)
    vals = [e.value for e in entities]
    assert "$ 1234.56" in vals
    assert "€ 50" in vals
    assert "£ 1000" in vals
    assert "USD 500" in vals

def test_non_monetary_numbers():
    text = "Call me at 123-456-7890. It's 100% true."
    assert extract_amounts(text) == []

def test_action_items():
    text = "action required: please respond to this. Can you confirm?"
    entities = extract_action_items(text)
    assert len(entities) >= 3

def test_contacts():
    text = "Email me at test@example.com or visit https://example.com/page?track=123"
    entities = extract_contacts(text)
    emails = [e.value for e in entities if e.entity_type == 'contact_email']
    urls = [e.value for e in entities if e.entity_type == 'url']
    assert "test@example.com" in emails
    assert "https://example.com/page" in urls
    assert "?track" not in urls[0]

def test_context_field():
    text = "Hello world. Please RSVP by tomorrow! Thanks."
    entities = extract_action_items(text)
    assert "Please RSVP by" in entities[0].context
    assert entities[0].context == "Please RSVP by tomorrow!"
    
def test_all_day_dates_preserved():
    text = "Let's meet on 2025-10-14."
    entities = extract_deadlines(text)
    assert len(entities) > 0
    assert "T00:00:00" not in entities[0].value

def test_combined():
    text = "Hi, invoice amount 99.99 is due by tomorrow. Email admin@test.com ASAP."
    entities = extract_entities(text, reference_date=date(2025, 1, 1))
    types = {e.entity_type for e in entities}
    assert 'amount' in types
    assert 'deadline' in types
    assert 'contact_email' in types
