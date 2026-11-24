Feature: Traceability report (validation of a QMS tool)
  The HTML traceability report is used as quality evidence. Software used in
  the quality system must itself be validated (ISO 13485 clause 4.1.6), so we
  test it like a product - in a real browser, with Playwright.

  Requirements: REQ-TOOL-001, REQ-TOOL-002, REQ-TOOL-003

  Background:
    Given the traceability report is open in the browser

  Scenario: TC-TOOL-001 The report lists every requirement
    Then the report has one row for every requirement in the specification

  Scenario: TC-TOOL-002 Filtering by a requirement id shows only that row
    When I type "REQ-FOLD-003" into the filter
    Then only the requirement "REQ-FOLD-003" is shown
    When I clear the filter
    Then every requirement is shown

  Scenario Outline: TC-TOOL-002 Filtering by status shows only rows with that status
    When I choose the status "<status>"
    Then every shown row has the status "<status>"

    Examples:
      | status |
      | passed |
      | failed |
      | manual |

  Scenario: TC-TOOL-003 The summary tiles match the rows
    Then the summary tiles match the rows of the table
