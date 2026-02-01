# browser.py
import os
import time
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from undetected_playwright import Tarnished

PROFILE_DIR = "kv_profile"

# Environment variable to control headless mode
# Set HEADLESS=true for cloud/automated scraping
# Set HEADLESS=false (or don't set) for local with visible browser
HEADLESS = os.environ.get("HEADLESS", "false").lower() == "true"

# Optional proxy for bypassing Cloudflare on datacenter IPs.
# Format: http://user:pass@host:port  or  socks5://user:pass@host:port
# Without a proxy, CF managed challenges will block headless scraping.
PROXY_URL = os.environ.get("PROXY_URL", "").strip() or None


def _proxy_config() -> dict | None:
    """
    Parse PROXY_URL into Playwright proxy config.

    Playwright requires username/password as separate fields — it doesn't
    reliably extract them from the server URL when auth is embedded.
    """
    if not PROXY_URL:
        return None

    parsed = urlparse(PROXY_URL)

    # server URL without credentials: scheme://host:port
    server = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"

    config = {"server": server}
    if parsed.username:
        config["username"] = parsed.username
    if parsed.password:
        config["password"] = parsed.password

    return config


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
                proxy=_proxy_config(),
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
                proxy=_proxy_config(),
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


import json as _json
import urllib.request as _urllib_request


def _get_2captcha_key() -> str | None:
    """Read TWOCAPTCHA_API_KEY fresh from env each time (not cached at import)."""
    return os.environ.get("TWOCAPTCHA_API_KEY", "").strip() or None


