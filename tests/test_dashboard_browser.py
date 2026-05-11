from __future__ import annotations

import os

import pytest
from playwright.sync_api import expect, sync_playwright

ERROR_TERMS = ("Traceback", "StreamlitAPIException", "ValueError:", "TypeError:")


@pytest.mark.skipif(
    "CS2_DASHBOARD_BASE_URL" not in os.environ,
    reason="Set CS2_DASHBOARD_BASE_URL to run browser smoke tests against Streamlit.",
)
@pytest.mark.parametrize(
    ("path", "heading"),
    [
        ("", "CS2 Analytics"),
        ("Upset_Tracker", "Upset Tracker"),
        ("Hidden_Gem_Scout", "Hidden Gem Scout"),
    ],
)
def test_dashboard_page_renders_without_streamlit_errors(
    path: str,
    heading: str,
) -> None:
    """Smoke-test rendered Streamlit pages in a real browser when a server is running."""
    base_url = os.environ["CS2_DASHBOARD_BASE_URL"].rstrip("/")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(f"{base_url}/{path}", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name=heading).first).to_be_visible(timeout=15_000)
        page.wait_for_timeout(3_000)

        body_text = page.locator("body").inner_text()
        browser.close()

    assert not [term for term in ERROR_TERMS if term in body_text]
