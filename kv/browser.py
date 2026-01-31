# browser.py
import os
from playwright.sync_api import sync_playwright
from undetected_playwright import Tarnished

PROFILE_DIR = "kv_profile"

# Environment variable to control headless mode
# Set HEADLESS=true for cloud/automated scraping
# Set HEADLESS=false (or don't set) for local with visible browser
HEADLESS = os.environ.get("HEADLESS", "false").lower() == "true"


def with_browser(fn, headless: bool | None = None):
    """
    Run a function with a browser context.

    Args:
        fn: Function that takes a page and returns a result
        headless: Override headless mode (None = use env variable)
    """
    use_headless = headless if headless is not None else HEADLESS

    with sync_playwright() as p:
        if use_headless:
            # Headless mode with stealth for cloud/automated scraping
            # Using Chrome's new headless mode which is less detectable
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--headless=new",  # New headless mode (Chrome 112+)
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="et-EE",
            )
            # Apply stealth patches to avoid bot detection
            Tarnished.apply_stealth(context)
            page = context.new_page()
            try:
                return fn(page)
            finally:
                context.close()
                browser.close()
        else:
            # Visible browser mode with persistent profile for local scraping
            # Useful when CAPTCHA solving is needed manually
            context = p.chromium.launch_persistent_context(
                PROFILE_DIR,
                headless=False,
                viewport={"width": 1280, "height": 900},
            )
            page = context.new_page()
            try:
                return fn(page)
            finally:
                context.close()


def with_browser_headless(fn):
    """Convenience wrapper that forces headless mode."""
    return with_browser(fn, headless=True)


def with_browser_visible(fn):
    """Convenience wrapper that forces visible browser mode."""
    return with_browser(fn, headless=False)
