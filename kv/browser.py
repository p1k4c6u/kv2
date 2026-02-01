# browser.py
import os
import time
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
            # Launch with headless=False but pass --headless=new as a Chrome arg.
            # This uses Chrome's newer headless mode which behaves like a real browser
            # (no Headless flag in navigator, realistic rendering). Passing headless=True
            # to Playwright conflicts with --headless=new and breaks stealth.
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--headless=new",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-gpu",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                locale="et-EE",
                # Don't set user_agent here — let Tarnished handle it so it
                # matches the actual Chromium version shipped with Playwright.
            )
            # Apply stealth patches to avoid bot detection
            Tarnished.apply_stealth(context)
            page = context.new_page()

            # Brief pause before first navigation — mimics real browser startup
            time.sleep(1)

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


def cf_goto(page, url):
    """
    Navigate to a kv.ee URL and handle Cloudflare's managed challenge.

    CF managed challenges work like this:
      1. First request returns a 403 with a challenge page
      2. The challenge page loads a script from challenges.cloudflare.com
      3. That script runs browser fingerprinting and solves the challenge
      4. On success, it POSTs back to kv.ee with a cf-clearance token
      5. kv.ee sets the cf-clearance cookie and redirects to the original URL

    Once cf-clearance is set, subsequent requests in the same browser
    context reuse it automatically — no need to re-solve.
    """
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)

    title = page.evaluate("() => document.title")

    if "just a moment" not in title.lower():
        # No challenge — already on the real page
        return

    print(f"  CF challenge detected, waiting for auto-solve...")

    # The challenge JS will solve and trigger a form POST + redirect.
    # Wait for the page to navigate away from the challenge page.
    try:
        with page.expect_navigation(timeout=60000, wait_until="domcontentloaded"):
            pass
    except Exception:
        pass  # expect_navigation might already have fired

    # Poll until title changes (CF managed challenges typically solve in 5-20s)
    for _ in range(12):  # up to 60s
        page.wait_for_timeout(5000)
        title = page.evaluate("() => document.title")
        if "just a moment" not in title.lower():
            print(f"  CF challenge solved, page title: {title}")
            page.wait_for_timeout(2000)
            return
        print(f"  still waiting for CF challenge... (title: {title})")

    # Failed — dump info for diagnosis
    html = page.content()
    raise RuntimeError(
        f"CF challenge did not resolve after ~60s.\n"
        f"Current URL: {page.url}\n"
        f"Title: {title}\n"
        f"HTML snippet: {html[:3000]}"
    )
