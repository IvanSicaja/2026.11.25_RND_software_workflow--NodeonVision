"""
Playwright + pytest-bdd: the traceability report tested in a real browser
(Chromium, headless). Same style as the Hamilton web framework: Gherkin
scenarios -> pytest-bdd steps -> Playwright `page` object.
"""
import yaml
from playwright.sync_api import Page, expect
from pytest_bdd import given, parsers, scenarios, then, when

from web_conftest_helpers import REPORT, SPECS

scenarios("../features_web/traceability_report.feature")


def requirement_ids():
    data = yaml.safe_load((SPECS / "requirements.yaml").read_text(encoding="utf-8"))
    return [r["id"] for r in data["requirements"]]


@given("the traceability report is open in the browser")
def _(page: Page):
    assert REPORT.exists(), "run tools/generate_docs.py first"
    page.goto(REPORT.as_uri())
    expect(page.get_by_role("heading", level=1)).to_contain_text("Traceability")


@then("the report has one row for every requirement in the specification")
def _(page: Page):
    rows = page.locator("#matrix tbody tr")
    expect(rows).to_have_count(len(requirement_ids()))
    ids = rows.locator("td.id").all_inner_texts()
    assert ids == requirement_ids()


@when(parsers.parse('I type "{text}" into the filter'))
def _(page: Page, text):
    page.get_by_label("Filter").fill(text)


@when("I clear the filter")
def _(page: Page):
    page.get_by_label("Filter").fill("")


@then(parsers.parse('only the requirement "{rid}" is shown'))
def _(page: Page, rid):
    visible = page.locator("#matrix tbody tr:visible")
    expect(visible).to_have_count(1)
    expect(visible.locator("td.id")).to_have_text(rid)
    expect(page.locator("#count")).to_have_text(f"1 of {len(requirement_ids())} shown")


@then("every requirement is shown")
def _(page: Page):
    expect(page.locator("#matrix tbody tr:visible")).to_have_count(len(requirement_ids()))


@when(parsers.parse('I choose the status "{status}"'))
def _(page: Page, status):
    page.get_by_label("Status").select_option(status)


@then(parsers.parse('every shown row has the status "{status}"'))
def _(page: Page, status):
    visible = page.locator("#matrix tbody tr:visible")
    badges = visible.locator(".badge").all_inner_texts()
    if not badges:
        expect(page.locator("#empty")).to_be_visible()      # "no requirement matches"
    assert all(b == status for b in badges), badges


@then("the summary tiles match the rows of the table")
def _(page: Page):
    rows = page.locator("#matrix tbody tr")
    statuses = rows.locator(".badge").all_inner_texts()
    expect(page.locator("#sum-total")).to_have_text(str(len(statuses)))
    for status in ("passed", "failed", "manual"):
        expect(page.locator(f"#sum-{status}")).to_have_text(str(statuses.count(status)))
    covered = sum(1 for t in rows.locator("td:nth-child(3)").all_inner_texts() if t.strip() != "–")
    expect(page.locator("#sum-covered")).to_have_text(str(covered))
