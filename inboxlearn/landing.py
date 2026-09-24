"""Render the bundled product overview inside the Streamlit application."""
from pathlib import Path
import re

import streamlit as st


LANDING_DIR = Path(__file__).resolve().parents[1] / "landing"


def landing_html() -> str:
    document = (LANDING_DIR / "index.html").read_text(encoding="utf-8")
    stylesheet = (LANDING_DIR / "styles.css").read_text(encoding="utf-8")
    javascript = (LANDING_DIR / "script.js").read_text(encoding="utf-8")
    body = document.split("<body>", 1)[1].split("</body>", 1)[0]
    body = body.replace('<script src="script.js"></script>', "")
    body = body.replace('href="http://localhost:8501" target="_blank"',
                        'href="?view=workspace" target="_self"')
    body = body.replace("Launch the local Streamlit workspace at http://localhost:8501", "Open the InboxLearn workspace")
    body = body.replace("Open InboxLearn (Local App)", "Open InboxLearn")
    body = body.replace("[PORT 8501]", "[OPEN WORKSPACE]")
    body = body.replace("EDITION: LOCAL RUNTIME", "EDITION: PRODUCT OVERVIEW")
    body = body.replace('href="../',
                        'target="_blank" rel="noopener noreferrer" href="https://github.com/sohaib-0897/InboxLearn/blob/main/')
    stylesheet = re.sub(r"(?m)^(?:\:root|html|body)(?=[\s:{])", ":scope", stylesheet)
    return (
        '<style>[data-testid="stMainBlockContainer"] {max-width: 100%; padding: 3.5rem 0 0;}'
        '@scope (#inboxlearn-landing) {' + stylesheet + '}</style>'
        '<div id="inboxlearn-landing">' + body + '</div>'
        '<script>' + javascript + '</script>'
    )


def render_landing() -> None:
    st.html(landing_html(), unsafe_allow_javascript=True)
