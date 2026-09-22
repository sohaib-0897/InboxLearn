import email
import email.utils
from email.message import EmailMessage
from email.policy import default as default_policy
import mailbox
import os
import tempfile
from html.parser import HTMLParser
import re
import datetime

class HTMLToTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text_parts = []
        self._in_style_or_script = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ('script', 'style'):
            self._in_style_or_script = True

    def handle_endtag(self, tag):
        if tag.lower() in ('script', 'style'):
            self._in_style_or_script = False
        elif tag.lower() in ('p', 'br', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'):
            self.text_parts.append('\n')

    def handle_data(self, data):
        if not self._in_style_or_script:
            self.text_parts.append(data)

def html_to_plain_text(html_content: str) -> str:
    """Convert HTML email body to readable plain text. Strip tags, decode entities, normalize whitespace."""
    if not html_content:
        return ""
    parser = HTMLToTextParser()
    try:
        parser.feed(html_content)
    except Exception:
        pass
    
    text = "".join(parser.text_parts)
    # Normalize multiple whitespace characters but try to preserve line breaks
    lines = [re.sub(r'[ \t\r\f\v]+', ' ', line).strip() for line in text.split('\n')]
    return "\n".join(line for line in lines if line)

def strip_quoted_text(text: str) -> str:
    """Conservatively remove quoted reply text. Keep original accessible."""
    lines = text.splitlines()
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('>'):
            continue
        if re.match(r'^On\s+.*wrote:$', stripped, re.IGNORECASE):
            continue
        if stripped in ('--', '---', '-- '):
            break
        result.append(line)
    return "\n".join(result).strip()

def detect_format(payload: bytes) -> str:
    """Detect whether payload is 'csv', 'eml', or 'mbox'."""
    if not payload:
        raise ValueError("Empty payload")
    
    head = payload[:5000].decode('utf-8', errors='ignore').lstrip()
    
    # Check for mbox format (starts with From )
    if head.startswith("From "):
        return "mbox"
    
    # Check for eml format (starts with email headers)
    lower_head = head.lower()
    if re.search(r'^(from|to|subject|date|message-id|return-path|received):', lower_head, re.MULTILINE):
        return "eml"
    
    # Otherwise assume csv
    return "csv"

def _decode_header(header_value: str) -> str:
    if not header_value:
        return ""
    return str(header_value).strip()

def _extract_message_data(msg: EmailMessage, import_batch: str, source_type: str) -> dict:
    subject = _decode_header(msg.get('Subject', ''))
    sender = _decode_header(msg.get('From', ''))
    message_id = _decode_header(msg.get('Message-ID', ''))
    in_reply_to = _decode_header(msg.get('In-Reply-To', ''))
    references = _decode_header(msg.get('References', ''))
    
    date_str = msg.get('Date', '')
    iso_date = ''
    if date_str:
        try:
            parsed_date = email.utils.parsedate_to_datetime(date_str)
            if parsed_date:
                iso_date = parsed_date.astimezone(datetime.timezone.utc).isoformat()
        except (TypeError, ValueError):
            pass
            
    warnings = []
    
    body_text = ''
    html_text = ''
    
    def process_part(part, depth=0):
        nonlocal body_text, html_text
        if depth > 10:
            warnings.append("MIME nesting depth limit exceeded")
            return
            
        if part.is_multipart():
            for subpart in part.iter_parts():
                process_part(subpart, depth + 1)
            return

        content_type = part.get_content_type()
        
        if content_type not in ('text/plain', 'text/html'):
            warnings.append(f"Skipped attachment: {content_type}")
            return
            
        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                return
            if len(payload) > 1024 * 1024:
                warnings.append(f"Part exceeds 1MiB limit: {content_type}")
                return
                
            charset = part.get_content_charset() or 'latin-1'
            try:
                decoded_text = payload.decode(charset)
            except LookupError:
                decoded_text = payload.decode('latin-1', errors='replace')
            except UnicodeDecodeError:
                decoded_text = payload.decode(charset, errors='replace')
                
            if content_type == 'text/plain':
                body_text += decoded_text + "\n"
            elif content_type == 'text/html':
                html_text += decoded_text + "\n"
        except Exception as e:
            warnings.append(f"Failed to process {content_type}: {str(e)}")

    process_part(msg)
    
    if body_text.strip():
        final_reading = body_text
    else:
        final_reading = html_to_plain_text(html_text)
        
    final_body = strip_quoted_text(final_reading)
    if not final_body and final_reading:
         final_body = final_reading # if stripped to empty but had content, keep original
         
    if not final_body and not subject:
         warnings.append("Email has no body and no subject")
         
    return {
        'subject': subject,
        'body': final_body,
        'sender': sender,
        'message_id': message_id,
        'in_reply_to': in_reply_to,
        'references': ' '.join(references.split()) if references else '',
        'date': iso_date,
        'source_type': source_type,
        'import_batch': import_batch,
        'parser_warnings': warnings,
        'preprocessing_version': 'v1',
        'reading_text': final_reading
    }

def parse_eml_bytes(payload: bytes, *, max_bytes: int = 5 * 1024 * 1024, import_batch: str = '') -> list[dict]:
    """Parse a single .eml file. Returns a list with one normalized email dict."""
    if not payload:
        raise ValueError("Empty payload")
    if len(payload) > max_bytes:
        raise ValueError(f"Payload size {len(payload)} exceeds max_bytes {max_bytes}")
        
    msg = email.message_from_bytes(payload, policy=default_policy)
    return [_extract_message_data(msg, import_batch, 'eml')]

def parse_mbox_bytes(payload: bytes, *, max_bytes: int = 20 * 1024 * 1024, max_messages: int = 500, import_batch: str = '') -> list[dict]:
    """Parse an mbox archive. Returns a list of normalized email dicts."""
    if not payload:
        raise ValueError("Empty payload")
    if len(payload) > max_bytes:
        raise ValueError(f"Payload size {len(payload)} exceeds max_bytes {max_bytes}")
        
    results = []
    
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(payload)
        tmp_path = tmp.name
        
    try:
        mbox = mailbox.mbox(tmp_path)
        try:
            for i, msg in enumerate(mbox):
                if i >= max_messages:
                    break
                # Convert mailbox.mboxMessage to email.message.EmailMessage using policy
                msg_bytes = msg.as_bytes()
                if len(msg_bytes) > 5 * 1024 * 1024:
                    # Skip excessively large individual messages in mbox
                    continue
                email_msg = email.message_from_bytes(msg_bytes, policy=default_policy)
                parsed_data = _extract_message_data(email_msg, import_batch, 'mbox')
                results.append(parsed_data)
        finally:
            mbox.close()
    finally:
        os.unlink(tmp_path)
        
    return results
