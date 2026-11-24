@desktop
Feature: Files and tree format
  Nodeon stores a tree as pure UTF-8 text with box-drawing lines and
  explanations after the arrow. Opening and saving must never change the tree.

  Requirements: REQ-FMT-001, REQ-FMT-002, REQ-FMT-003, REQ-FMT-005, REQ-FILE-002

  Scenario: TC-FMT-001 Opening and saving keeps the tree exactly
    Given Nodeon is open with the test file "tree_a.txt"
    When I save the tree
    Then the saved file is:
      """
      project/
      │
      ├── src/                          ➡️ Source code
      │   ├── main.py                   ➡️ Entry point
      │   └── a_really_long_module_name.py   ➡️ Long one
      ├── docs/                         ➡️ Documentation
      │                                 ➡️ second line
      └── README.md                     ➡️ Overview
      """

  Scenario: TC-FMT-003 A hash sign is ordinary text, not an explanation
    Given Nodeon is open with the tree:
      """
      root/
      └── src/   # note
      """
    When I save the tree
    Then the saved file is:
      """
      root/
      └── src/   # note
      """
    And the name "src/   # note" is marked "Not checked yet (only mentioned)"

  Scenario: TC-FILE-002 Saving writes the new item to the file
    Given Nodeon is open with the test file "tree_a.txt"
    When I put the cursor at the end of line 8
    And I press "Ctrl+Enter"
    And I type "LICENSE"
    And I save the tree
    Then line 9 is "└── LICENSE"
    And the saved file contains the line "└── LICENSE"