def _solve_cf_with_2captcha(page, url: str) -> str:
    """
    Solve a Cloudflare managed challenge using 2captcha's Turnstile solver.

    Flow:
      1. Inject JS that intercepts turnstile.render() to capture sitekey,
         action, cData, chlPageData before CF's script grabs them.
      2. Wait for CF's script to load and call turnstile.render().
      3. Send captured params to 2captcha API.
      4. Poll 2captcha until solution is ready.
      5. Execute the original turnstile callback with the token — CF
         processes it, sets cf-clearance cookie, and redirects.

    Returns the page title after successful redirect.
    """
    api_key = _get_2captcha_key()
    if not api_key:
        raise RuntimeError(
            "TWOCAPTCHA_API_KEY env var is not set. "
            "Set it on Railway to enable CF challenge solving."
        )

    # Step 1: inject interceptor BEFORE navigating, so it's ready when
    # CF's script calls turnstile.render().
    # We store captured params in window.__cf_params and the callback in
    # window.__cf_callback so we can retrieve them from Python.
    intercept_js = """
    (function() {
        window.__cf_params = null;
        window.__cf_callback = null;

        // Poll for window.turnstile appearing (CF loads it dynamically)
        const i = setInterval(() => {
            if (window.turnstile) {
                clearInterval(i);
                const orig = window.turnstile.render;
                window.turnstile.render = function(container, opts) {
                    window.__cf_params = {
                        sitekey: opts.sitekey,
                        action: opts.action || '',
                        data: opts.cData || '',
                        pagedata: opts.chlPageData || ''
                    };
                    window.__cf_callback = opts.callback;
                    // Return a dummy id so CF doesn't error
                    return 'intercepted';
                };
            }
        }, 50);
    })();
    """
    page.evaluate(intercept_js)

    # Step 2: navigate to the CF challenge page
    page.goto(url, wait_until="domcontentloaded", timeout=60000)

    # Wait for CF's script to load and our interceptor to fire
    print("  Waiting for CF turnstile params...")
    for _ in range(40):  # up to 20s
        page.wait_for_timeout(500)
        params = page.evaluate("() => window.__cf_params")
        if params:
            break
    else:
        # Fallback: maybe CF solved itself or page redirected
        title = page.evaluate("() => document.title")
        if "just a moment" not in title.lower():
            return title
        raise RuntimeError(
            "CF challenge loaded but turnstile.render() was never called. "
            f"URL: {page.url}"
        )

    print(f"  Got CF params: sitekey={params['sitekey']}, action={params['action']}")

    # Step 3: submit to 2captcha
    task_payload = {
        "clientKey": api_key,
        "task": {
            "type": "TurnstileTaskProxyless",
            "websiteURL": url,
            "websiteKey": params["sitekey"],
            "action": params["action"],
            "data": params["data"],
            "pagedata": params["pagedata"],
        },
    }

    req = _urllib_request.Request(
        "https://api.2captcha.com/createTask",
        data=_json.dumps(task_payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = _json.loads(_urllib_request.urlopen(req).read())

    if resp.get("errorId", 0) != 0:
        raise RuntimeError(f"2captcha createTask error: {resp}")

    task_id = resp["taskId"]
    print(f"  2captcha task created: {task_id}")

    # Step 4: poll for result
    for attempt in range(24):  # up to 120s (5s intervals)
        time.sleep(5)
        req = _urllib_request.Request(
            "https://api.2captcha.com/getTaskResult",
            data=_json.dumps({"clientKey": api_key, "taskId": task_id}).encode(),
            headers={"Content-Type": "application/json"},
        )
        result = _json.loads(_urllib_request.urlopen(req).read())

        if result.get("errorId", 0) != 0:
            raise RuntimeError(f"2captcha getTaskResult error: {result}")

        if result["status"] == "ready":
            token = result["solution"]["token"]
            print(f"  2captcha solved (attempt {attempt + 1})")
            break
        # status == "notReady", keep polling
    else:
        raise RuntimeError("2captcha did not return a solution within 120s")

    # Step 5: execute the CF callback with the token.
    # This triggers CF's internal flow: it validates the token, sets
    # cf-clearance cookie, and submits the form which redirects to the
    # real page.
    page.evaluate(
        "(token) => { if (window.__cf_callback) window.__cf_callback(token); }", token
    )

    # Wait for CF to process and redirect
    print("  Waiting for CF redirect after token injection...")
    for _ in range(20):  # up to 10s
        page.wait_for_timeout(500)
        title = page.evaluate("() => document.title")
        if "just a moment" not in title.lower():
            print(f"  CF solved! Page title: {title}")
            page.wait_for_timeout(1000)
            return title

    # If still on challenge page, try waiting longer for navigation
    try:
        with page.expect_navigation(timeout=15000, wait_until="domcontentloaded"):
            pass
        title = page.evaluate("() => document.title")
        if "just a moment" not in title.lower():
            print(f"  CF solved after navigation wait! Title: {title}")
            return title
    except Exception:
        pass

    raise RuntimeError(
        f"CF challenge token was accepted but page did not redirect.\n"
        f"URL: {page.url}\nTitle: {page.evaluate('() => document.title')}"
    )


def cf_goto(page, url):
    """
    Navigate to a kv.ee URL and handle Cloudflare's managed challenge.

    If TWOCAPTCHA_API_KEY is set, uses 2captcha to solve CF Turnstile
    challenges automatically. Otherwise falls back to waiting for the
    CF JS to auto-solve (works in visible browser, fails in headless).

    Once cf-clearance is set, subsequent requests in the same browser
    context reuse it automatically — no need to re-solve.
    """
    # If 2captcha is configured, use it proactively — inject the
    # interceptor before navigating so we catch turnstile.render().
    two_captcha_key = _get_2captcha_key()
    print(f"  cf_goto: TWOCAPTCHA_API_KEY={'SET' if two_captcha_key else 'NOT SET'}")
    if two_captcha_key:
        _solve_cf_with_2captcha(page, url)
        return

    # Fallback: navigate and hope CF auto-solves (visible browser only)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)

    title = page.evaluate("() => document.title")

    if "just a moment" not in title.lower():
        return

    print("  CF challenge detected, waiting for auto-solve...")

    try:
        with page.expect_navigation(timeout=60000, wait_until="domcontentloaded"):
            pass
    except Exception:
        pass

    for _ in range(12):  # up to 60s
        page.wait_for_timeout(5000)
        title = page.evaluate("() => document.title")
        if "just a moment" not in title.lower():
            print(f"  CF challenge solved, page title: {title}")
            page.wait_for_timeout(2000)
            return
        print(f"  still waiting for CF challenge... (title: {title})")

    html = page.content()
    raise RuntimeError(
        f"CF challenge did not resolve after ~60s.\n"
        f"Current URL: {page.url}\n"
        f"Title: {title}\n"
        f"HTML snippet: {html[:3000]}"
    )
