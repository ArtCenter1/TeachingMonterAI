"""
Direct NotebookLM login using Playwright.
Auto-detects when login is complete — no manual ENTER needed.

Usage:
    .venv\\Scripts\\python.exe scripts\\nlm_login_direct.py
"""

import os
import sys
import json
import time
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
NOTEBOOKLM_HOME = Path(os.environ.get("NOTEBOOKLM_HOME", Path.home() / ".notebooklm"))
STORAGE_PATH = NOTEBOOKLM_HOME / "storage_state.json"
BROWSER_PROFILE = NOTEBOOKLM_HOME / "browser_profile"

NOTEBOOKLM_HOME.mkdir(parents=True, exist_ok=True)
BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)

print(f"NotebookLM home : {NOTEBOOKLM_HOME}")
print(f"Browser profile : {BROWSER_PROFILE}")
print(f"Storage target  : {STORAGE_PATH}")
print()
print("Launching Windows Chrome...")
print("=" * 60)
print("  -> Sign in to Google in the browser window that opens")
print("  -> Wait for the NotebookLM homepage to load")
print("  -> This script auto-detects completion — do NOT close it")
print("=" * 60)
print()

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(BROWSER_PROFILE),
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--password-store=basic",
        ],
        ignore_default_args=["--enable-automation"],
        slow_mo=50,
    )

    page = context.pages[0] if context.pages else context.new_page()
    page.goto("https://notebooklm.google.com/")

    print("Waiting for you to complete Google login...")
    print("(Polling URL every 3 seconds — will save automatically)\n")

    timeout = 300  # 5-minute timeout
    start = time.time()
    saved = False

    while time.time() - start < timeout:
        try:
            current_url = page.url
        except Exception:
            break  # Browser was closed

        if "notebooklm.google.com" in current_url and "accounts.google.com" not in current_url and "login" not in current_url:
            print(f"Detected NotebookLM homepage! URL: {current_url}")
            # Wait an extra 2s for page to fully settle
            time.sleep(2)
            context.storage_state(path=str(STORAGE_PATH))
            print(f"\nSUCCESS! Session saved to: {STORAGE_PATH}")
            saved = True
            break
        else:
            elapsed = int(time.time() - start)
            print(f"  [{elapsed:3d}s] Waiting... (current: {current_url[:60]})", end="\r")
            time.sleep(3)

    if not saved:
        print("\nTimeout or browser closed before login completed.")
        print("Session NOT saved. Please re-run and complete login within 5 minutes.")

    context.close()

print()
if STORAGE_PATH.exists():
    with open(STORAGE_PATH) as f:
        state = json.load(f)
    cookie_count = len(state.get("cookies", []))
    print(f"Cookies saved  : {cookie_count}")
    if cookie_count > 0:
        print("Login SUCCESSFUL. NLM is ready!")
    else:
        print("WARNING: No cookies saved. Login may have failed.")
else:
    print("ERROR: No session file found. Login failed.")
