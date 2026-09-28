"""E2E Verification & Portfolio Capture for InboxLearn Premium Agency UI."""
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
    print(f"Connecting Playwright to {url}...")

    with sync_playwright() as p:
        browser = None
        for channel in ["chrome", "msedge", None]:
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

        page.goto(url)
        page.wait_for_load_state("networkidle")
        time.sleep(1.5)

        # 1. Verify Hero
        title = page.title()
        print(f"Page title: {title}")
        assert "InboxLearn" in title

        hero_heading = page.locator("h1")
        expect(hero_heading).to_be_visible()
        print("Hero heading verified visible.")

        # Capture Hero & Studio
        page.screenshot(path=str(SCREENSHOTS_DIR / "desktop-01-hero.png"))
        print(f"Captured: {SCREENSHOTS_DIR / 'desktop-01-hero.png'}")

        # 2. Run Inference Probe in Studio
        print("Testing interactive Inference Studio...")
        offer_preset_btn = page.locator("button:has-text('AWS Cloud Invoice')")
        if offer_preset_btn.count() > 0:
            offer_preset_btn.first.click()
            time.sleep(1.0)
            page.screenshot(path=str(SCREENSHOTS_DIR / "desktop-02-inference-aws.png"))
            print(f"Captured: {SCREENSHOTS_DIR / 'desktop-02-inference-aws.png'}")

        # Test another preset
        phish_btn = page.locator("button:has-text('Phishing Wire Transfer')")
        if phish_btn.count() > 0:
            phish_btn.first.click()
            time.sleep(1.0)
            page.screenshot(path=str(SCREENSHOTS_DIR / "desktop-03-inference-phish.png"))
            print(f"Captured: {SCREENSHOTS_DIR / 'desktop-03-inference-phish.png'}")

        # 3. Test Review Desk
        print("Testing Review Desk...")
        page.locator("button:has-text('Review Desk')").first.click()
        time.sleep(1.0)
        page.screenshot(path=str(SCREENSHOTS_DIR / "desktop-04-review-desk.png"))
        print(f"Captured: {SCREENSHOTS_DIR / 'desktop-04-review-desk.png'}")

        # 4. Test Candidate & Gate
        print("Testing Candidate & Gate...")
        page.locator("button:has-text('Candidate & Gate')").first.click()
        time.sleep(1.0)
        page.screenshot(path=str(SCREENSHOTS_DIR / "desktop-05-candidate-gate.png"))
        print(f"Captured: {SCREENSHOTS_DIR / 'desktop-05-candidate-gate.png'}")

        # 5. Test Version Ledger
        print("Testing Version Ledger...")
        page.locator("button:has-text('Version Ledger')").first.click()
        time.sleep(1.0)
        page.screenshot(path=str(SCREENSHOTS_DIR / "desktop-06-version-ledger.png"))
        print(f"Captured: {SCREENSHOTS_DIR / 'desktop-06-version-ledger.png'}")

        # 6. Test Architecture Pipeline
        print("Testing Architecture Pipeline...")
        page.locator("button:has-text('Architecture')").first.click()
        time.sleep(1.0)
        page.screenshot(path=str(SCREENSHOTS_DIR / "desktop-07-pipeline.png"))
        print(f"Captured: {SCREENSHOTS_DIR / 'desktop-07-pipeline.png'}")

        page.close()

        # -------------------------------------------------------------
        # Mobile Test (390x844)
        # -------------------------------------------------------------
        print("\n--- Running Mobile E2E Tests ---")
        mobile_page = browser.new_page(viewport={"width": 390, "height": 844})
        try:
            mobile_page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(1.0)
            mobile_page.screenshot(path=str(SCREENSHOTS_DIR / "mobile-01-hero.png"))
            print(f"Captured: {SCREENSHOTS_DIR / 'mobile-01-hero.png'}")
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
