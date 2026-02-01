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

    CF managed challenge flow on kv.ee:
      - Page loads with _cf_chl_opt (obfuscated keys) and two scripts:
        1. /cdn-cgi/challenge-platform/... (orchestrator)
        2. challenges.cloudflare.com/turnstile/v0/.../api.js?onload=X&render=explicit
      - Once api.js loads, CF calls the onload callback (e.g. cAdz2)
      - That callback calls turnstile.render(container, {sitekey, action, cData, ...})
      - We intercept api.js via Playwright route handler, replace it with a stub
        that exposes turnstile.render as a capture function.
      - Once params are captured, we send to 2captcha.
      - 2captcha returns a token.
      - We call the captured CF callback with the token → CF sets cf-clearance
        and redirects.
    """
    api_key = _get_2captcha_key()
    if not api_key:
        raise RuntimeError(
            "TWOCAPTCHA_API_KEY env var is not set. "
            "Set it on Railway to enable CF challenge solving."
        )

    # Step 1: set up a route handler that intercepts the Turnstile api.js
    # and replaces it with our stub. The stub:
    #   - Defines window.turnstile with a render() that captures params
    #   - Calls the onload callback (from the URL ?onload=X param) so CF
    #     proceeds to call turnstile.render()

    def handle_turnstile(route):
        request_url = route.request.url
        # Extract the onload callback name from the URL
        # e.g. ?onload=cAdz2&render=explicit
        onload = ""
        if "onload=" in request_url:
            onload = request_url.split("onload=")[1].split("&")[0]

        # Our replacement script:
        # - Creates window.turnstile with a render() that stores params
        # - Calls the onload function so CF proceeds
        stub = f"""
        (function() {{
            window.__cf_params = null;
            window.__cf_callback = null;
            window.turnstile = {{
                render: function(container, opts) {{
                    window.__cf_params = {{
                        sitekey: opts.sitekey,
                        action: opts.action || '',
                        data: opts.cData || '',
                        pagedata: opts.chlPageData || ''
                    }};
                    window.__cf_callback = opts.callback;
                    return 'intercepted';
                }}
            }};
            // Call CF's onload so it proceeds to call turnstile.render()
            if (typeof {onload} === 'function') {{
                {onload}();
            }} else {{
                // onload might not be defined yet — schedule it
                setTimeout(function() {{
                    if (typeof {onload} === 'function') {onload}();
                }}, 100);
            }}
        }})();
        """
        route.fulfill(
            status=200,
            content_type="application/javascript",
            body=stub,
        )

    page.route("**/challenges.cloudflare.com/turnstile/**", handle_turnstile)

    # Step 2: navigate — CF serves challenge page, api.js gets intercepted
    page.goto(url, wait_until="domcontentloaded", timeout=60000)

    title = page.evaluate("() => document.title")
    if "just a moment" not in title.lower():
        page.unroute("**/challenges.cloudflare.com/turnstile/**")
        return title

    # Step 3: wait for our interceptor to capture the params
    print("  Waiting for CF turnstile params via intercepted api.js...")
    params = None
    for _ in range(60):  # up to 30s
        page.wait_for_timeout(500)
        params = page.evaluate("() => window.__cf_params")
        if params and params.get("sitekey"):
            break

    page.unroute("**/challenges.cloudflare.com/turnstile/**")

    if not params or not params.get("sitekey"):
        # Dump what we have for diagnosis
        cf_chl_opt_text = page.evaluate("""
        () => {
            const scripts = document.querySelectorAll('script');
            for (const s of scripts) {
                if (s.textContent.includes('_cf_chl_opt')) {
                    return s.textContent.slice(0, 2000);
                }
            }
            return 'no _cf_chl_opt script found';
        }
        """)
        raise RuntimeError(
            f"CF turnstile.render() was not called after api.js interception.\n"
            f"Captured params: {params}\n"
            f"_cf_chl_opt script: {cf_chl_opt_text}"
        )

    print(f"  Got CF params: sitekey={params['sitekey']}, action={params['action']}")

    # Step 4: submit to 2captcha
    task = {
        "type": "TurnstileTaskProxyless",
        "websiteURL": url,
        "websiteKey": params["sitekey"],
    }
    if params.get("action"):
        task["action"] = params["action"]
    if params.get("data"):
        task["data"] = params["data"]
    if params.get("pagedata"):
        task["pagedata"] = params["pagedata"]

    task_payload = {"clientKey": api_key, "task": task}

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

    # Step 5: poll for result
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
    else:
        raise RuntimeError("2captcha did not return a solution within 120s")

    # Step 6: call the CF callback with the token.
    # This is what CF expects — it processes the token, sets cf-clearance
    # cookie, and submits an internal form that redirects to the real page.
    page.evaluate(
        "(token) => { if (window.__cf_callback) window.__cf_callback(token); }",
        token,
    )

    # Wait for CF to redirect
    print("  Waiting for CF redirect after token injection...")
    for _ in range(30):  # up to 15s
        page.wait_for_timeout(500)
        title = page.evaluate("() => document.title")
        if "just a moment" not in title.lower():
            print(f"  CF solved! Page title: {title}")
            page.wait_for_timeout(1000)
            return title

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
        f"CF token injected but page did not redirect.\n"
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
        f"CF challenge did not resolve after ~60s. "
        f"[TWOCAPTCHA_API_KEY={'SET' if two_captcha_key else 'NOT SET'}, "
        f"env keys: {[k for k in os.environ if 'CAPTCHA' in k.upper() or 'TWO' in k.upper()]}]\n"
        f"Current URL: {page.url}\n"
        f"Title: {title}\n"
        f"HTML snippet: {html[:2000]}"
    )
