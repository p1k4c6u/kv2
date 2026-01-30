# browser.py
from playwright.sync_api import sync_playwright

PROFILE_DIR = "kv_profile"

def with_browser(fn):
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=False,   # KV puhul soovitatav
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()
        try:
            return fn(page)
        finally:
            context.close()
