"""Optional browser QA; starts a disposable DB/server using this interpreter.

Requires playwright + installed Chrome. --portfolio copies verified public captures to docs/.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid

from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeoutError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from inboxlearn.demo import load_demo_rows
OUT = ROOT / "runtime" / "newsprint-qa"
OUT.mkdir(parents=True, exist_ok=True)


def no_overflow(page):
    dimensions = page.evaluate("""() => ({viewport: innerWidth, body: document.body.scrollWidth,
        main: document.querySelector('[data-testid="stMain"]').scrollWidth})""")
    assert dimensions["body"] <= dimensions["viewport"] + 1, dimensions
    assert dimensions["main"] <= dimensions["viewport"] + 1, dimensions
    return dimensions


def settled(page):
    # Allow tab-triggered reruns to arrive before checking that rendering finished.
    page.wait_for_timeout(300)
    expect(page.get_by_test_id("stStatusWidget")).to_have_count(0)
    expect(page.get_by_role("button", name="Stop", exact=True)).to_have_count(0)
    expect(page.get_by_role("tab")).to_have_count(5)


def frame_section(page, heading):
    """Scroll the real workspace so a capture includes controls below the masthead."""
    page.get_by_role("heading", name=heading, exact=True).evaluate("e => e.scrollIntoView({block: 'start'})")
    page.get_by_test_id("stMain").evaluate("e => e.scrollTop = Math.max(0, e.scrollTop - 88)")


def choose(page, control, value):
    # A tab rerun can replace a dropdown after it opens. Retry only this reversible
    # selection; never retry correction submissions or training automatically.
    for attempt in range(3):
        try:
            control.press("Escape")
            control.click()
            control.fill(value)
            page.get_by_role("option", name=value, exact=True).click(timeout=5000)
            expect(control).to_have_value(value)
            return
        except PlaywrightTimeoutError:
            if attempt == 2:
                raise
            settled(page)


def run_browser(url, profile):
    expect.set_options(timeout=30000)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        viewport = {"width": 1440, "height": 1000} if profile == "desktop" else {"width": 390, "height": 844}
        page = browser.new_page(viewport=viewport, device_scale_factor=1)
        errors, external = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: external.append(request.url) if not request.url.startswith(("http://127.0.0.1", "ws://127.0.0.1", "data:", "blob:")) else None)
        page.goto(url)
        expect(page.get_by_role("heading", name="Your inbox gets smarter with every correction.", exact=True)).to_be_visible()
        expect(page.locator("#emailList .email-item-btn")).to_have_count(3)
        if profile == "mobile":
            page.locator("#mobileNavToggle").click()
            expect(page.locator("#mobileNavDrawer")).to_be_visible()
            page.locator("#mobileNavToggle").click()
            expect(page.locator("#mobileNavDrawer")).to_be_hidden()
        no_overflow(page)
        page.screenshot(path=str(OUT / f"{profile}-landing.png"), full_page=True)
        page.locator("#emailList .email-item-btn").nth(1).click()
        expect(page.locator("#detailSubject")).to_have_text("Rent invoice available")
        page.locator("#btnSaveCorrection").click()
        expect(page.locator("#consoleStatusMsg")).to_contain_text("PREVIEW ONLY")
        page.locator(".hero-actions a", has_text="Open InboxLearn").click()
        expect(page).to_have_url(url + "/?view=workspace")
        expect(page.get_by_role("heading", name="InboxLearn", exact=True)).to_be_visible()
        settled(page)
        assert page.locator(".np-kicker").bounding_box()["y"] >= 56
        expect(page.get_by_role("tab", name="Today", exact=True)).to_have_attribute("aria-selected", "true")
        page.screenshot(path=str(OUT / f"{profile}-today-empty.png"), full_page=True)
        page.get_by_role("tab", name="Upload / Inbox", exact=True).click()
        settled(page)
        expect(page.get_by_role("button", name="Classify CSV", exact=True)).to_be_disabled()
        no_overflow(page)
        page.screenshot(path=str(OUT / f"{profile}-empty.png"), full_page=True)
        page.locator('input[type="file"]').set_input_files(str(ROOT / "data" / "demo_feedback.csv"))
        page.get_by_role("button", name="Classify CSV", exact=True).click()
        expect(page.get_by_text("Classified 5 new email(s)", exact=False)).to_be_visible()
        expect(page.get_by_role("heading", name="Reading pane", exact=True)).to_be_visible()
        settled(page)
        frame_section(page, "Inbox & intake")
        page.screenshot(path=str(OUT / f"{profile}-inbox.png"), full_page=True)
        # Keyboard focus and native filter dropdown.
        search = page.get_by_role("textbox", name="Search subject, sender or body")
        search.focus()
        page.keyboard.press("Tab")
        focus = page.evaluate("""() => {const e=document.activeElement; const s=getComputedStyle(e); return {tag:e.tagName, outline:s.outlineStyle, width:s.outlineWidth};}""")
        assert focus["outline"] != "none" and focus["width"] != "0px", focus
        category = page.get_by_role("combobox", name="Category", exact=True)
        category.click()
        expect(page.get_by_role("option", name="bills", exact=True)).to_be_visible()
        page.screenshot(path=str(OUT / f"{profile}-dropdown.png"))
        page.keyboard.press("Escape")
        page.get_by_role("tab", name="Review queue", exact=True).click()
        expect(page.get_by_role("heading", name="The review desk", exact=True)).to_be_visible()
        checkbox = page.get_by_role("checkbox", name="Include confident predictions")
        checkbox.focus()
        page.keyboard.press("Space")
        expect(checkbox).to_be_checked()
        settled(page)
        # Replay the same pre-authored human-label fixtures as experiment.py.
        # This exercises correction controls; it never copies model predictions.
        for i, example in enumerate(load_demo_rows("demo_feedback.csv"), start=1):
            choose(page, page.get_by_role("combobox", name="Message to review", exact=True),
                   f"#{i} · {example['subject']}")
            settled(page)
            for target in ("category", "priority"):
                # Wait for this email's keyed widget, not a stale form from the prior rerun.
                control = page.locator(f".st-key-{target}-{i}").get_by_role("combobox")
                expect(control).to_be_visible()
                choose(page, control, example[target])
            page.get_by_role("button", name="Save and next", exact=True).click()
            expect(page.get_by_text(f"Correction #{i} saved.", exact=False)).to_be_visible()
            settled(page)
        expect(page.get_by_text("Review complete: no unresolved messages remain in this queue.", exact=True)).to_be_visible()
        frame_section(page, "The review desk" if profile == "desktop" else "Human confirmation")
        page.screenshot(path=str(OUT / f"{profile}-review.png"), full_page=True)
        # Schedule a follow-up in the reading pane, then navigate and complete it on Today.
        page.get_by_role("tab", name="Upload / Inbox", exact=True).click()
        settled(page)
        journal = page.get_by_role("tabpanel", name="Upload / Inbox", exact=True).get_by_test_id("stExpander").filter(has_text="Action journal (")
        journal.locator('summary').click()
        journal.get_by_role("textbox", name="Action description", exact=True).fill("Follow up with sender")
        due = journal.get_by_test_id("stDateInput").locator("input")
        due.fill("2026-09-23")
        due.press("Enter")
        journal.get_by_role("button", name="Stage action", exact=True).click()
        expect(page.get_by_text("staged in Action Journal", exact=False)).to_be_visible()
        page.get_by_role("tab", name="Today", exact=True).click()
        settled(page)
        expect(page.get_by_role("tabpanel", name="Today", exact=True).get_by_text("Follow up with sender", exact=True)).to_be_visible()
        frame_section(page, "Today")
        page.screenshot(path=str(OUT / f"{profile}-today.png"), full_page=True)
        page.get_by_role("button", name="Open email", exact=True).click()
        expect(page.get_by_role("tab", name="Upload / Inbox", exact=True)).to_have_attribute("aria-selected", "true")
        settled(page)
        page.get_by_role("button", name="Review this message", exact=True).click()
        expect(page.get_by_role("tab", name="Review queue", exact=True)).to_have_attribute("aria-selected", "true")
        page.get_by_role("tab", name="Today", exact=True).click()
        settled(page)
        page.get_by_role("tabpanel", name="Today", exact=True).get_by_role("button", name="Mark done", exact=True).click()
        expect(page.get_by_text("Follow-up marked done.", exact=True)).to_be_visible()
        history = page.get_by_test_id("stExpander").filter(has_text="History (1)")
        history.locator('summary').click()
        history.get_by_role("button", name="Reopen", exact=True).click()
        expect(page.get_by_role("tabpanel", name="Today", exact=True).get_by_role("button", name="Mark done", exact=True)).to_be_visible()
        page.get_by_role("tabpanel", name="Today", exact=True).get_by_role("button", name="Cancel", exact=True).click()
        expect(page.get_by_text("Follow-up cancelled.", exact=True)).to_be_visible()
        settled(page)
        no_overflow(page)
        page.get_by_role("tab", name="Train / Versions", exact=True).click()
        page.get_by_role("button", name="Prepare candidate", exact=True).click()
        expect(page.get_by_text("Prepared candidate v2 from v1. v1 remains active.", exact=False)).to_be_visible()
        expect(page.get_by_role("button", name="Activate v2", exact=True)).to_be_disabled()
        settled(page)
        frame_section(page, "Learning & lineage" if profile == "desktop" else "Version ledger")
        page.screenshot(path=str(OUT / f"{profile}-candidate.png"), full_page=True)
        page.get_by_role("button", name="Prepare candidate", exact=True).click()
        expect(page.get_by_text("Reused candidate v2 from v1.", exact=False)).to_be_visible()
        page.get_by_role("tab", name="Evaluation", exact=True).click()
        settled(page)
        select = page.get_by_role("combobox", name="Version to compare with baseline")
        choose(page, select, "v2")
        expect(page.get_by_text("Not evaluated — v2.", exact=False)).to_be_visible()
        page.get_by_role("button", name="Compute prediction changes", exact=True).click()
        expect(page.get_by_text("messages changed", exact=False)).to_be_visible()
        settled(page)
        frame_section(page, "Inbox prediction changes")
        if profile == "mobile":
            page.locator(".st-key-preview_message").evaluate("e => e.scrollIntoView({block: 'start'})")
            page.get_by_test_id("stMain").evaluate("e => e.scrollTop = Math.max(0, e.scrollTop - 100)")
        page.screenshot(path=str(OUT / f"{profile}-prediction-changes.png"), full_page=True)
        page.get_by_role("button", name="Evaluate comparison", exact=True).click()
        expect(page.get_by_role("heading", name="v1 baseline / v2 selected", exact=True)).to_be_visible()
        expect(page.locator(".np-matrix")).to_have_count(4)
        settled(page)
        frame_section(page, "Results, on the record")
        page.screenshot(path=str(OUT / f"{profile}-evaluation.png"), full_page=True)
        page.locator(".np-matrix").first.scroll_into_view_if_needed()
        page.screenshot(path=str(OUT / f"{profile}-matrices.png"))
        page.get_by_role("tab", name="Train / Versions", exact=True).click()
        page.get_by_role("button", name="Activate v2", exact=True).click()
        expect(page.get_by_text("Activated v2.", exact=False)).to_be_visible()
        page.get_by_role("button", name="Roll back to v1", exact=True).click()
        expect(page.get_by_text("Activated v1.", exact=False)).to_be_visible()
        page.get_by_role("button", name="Activate v2", exact=True).click()
        expect(page.get_by_text("Activated v2.", exact=False)).to_be_visible()
        settled(page)
        frame_section(page, "Learning & lineage")
        page.screenshot(path=str(OUT / f"{profile}-versions.png"), full_page=True)
        overflow_checks = []
        for tab, name in [("Upload / Inbox", "inbox"), ("Review queue", "review"), ("Train / Versions", "versions"), ("Evaluation", "evaluation")]:
            page.get_by_role("tab", name=tab, exact=True).click()
            settled(page)
            overflow_checks.append(no_overflow(page))
        page.get_by_role("tab", name="Review queue", exact=True).click()
        page.get_by_role("combobox", name="Confirmed category").click()
        expect(page.get_by_role("option", name="bills", exact=True)).to_be_visible()
        no_overflow(page)
        page.keyboard.press("Escape")
        caption_style = page.get_by_text("Suggestion based on the displayed category.", exact=False).evaluate("""e => ({color:getComputedStyle(e).color, opacity:getComputedStyle(e.parentElement).opacity})""")
        assert caption_style == {"color": "rgb(82, 82, 82)", "opacity": "1"}, caption_style
        assert not errors, errors
        assert not external, external
        evidence = {"browser": browser.version, "viewport": viewport, "focus": focus,
                          "overflow": overflow_checks, "page_errors": errors, "external_requests": external,
                          "workflow": "upload/classify/save and next/schedule/open email/review confirmed/done/reopen/cancel/prepare/deduplicate/preview/evaluate/activate/rollback/reactivate passed",
                          "data": "Only the shipped synthetic demonstration fixtures", "screenshots": "runtime/newsprint-qa"}
        print(json.dumps(evidence, indent=2))
        browser.close()
        return evidence


def capture_profile(profile, portfolio):
    # Each run starts the isolated interpreter against its own disposable database.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "INBOXLEARN_DB": str(OUT / f"browser-{uuid.uuid4().hex}.sqlite3")}
    url = f"http://127.0.0.1:{port}"
    with (OUT / f"{profile}-server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
                                   "--server.port", str(port)], cwd=ROOT, env=env, stdout=log, stderr=log,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urllib.request.urlopen(url + "/_stcore/health", timeout=1) as response:
                        assert response.status == 200
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(0.25)
            evidence = run_browser(url, profile)
            evidence["startup_health"] = "HTTP 200"
            if portfolio:
                # Verify that the screenshot database's scores match the recorded experiment.
                from inboxlearn.config import Settings
                from inboxlearn.service import InboxLearnService
                service = InboxLearnService(Settings(db_path=Path(env["INBOXLEARN_DB"])))
                comparison = service.compare_versions(2)
                measured = json.loads((ROOT / "reports" / "learning.json").read_text(encoding="utf-8"))
                assert comparison["baseline"] == measured["baseline"]
                assert comparison["updated"] == measured["updated"]
                assert service.prediction_preview(1, 2) == measured["inbox_preview"]
                assert len(service.repo.versions()) == 2
                evidence["scores_match_learning_report"] = True
                evidence["preview_matches_learning_report"] = True
                destination = ROOT / "docs" / "screenshots"
                destination.mkdir(parents=True, exist_ok=True)
                images = [f"{profile}-{name}.png" for name in (
                    "landing", "today-empty", "today", "inbox", "review", "candidate", "prediction-changes", "evaluation", "matrices", "versions")]
                for name in images:
                    shutil.copyfile(OUT / name, destination / name)
                evidence["screenshots"] = images
                print("Portfolio screenshots verified against reports/learning.json and copied to docs/screenshots.")
            return evidence
        finally:
            server.terminate()
            server.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portfolio", action="store_true", help="Copy verified synthetic captures to docs/screenshots")
    args = parser.parse_args()
    evidence = {profile: capture_profile(profile, args.portfolio) for profile in ("desktop", "mobile")}
    if args.portfolio:
        evidence["captured_at"] = datetime.now(timezone.utc).isoformat()
        evidence["source_sha256"] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
            "app.py", "inboxlearn/presentation.py", "inboxlearn/landing.py", "assets/newsprint.css",
            "landing/index.html", "landing/styles.css", "landing/script.js", ".streamlit/config.toml", "scripts/browser_qa.py")}
        evidence["screenshot_sha256"] = {name: hashlib.sha256((ROOT / "docs" / "screenshots" / name).read_bytes()).hexdigest()
                                         for profile in ("desktop", "mobile") for name in evidence[profile]["screenshots"]}
        (ROOT / "docs" / "screenshots" / "capture.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
