@desktop
Feature: Pasting lines and column selection
  Lines copied from Word or a PDF become branches on the same level; column
  selection edits several lines at once, like in PyCharm.

  Requirements: REQ-PASTE-001, REQ-PASTE-002, REQ-COL-001 .. REQ-COL-003

  Scenario: TC-PASTE-001 Three pasted lines become three items on the same level
    Given Nodeon is open with the tree:
      """
      root/
      ├── a/
      │   ├── a1
      │   └── a2
      └── b
      """
    When I put the cursor at the end of line 3
    And I press "Enter"
    And I paste:
      """
      First requirement

      Second requirement
      Third requirement
      """
    Then the tree is:
      """
      root/
      ├── a/
      │   ├── a1
      │   ├── First requirement
      │   ├── Second requirement
      │   ├── Third requirement
      │   └── a2
      └── b
      """

  Scenario: TC-COL-002 Type on three lines at once in column mode
    Given Nodeon is open with the tree:
      """
      root/
      ├── alpha
      ├── beta
      └── gamma
      """
    When I put the cursor at the start of line 2
    And I press "Right" 4 times
    And I press "Alt+Shift+Insert"
    And I press "Shift+Down" 2 times
    And I type "x_"
    Then the tree is:
      """
      root/
      ├── x_alpha
      ├── x_beta
      └── x_gamma
      """
