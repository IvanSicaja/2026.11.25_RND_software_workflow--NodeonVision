@desktop
Feature: Colour legend
  The legend explains every colour. Own colours (e.g. "Same on both robots")
  can be added and get free shortcuts.

  Requirements: REQ-LEG-001, REQ-LEG-002, REQ-LEG-003

  Background:
    Given Nodeon is open with the test file "tree_a.txt"

  Scenario: TC-LEG-001 The legend shows the standard meanings
    Then the legend shows "Not checked yet (only mentioned)"
    And the legend shows "Accepted"
    And the legend shows "To be approved"
    And the legend shows "Rejected"
    And the legend shows "Explanation"

  Scenario: TC-LEG-002 Add an own colour and use its suggested shortcut
    When I add the colour "Same on both robots" in the legend
    Then the legend shows "Same on both robots"
    When I put the cursor on "src/"
    And I press "Alt+5"
    Then the name "src/" is marked "Same on both robots"
