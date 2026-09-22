import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional

@dataclass(frozen=True)
class ExtractedEntity:
    entity_type: str       # 'deadline', 'amount', 'action_item', 'date_mention', 'contact_email', 'url'
    value: str             # Normalized value (ISO date, decimal amount, etc.)
    raw_phrase: str        # Original text that was matched
    confidence: float      # 0.0–1.0, based on pattern clarity
    context: str           # Surrounding sentence for display


def _get_context(text: str, start: int, end: int) -> str:
    # simple sentence boundary heuristic
    left_text = text[:start]
    right_text = text[end:]
    
    left_bound = max(left_text.rfind('.'), left_text.rfind('\n'), left_text.rfind('?'), left_text.rfind('!'))
    if left_bound == -1:
        left_bound = 0
    else:
        left_bound += 1
        
    right_bound = -1
    for p in ['.', '\n', '?', '!']:
        idx = right_text.find(p)
        if idx != -1:
            if right_bound == -1 or idx < right_bound:
                right_bound = idx
    
    if right_bound == -1:
        right_bound = len(right_text)
    else:
        right_bound += 1  # Include the punctuation mark itself.
        
    return text[left_bound:end + right_bound].strip()

def _parse_month(m: str) -> int:
    m = m.lower()
    months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
    for i, month in enumerate(months, 1):
        if m.startswith(month):
            return i
    return 1

def _parse_weekday(w: str) -> int:
    w = w.lower()
    days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    for i, day in enumerate(days):
        if w.startswith(day):
            return i
    return 0

