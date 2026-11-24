@desktop
Feature: Folding the tree
  Large trees need an overview: fold everything, open level by level, or show
  exactly N levels - for the whole document at once.

  Requirements: REQ-FOLD-003, REQ-FOLD-004, REQ-FOLD-005, REQ-FOLD-006

  Background:
    Given Nodeon is open with the test file "tree_b_example_project.txt"

  Scenario: TC-FOLD-001 Collapse all and expand all
    When I press "Alt+1"
    Then the level indicator shows 0 of 3
    When I press "Alt+4"
    Then the level indicator shows 3 of 3

  Scenario: TC-FOLD-002 Collapse and expand one level for the whole document
    When I press "Alt+2"
    Then the level indicator shows 2 of 3
    When I press "Alt+2"
    Then the level indicator shows 1 of 3
    When I press "Alt+3"
    Then the level indicator shows 2 of 3

  Scenario Outline: TC-FOLD-003 Show exactly N levels with Ctrl+number
    When I press "<keys>"
    Then the level indicator shows <shown> of 3

    Examples:
      | keys   | shown |
      | Ctrl+1 | 1     |
      | Ctrl+2 | 2     |
      | Ctrl+9 | 3     |

  @python_only
  Scenario: TC-FOLD-001 Collapse all leaves only the first line visible
    When I press "Alt+1"
    Then 1 lines are visible
    When I press "Alt+4"
    Then 66 lines are visible

  @python_only
  Scenario: TC-FOLD-005 Fold the branch at the cursor
    When I put the cursor on "assets/"
    And I press "Ctrl+."
    Then 56 lines are visible
    When I press "Ctrl+."
    Then 66 lines are visible
