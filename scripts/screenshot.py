"""Capture README screenshots from the running app (Playwright, Chromium).

    python scripts/screenshot.py [--url http://127.0.0.1:5173] [--out docs]

Needs the frontend (vite dev or preview), the backend and some scraped data.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "docs"))
    parser.add_argument("--scheme", choices=["light", "dark"], default="light")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1360, "height": 900}, device_scale_factor=1, color_scheme=args.scheme)

        # 1. Search with filters: a realistic query someone would share.
        page.goto(f"{args.url}/?q=python&workplace=remote,hybrid")
        page.wait_for_selector(".card")
        page.wait_for_selector(".top__stats")
        page.wait_for_timeout(300)
        page.screenshot(path=str(out / "screenshot.png"))

        # 2. A cross-posted job open in the detail drawer.
        page.goto(f"{args.url}/?sort=salary")
        page.wait_for_selector(".card")
        cards = page.locator(".card", has=page.locator(".board:nth-child(2)"))
        (cards.first if cards.count() else page.locator(".card").first).locator(".card__open").click()
        page.wait_for_selector(".drawer h2")
        page.evaluate("window.scrollTo(0, 0)")  # the drawer is fixed; keep the list behind it at the top
        page.wait_for_timeout(250)
        page.screenshot(path=str(out / "detail.png"))

        # 3. Phone width.
        phone = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, color_scheme=args.scheme)
        phone.goto(f"{args.url}/?tags=Kubernetes")
        phone.wait_for_selector(".card")
        phone.wait_for_timeout(250)
        phone.screenshot(path=str(out / "mobile.png"))
        browser.close()
    print(f"saved screenshots to {out}")


if __name__ == "__main__":
    main()

def extract_text(data=None):
    if data is None:
        return None
    return data