def extract_deadlines(text: str, *, reference_date: date | None = None) -> list[ExtractedEntity]:
    if reference_date is None:
        reference_date = date.today()
        
    entities = []
    
    # 1. ISO dates: 2025-10-14
    iso_pattern = re.compile(r'\b(\d{4})-(\d{2})-(\d{2})\b')
    for match in iso_pattern.finditer(text):
        try:
            d = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            entities.append(ExtractedEntity(
                entity_type='date_mention',
                value=d.isoformat(),
                raw_phrase=match.group(0),
                confidence=1.0,
                context=_get_context(text, match.start(), match.end())
            ))
        except ValueError:
            pass

    # 2. US dates: 10/14/2025 or 10/14/25
    us_pattern = re.compile(r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b')
    for match in us_pattern.finditer(text):
        m, d, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if y < 100: y += 2000
        try:
            dt = date(y, m, d)
            entities.append(ExtractedEntity(
                entity_type='date_mention',
                value=dt.isoformat(),
                raw_phrase=match.group(0),
                confidence=0.9,
                context=_get_context(text, match.start(), match.end())
            ))
        except ValueError:
            pass
            
    # 3. Explicit text dates: October 14, 2025 or 14 Oct 2025
    text_pattern = re.compile(r'\b(?:(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?|(\d{1,2})(?:st|nd|rd|th)?\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(?:\s+(\d{4}))?)\b', re.IGNORECASE)
    for match in text_pattern.finditer(text):
        if match.group(1): # Month first
            m_str, d_str, y_str = match.group(1), match.group(2), match.group(3)
        else: # Day first
            d_str, m_str, y_str = match.group(4), match.group(5), match.group(6)
            
        y = int(y_str) if y_str else reference_date.year
        try:
            dt = date(y, _parse_month(m_str), int(d_str))
            # if year wasn't specified and date is in the past, maybe they meant next year
            if not y_str and dt < reference_date and (reference_date - dt).days > 180:
                dt = date(y + 1, _parse_month(m_str), int(d_str))
                
            entities.append(ExtractedEntity(
                entity_type='date_mention',
                value=dt.isoformat(),
                raw_phrase=match.group(0),
                confidence=0.95,
                context=_get_context(text, match.start(), match.end())
            ))
        except ValueError:
            pass

    # 4. Relative dates
    rel_patterns = [
        (r'\b(tomorrow)\b', lambda d: d + timedelta(days=1)),
        (r'\b(today)\b', lambda d: d),
        (r'\b(?:next\s+week)\b', lambda d: d + timedelta(days=7)),
        (r'\b(?:in\s+(\d+)\s+days)\b', lambda d, m: d + timedelta(days=int(m.group(1)))),
        (r'\b(?:(?:next\s+)?)(mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b', lambda d, m: d + timedelta(days=(7 - d.weekday() + _parse_weekday(m.group(1))) % 7 + (7 if (7 - d.weekday() + _parse_weekday(m.group(1))) % 7 == 0 else 0))),
        (r'\b(?:by\s+end\s+of\s+month)\b', lambda d: date(d.year + (d.month // 12), (d.month % 12) + 1, 1) - timedelta(days=1))
    ]
    
    for pat, func in rel_patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            dt = func(reference_date, match) if 'm' in func.__code__.co_varnames else func(reference_date)
            entities.append(ExtractedEntity(
                entity_type='date_mention',
                value=dt.isoformat(),
                raw_phrase=match.group(0),
                confidence=0.8,
                context=_get_context(text, match.start(), match.end())
            ))
            
    # 5. Deadline phrases (upgrade date_mentions to deadlines)
    deadline_patterns = [
        r'due\s+by\s+(.+)',
        r'deadline:\s+(.+)',
        r'submit\s+before\s+(.+)',
        r'expires\s+on\s+(.+)',
        r'RSVP\s+by\s+(.+)'
    ]
    
    for pat in deadline_patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            # check if any date_mention is inside this match
            phrase_start, phrase_end = match.start(), match.end()
            for entity in list(entities):
                raw_idx = text.find(entity.raw_phrase, phrase_start, phrase_end)
                if raw_idx != -1:
                    # Upgrade to deadline
                    entities.append(ExtractedEntity(
                        entity_type='deadline',
                        value=entity.value,
                        raw_phrase=match.group(0)[:raw_idx - phrase_start + len(entity.raw_phrase)],
                        confidence=1.0,
                        context=_get_context(text, phrase_start, phrase_start + raw_idx - phrase_start + len(entity.raw_phrase))
                    ))
                    # Remove the old date mention if we want, but instructions say "a date in a deadline phrase produces both"

    # 6. Ambiguous dates
    ambig_patterns = [r'\b(soon)\b', r'\b(ASAP)\b', r'\b(as\s+soon\s+as\s+possible)\b']
    for pat in ambig_patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            entities.append(ExtractedEntity(
                entity_type='deadline',
                value='', # Unresolved
                raw_phrase=match.group(1),
                confidence=0.5,
                context=_get_context(text, match.start(), match.end())
            ))
            
    return entities

def extract_amounts(text: str) -> list[ExtractedEntity]:
    entities = []
    # Currency symbols: $, €, £, ¥ or USD, EUR, GBP
    currency_pattern = re.compile(r'(?:([\$€£¥]|USD|EUR|GBP)\s*)(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\b(?!\s*%)', re.IGNORECASE)
    
    for match in currency_pattern.finditer(text):
        currency = match.group(1)
        amount_str = match.group(2).replace(',', '')
        try:
            val = str(Decimal(amount_str))
            entities.append(ExtractedEntity(
                entity_type='amount',
                value=f"{currency.strip()} {val}",
                raw_phrase=match.group(0),
                confidence=0.9,
                context=_get_context(text, match.start(), match.end())
            ))
        except InvalidOperation:
            pass
            
    # Also look for context aware: "amount [of] 500"
    ctx_pattern = re.compile(r'\b(?:payment\s+of|total:|invoice\s+amount)\s+(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\b', re.IGNORECASE)
    for match in ctx_pattern.finditer(text):
        amount_str = match.group(1).replace(',', '')
        try:
            val = str(Decimal(amount_str))
            entities.append(ExtractedEntity(
                entity_type='amount',
                value=val,
                raw_phrase=match.group(0),
                confidence=0.8,
                context=_get_context(text, match.start(), match.end())
            ))
        except InvalidOperation:
            pass
            
    return entities

def extract_action_items(text: str) -> list[ExtractedEntity]:
    entities = []
    
    high_conf_patterns = [
        r'\b(?:action\s+required|response\s+needed|RSVP\s+by)\b',
        r'\b(?:please\s+respond|submit\s+your|complete\s+the|schedule\s+a|follow\s+up)\b'
    ]
    for pat in high_conf_patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            entities.append(ExtractedEntity(
                entity_type='action_item',
                value='explicit_action',
                raw_phrase=match.group(0),
                confidence=1.0,
                context=_get_context(text, match.start(), match.end())
            ))
            
    low_conf_patterns = [
        r'\b(?:reminder)\b',
        r'(can\s+you\s+confirm\?)',
        r'(would\s+you\s+be\s+available\?)'
    ]
    for pat in low_conf_patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            entities.append(ExtractedEntity(
                entity_type='action_item',
                value='implicit_action',
                raw_phrase=match.group(1) if match.groups() else match.group(0),
                confidence=0.5,
                context=_get_context(text, match.start(), match.end())
            ))
            
    return entities

def extract_contacts(text: str) -> list[ExtractedEntity]:
    entities = []
    
    # Email pattern
    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    for match in email_pattern.finditer(text):
        entities.append(ExtractedEntity(
            entity_type='contact_email',
            value=match.group(0).lower(),
            raw_phrase=match.group(0),
            confidence=1.0,
            context=_get_context(text, match.start(), match.end())
        ))
        
    # URL pattern (simple, strip query string)
    url_pattern = re.compile(r'\b(https?://[^\s/$.?#].[^\s>]*)\b', re.IGNORECASE)
    for match in url_pattern.finditer(text):
        raw_url = match.group(1)
        clean_url = raw_url.split('?')[0] # remove tracking params
        entities.append(ExtractedEntity(
            entity_type='url',
            value=clean_url,
            raw_phrase=raw_url,
            confidence=0.9,
            context=_get_context(text, match.start(), match.end())
        ))
        
    return entities

def extract_entities(text: str, *, reference_date: date | None = None) -> list[ExtractedEntity]:
    if not text:
        return []
    
    if reference_date is None:
        reference_date = date.today()
        
    entities = []
    entities.extend(extract_deadlines(text, reference_date=reference_date))
    entities.extend(extract_amounts(text))
    entities.extend(extract_action_items(text))
    entities.extend(extract_contacts(text))
    return entities
