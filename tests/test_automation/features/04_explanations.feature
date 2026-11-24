@desktop
Feature: Aligning explanations
  Alt+Right / Alt+Left move the explanations. They always keep 3 spaces after
  their text and line up in one column whenever the text allows it.

  Requirements: REQ-EXPL-001 .. REQ-EXPL-006, REQ-FILE-007

  Background:
    Given Nodeon is open with the test file "tree_a.txt"

  Scenario: TC-EXPL-001 Moving right brings every explanation into one column
    When I press "Alt+Right" 5 times
    Then every explanation is in the same column

  Scenario: TC-EXPL-002 Moving left stops 3 spaces after the text
    When I press "Alt+Left" 40 times
    Then every explanation is exactly 3 spaces after its name
    And line 7 is "│           ➡️ second line"

  Scenario: TC-FILE-007 Saving keeps the moved explanations
    When I press "Alt+Right" 5 times
    And I save the tree
    Then the saved file contains the line "└── README.md                          ➡️ Overview"
