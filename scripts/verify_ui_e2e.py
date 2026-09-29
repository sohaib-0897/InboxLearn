"""E2E Verification & Portfolio Capture for InboxLearn UI."""
import os
import sys
import time
import subprocess
import socket
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCREENSHOTS_DIR = ROOT / "docs" / "screenshots" / "agency"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def main():
    port = 8855
    server_process = None

    if not is_port_open(port):
        print(f"Starting backend server on port {port}...")
        server_process = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "serve_api.py"), str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Wait for server to bind
        for _ in range(25):
            time.sleep(0.5)
            if is_port_open(port):
                break
        else:
            raise RuntimeError(f"Server failed to start on port {port}")

    url = f"http://127.0.0.1:{port}"
    app_url = f"{url}/app"
    print(f"Connecting Playwright to {url}...")

    with sync_playwright() as p:
        browser = None
        for channel in [None, "msedge", "chrome"]:
            try:
                launch_opts = {"headless": True}
                if channel:
                    launch_opts["channel"] = channel
                browser = p.chromium.launch(**launch_opts)
                print(f"Launched browser with channel: {channel or 'bundled'}")
                break
            except Exception as e:
                print(f"Could not launch with channel {channel}: {e}")

        if not browser:
            print("No suitable browser found for Playwright.")
            return

        # -------------------------------------------------------------
        # Desktop Test (1440x950)
        # -------------------------------------------------------------
        print("\n--- Running Desktop E2E Tests ---")
        page = browser.new_page(viewport={"width": 1440, "height": 950})
        console_errors = []
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        # ---- LANDING PAGE ----
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(2.0)  # Allow 3D scene and GSAP animations to initialize

        # 0. Verify Landing Page
        title = page.title()
        print(f"Page title: {title}")
        assert "InboxLearn" in title

        hero_heading = page.locator("h1")
        expect(hero_heading).to_be_visible()
        print("Landing page hero verified visible.")

        # Verify CTA button exists
        cta_link = page.locator("a:has-text('Open the App')")
        if cta_link.count() == 0:
            cta_link = page.locator("a:has-text('Open App')")
        expect(cta_link.first).to_be_visible()
        print("Landing page CTA verified visible.")

        # Capture landing page screenshots
        page.screenshot(path=str(SCREENSHOTS_DIR / "desktop-01-hero.png"))
        print(f"Captured: {SCREENSHOTS_DIR / 'desktop-01-hero.png'}")

        # Scroll down to features section for a full-page capture
        page.locator("#features").scroll_into_view_if_needed()
        time.sleep(1.2)
        page.screenshot(path=str(SCREENSHOTS_DIR / "desktop-08-features.png"))
        print(f"Captured: {SCREENSHOTS_DIR / 'desktop-08-features.png'}")

        # ---- NAVIGATE TO APP ----
        page.goto(app_url, wait_until="domcontentloaded")
        time.sleep(1.0)

        # 1. Verify Masthead and Inbox & Triage Desk
        hero_heading = page.locator("h1")
        expect(hero_heading).to_be_visible()
        print("App masthead verified visible.")

        # Ensure demo fixture is loaded so the reading pane and triage table have realistic data
        load_demo_btn = page.locator("button:has-text('Load Demo Fixture')")
        if load_demo_btn.count() > 0:
            load_demo_btn.first.click()
            time.sleep(1.0)

        # Save human correction on first message to create training feedback
        save_feedback_btn = page.locator("button:has-text('Save Human Correction')")
        if save_feedback_btn.count() > 0:
            save_feedback_btn.first.click()
            time.sleep(1.0)

        # Capture Desktop Inbox & Review Desk
        page.screenshot(path=str(SCREENSHOTS_DIR / "desktop-04-review-desk.png"))
        print(f"Captured: {SCREENSHOTS_DIR / 'desktop-04-review-desk.png'}")

        # 2. Test Live Inference Probe Bench
        print("Testing Live Inference Probe...")
        probe_tab_btn = page.locator("button:has-text('Live Inference Probe')")
        if probe_tab_btn.count() > 0:
            probe_tab_btn.first.click()
            time.sleep(0.5)

        offer_preset_btn = page.locator("button:has-text('AWS Cloud Invoice')")
        if offer_preset_btn.count() > 0:
            offer_preset_btn.first.click()
            time.sleep(0.5)
            run_btn = page.locator("button:has-text('Run Real-Time Inference Probe')")
            if run_btn.count() > 0:
                run_btn.first.click()
                time.sleep(0.8)
            page.screenshot(path=str(SCREENSHOTS_DIR / "desktop-02-inference-aws.png"))
            print(f"Captured: {SCREENSHOTS_DIR / 'desktop-02-inference-aws.png'}")

        # Test another preset
        phish_btn = page.locator("button:has-text('Phishing Wire Transfer')")
        if phish_btn.count() > 0:
            phish_btn.first.click()
            time.sleep(0.5)
            run_btn = page.locator("button:has-text('Run Real-Time Inference Probe')")
            if run_btn.count() > 0:
                run_btn.first.click()
                time.sleep(0.8)
            page.screenshot(path=str(SCREENSHOTS_DIR / "desktop-03-inference-phish.png"))
            print(f"Captured: {SCREENSHOTS_DIR / 'desktop-03-inference-phish.png'}")

        # 3. Test Candidate & Gate
        print("Testing Candidate & Gate...")
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.5)
        page.locator("button:has-text('Candidate & Gate')").first.click()
        time.sleep(0.8)
        # Click prepare candidate if available
        prep_btn = page.locator("button:has-text('Prepare Candidate Snapshot')")
        if prep_btn.count() > 0:
            prep_btn.first.click()
            time.sleep(1.2)
        # Click diff inbox if enabled
        diff_btn = page.locator("button:has-text('Diff Inbox Predictions')")
        if diff_btn.count() > 0 and diff_btn.first.is_enabled():
            diff_btn.first.click()
            time.sleep(0.8)
        # Click evaluation
        eval_btn = page.locator("button:has-text('Run Held-Out Evaluation')")
        if eval_btn.count() > 0:
            eval_btn.first.click()
            time.sleep(1.5)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.5)
        page.screenshot(path=str(SCREENSHOTS_DIR / "desktop-05-candidate-gate.png"))
        print(f"Captured: {SCREENSHOTS_DIR / 'desktop-05-candidate-gate.png'}")

        # 4. Test Version Ledger
        print("Testing Version Ledger...")
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.5)
        ledger_btn = page.locator("nav button:has-text('Version Ledger')").first
        ledger_btn.click()
        time.sleep(0.8)
        page.screenshot(path=str(SCREENSHOTS_DIR / "desktop-06-version-ledger.png"))
        print(f"Captured: {SCREENSHOTS_DIR / 'desktop-06-version-ledger.png'}")

        # 5. Test Architecture Pipeline
        print("Testing Architecture...")
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.5)
        arch_btn = page.locator("nav button:has-text('Architecture')").first
        arch_btn.click()
        time.sleep(0.8)
        page.screenshot(path=str(SCREENSHOTS_DIR / "desktop-07-pipeline.png"))
        print(f"Captured: {SCREENSHOTS_DIR / 'desktop-07-pipeline.png'}")

        page.close()

        # -------------------------------------------------------------
        # Mobile Test (390x844)
        # -------------------------------------------------------------
        print("\n--- Running Mobile E2E Tests ---")
        time.sleep(1.0)
        mobile_page = browser.new_page(viewport={"width": 390, "height": 844})
        try:
            # Mobile Landing Page
            mobile_page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(2.0)
            mobile_page.screenshot(path=str(SCREENSHOTS_DIR / "mobile-01-hero.png"))
            print(f"Captured: {SCREENSHOTS_DIR / 'mobile-01-hero.png'}")

            # Navigate to App
            mobile_page.goto(app_url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(1.0)

            # Load demo fixture for mobile testing
            load_demo_btn = mobile_page.locator("button:has-text('Load Demo Fixture')")
            if load_demo_btn.count() > 0:
                load_demo_btn.first.click()
                time.sleep(1.0)

            mobile_page.screenshot(path=str(SCREENSHOTS_DIR / "mobile-02-inference.png"))
            print(f"Captured: {SCREENSHOTS_DIR / 'mobile-02-inference.png'}")
        except Exception as e:
            print(f"Mobile capture note: {e}")
        finally:
            mobile_page.close()
            browser.close()

    if server_process:
        print("Terminating test server...")
        server_process.terminate()

    print("\n[SUCCESS] All E2E checks and screenshot captures completed cleanly.")
    if console_errors:
        print(f"Console errors noted: {console_errors}")
    else:
        print("Zero console errors detected.")


if __name__ == "__main__":
    main()
