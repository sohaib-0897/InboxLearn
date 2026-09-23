"""Visual & Functional QA verification script for InboxLearn Landing Page."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

LANDING_HTML = (Path(__file__).parent.parent / "landing" / "index.html").resolve().as_uri()
SCREENSHOT_DIR = Path(__file__).parent.parent / "runtime" / "landing-qa"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

async def run_verification():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        
        # 1. Desktop Check (1440x900)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        
        await page.goto(LANDING_HTML, wait_until="networkidle")
        
        # Verify title & main elements
        title = await page.title()
        assert "InboxLearn" in title, f"Unexpected title: {title}"
        
        # Check horizontal overflow on desktop
        overflow = await page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        assert not overflow, "Horizontal overflow detected on desktop!"
        
        # Capture Desktop Full Screenshot at initial top state
        desktop_shot = SCREENSHOT_DIR / "landing-desktop.png"
        await page.screenshot(path=str(desktop_shot), full_page=True)
        print(f"Captured Desktop Screenshot: {desktop_shot}")

        # Test interactive email switcher
        await page.click("button.email-item-btn >> text=#02")
        subject_text = await page.inner_text("#detailSubject")
        assert "Rent invoice available" in subject_text, f"Subject did not update: {subject_text}"
        
        # Test simulated human feedback
        await page.click("#btnSaveCorrection")
        await page.wait_for_timeout(300)
        status_msg = await page.inner_text("#consoleStatusMsg")
        assert "PERSISTED TO SQLITE" in status_msg, f"Correction feedback missing: {status_msg}"
        
        # 2. Tablet Check (768x1024)
        page_tablet = await browser.new_page(viewport={"width": 768, "height": 1024})
        await page_tablet.goto(LANDING_HTML, wait_until="networkidle")
        overflow_tab = await page_tablet.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        assert not overflow_tab, "Horizontal overflow detected on tablet!"
        tablet_shot = SCREENSHOT_DIR / "landing-tablet.png"
        await page_tablet.screenshot(path=str(tablet_shot), full_page=True)
        print(f"Captured Tablet Screenshot: {tablet_shot}")

        # 3. Mobile Check (390x844)
        page_mobile = await browser.new_page(viewport={"width": 390, "height": 844})
        await page_mobile.goto(LANDING_HTML, wait_until="networkidle")
        overflow_mob = await page_mobile.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        assert not overflow_mob, "Horizontal overflow detected on mobile!"
        
        mobile_closed_shot = SCREENSHOT_DIR / "landing-mobile.png"
        await page_mobile.screenshot(path=str(mobile_closed_shot), full_page=True)
        print(f"Captured Mobile (Default) Screenshot: {mobile_closed_shot}")

        # Test mobile nav menu toggle
        await page_mobile.click("#mobileNavToggle")
        is_open = await page_mobile.is_visible("#mobileNavDrawer")
        assert is_open, "Mobile drawer did not open!"
        
        mobile_open_shot = SCREENSHOT_DIR / "landing-mobile-menu-open.png"
        await page_mobile.screenshot(path=str(mobile_open_shot), full_page=True)
        print(f"Captured Mobile (Menu Open) Screenshot: {mobile_open_shot}")
        
        assert len(console_errors) == 0, f"Encountered console errors: {console_errors}"
        
        await browser.close()
        print("\nAll Playwright functional, responsive, and visual verifications passed successfully!")

if __name__ == "__main__":
    asyncio.run(run_verification())
