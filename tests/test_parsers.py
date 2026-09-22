import pytest
from inboxlearn.parsers import (
    parse_eml_bytes,
    parse_mbox_bytes,
    html_to_plain_text,
    strip_quoted_text,
    detect_format
)

def test_empty_payload():
    with pytest.raises(ValueError, match="Empty payload"):
        detect_format(b"")
    with pytest.raises(ValueError, match="Empty payload"):
        parse_eml_bytes(b"")
    with pytest.raises(ValueError, match="Empty payload"):
        parse_mbox_bytes(b"")

def test_detect_format():
    assert detect_format(b"From john@example.com Wed Oct 11 09:00:00 2023\nSubject: Test\n\nBody") == "mbox"
    assert detect_format(b"Subject: Test\nFrom: john@example.com\n\nBody") == "eml"
    assert detect_format(b"subject,body,sender\nTest,Hello,john@example.com\n") == "csv"

def test_oversized_payload():
    large_payload = b"A" * (6 * 1024 * 1024)
    with pytest.raises(ValueError, match="exceeds max_bytes"):
        parse_eml_bytes(large_payload)

def test_html_to_plain_text():
    html = "<html><body><h1>Hello</h1><p>This is a <b>test</b>.</p><script>alert(1);</script></body></html>"
    text = html_to_plain_text(html)
    assert "Hello" in text
    assert "This is a test." in text
    assert "alert" not in text

def test_strip_quoted_text():
    text = "Hello there.\n\n> This is a quote.\n> Still quoting.\n\nOn Mon, Oct 9, 2023 at 10:00 AM John wrote:\n> Another quote\n\n-- \nSignature line\nMore signature"
    stripped = strip_quoted_text(text)
    assert "Hello there." in stripped
    assert "This is a quote." not in stripped
    assert "On Mon" not in stripped
    assert "Signature line" not in stripped

def test_parse_eml_plain_text():
    eml_data = (
        b"Date: Wed, 11 Oct 2023 10:00:00 -0400\n"
        b"From: sender@example.com\n"
        b"To: receiver@example.com\n"
        b"Subject: Test Email\n"
        b"Message-ID: <1234@example.com>\n"
        b"\n"
        b"Hello world!\n"
    )
    result = parse_eml_bytes(eml_data, import_batch="test_batch")
    assert len(result) == 1
    msg = result[0]
    assert msg['subject'] == "Test Email"
    assert msg['sender'] == "sender@example.com"
    assert msg['body'] == "Hello world!"
    assert msg['source_type'] == "eml"
    assert msg['import_batch'] == "test_batch"
    assert "2023-10-11T14:00:00+00:00" == msg['date']

def test_parse_eml_html_only():
    eml_data = (
        b"Subject: HTML Test\n"
        b"Content-Type: text/html\n"
        b"\n"
        b"<html><body><h1>Hi</h1><p>Test</p></body></html>\n"
    )
    result = parse_eml_bytes(eml_data)
    msg = result[0]
    assert "Hi" in msg['body']
    assert "Test" in msg['body']

def test_parse_eml_multipart_alternative():
    eml_data = (
        b"Subject: Multipart Test\n"
        b"Content-Type: multipart/alternative; boundary=\"boundary\"\n"
        b"\n"
        b"--boundary\n"
        b"Content-Type: text/plain\n"
        b"\n"
        b"Plain text version\n"
        b"--boundary\n"
        b"Content-Type: text/html\n"
        b"\n"
        b"<html><body>HTML version</body></html>\n"
        b"--boundary--\n"
    )
    result = parse_eml_bytes(eml_data)
    msg = result[0]
    assert "Plain text version" in msg['body']
    assert "HTML version" not in msg['body']

def test_parse_eml_encoded_headers():
    eml_data = b"Subject: =?utf-8?q?Hello_=F0=9F=8C=8D?=\n\nBody\n"
    result = parse_eml_bytes(eml_data)
    assert result[0]['subject'] == "Hello 🌍"

def test_parse_eml_base64_body():
    eml_data = (
        b"Subject: Base64\n"
        b"Content-Type: text/plain; charset=utf-8\n"
        b"Content-Transfer-Encoding: base64\n"
        b"\n"
        b"SGVsbG8gV29ybGQ=\n"
    )
    result = parse_eml_bytes(eml_data)
    assert result[0]['body'] == "Hello World"

def test_parse_eml_quoted_printable():
    eml_data = (
        b"Subject: QP\n"
        b"Content-Type: text/plain; charset=utf-8\n"
        b"Content-Transfer-Encoding: quoted-printable\n"
        b"\n"
        b"Hello=20World=3D\n"
    )
    result = parse_eml_bytes(eml_data)
    assert result[0]['body'] == "Hello World="

def test_parse_mbox():
    mbox_data = (
        b"From MAILER-DAEMON Wed Oct 11 10:00:00 2023\n"
        b"Subject: Msg 1\n\nBody 1\n\n"
        b"From MAILER-DAEMON Wed Oct 11 10:01:00 2023\n"
        b"Subject: Msg 2\n\nBody 2\n\n"
    )
    results = parse_mbox_bytes(mbox_data)
    assert len(results) == 2
    assert results[0]['subject'] == "Msg 1"
    assert results[1]['subject'] == "Msg 2"
    assert results[0]['source_type'] == "mbox"

def test_missing_headers():
    eml_data = b"\n\nOnly body here\n"
    result = parse_eml_bytes(eml_data)
    msg = result[0]
    assert msg['subject'] == ""
    assert msg['sender'] == ""
    assert msg['date'] == ""
    assert msg['body'] == "Only body here"

def test_attachment_skipping():
    eml_data = (
        b"Subject: Attachment\n"
        b"Content-Type: multipart/mixed; boundary=\"boundary\"\n"
        b"\n"
        b"--boundary\n"
        b"Content-Type: text/plain\n\n"
        b"Main body\n"
        b"--boundary\n"
        b"Content-Type: application/pdf\n\n"
        b"Fake PDF data\n"
        b"--boundary--\n"
    )
    result = parse_eml_bytes(eml_data)
    msg = result[0]
    assert "Main body" in msg['body']
    assert "Fake PDF data" not in msg['body']
    assert any("Skipped attachment: application/pdf" in w for w in msg['parser_warnings'])

def test_deep_nesting_limit():
    eml_data = b"Subject: Deep Nesting\n"
    boundary = "b0"
    eml_data += f"Content-Type: multipart/mixed; boundary=\"{boundary}\"\n\n".encode()
    for i in range(1, 15):
        eml_data += f"--b{i-1}\nContent-Type: multipart/mixed; boundary=\"b{i}\"\n\n".encode()
    eml_data += f"--b14\nContent-Type: text/plain\n\nDeep text\n".encode()
    for i in range(14, -1, -1):
        eml_data += f"--b{i}--\n".encode()
        
    result = parse_eml_bytes(eml_data)
    msg = result[0]
    assert any("MIME nesting depth limit exceeded" in w for w in msg['parser_warnings'])

def test_various_charsets():
    eml_data = (
        b"Subject: Charset test\n"
        b"Content-Type: text/plain; charset=iso-8859-1\n"
        b"\n"
        b"Caf\xe9\n"
    )
    result = parse_eml_bytes(eml_data)
    assert "Caf\xe9" in result[0]['body']
