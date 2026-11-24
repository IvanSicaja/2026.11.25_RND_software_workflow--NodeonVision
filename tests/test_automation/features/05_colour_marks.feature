@desktop
Feature: Colour marks
  Names are coloured to track the review state: Accepted, To be approved,
  Rejected. Explanations always keep their own colour.

  Requirements: REQ-MARK-001 .. REQ-MARK-008

  Background:
    Given Nodeon is open with the test file "tree_a.txt"

  Scenario: TC-MARK-001 Colour the whole name of a branch
    When I put the cursor on "src/"
    And I press "Alt+G"
    Then the name "src/" is marked "Accepted"
    And the name "main.py" is marked "Not checked yet (only mentioned)"

  Scenario: TC-MARK-002 Colour only the word at the cursor
    When I put the cursor on "README.md"
    And I press "Alt+Shift+R"
    Then the word "README.md" is marked "Rejected"

  Scenario: TC-MARK-003 The same key again removes the colour
    When I put the cursor on "README.md"
    And I press "Alt+O"
    Then the name "README.md" is marked "To be approved"
    When I press "Alt+O"
    Then the name "README.md" is marked "Not checked yet (only mentioned)"

  Scenario: TC-MARK-006 Colours are stored and come back after reopening
    When I put the cursor on "docs/"
    And I press "Alt+R"
    And I reopen the tree
    Then the name "docs/" is marked "Rejected"

  @python_only
  Scenario: TC-MARK-004 Explanations are never coloured
    When I select "Source code"
    And I press "Alt+Shift+G"
    Then the explanation "Source code" has the explanation colour
