"""
The same kind of check as plain pytest + Playwright (no Gherkin) - shorter,
for developers; the BDD version is readable for non-programmers. Also shows a
Playwright-only capability: emulating the dark colour scheme.
"""
import pytest
from playwright.sync_api import Page, expect

from web_conftest_helpers import REPORT


@pytest.mark.req("REQ-TOOL-002")
def test_TC_TOOL_002_text_filter_matches_titles_and_test_cases(page: Page):
    page.goto(REPORT.as_uri())
    page.get_by_label("Filter").fill("TC-LEG-007")
    rows = page.locator("#matrix tbody tr:visible")
    expect(rows).to_have_count(1)
    expect(rows.locator("td.id")).to_have_text("REQ-LEG-009")
    page.get_by_label("Filter").fill("zzz-nothing")
    expect(page.locator("#empty")).to_be_visible()


@pytest.mark.req("REQ-TOOL-001")
def test_TC_TOOL_001_readable_in_dark_mode(page: Page):
    page.emulate_media(color_scheme="dark")
    page.goto(REPORT.as_uri())
    bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert bg == "rgb(22, 24, 29)"
    expect(page.locator("#matrix tbody tr").first).to_be_visible()
