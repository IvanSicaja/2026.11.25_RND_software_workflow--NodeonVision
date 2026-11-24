@desktop
Feature: Structural editing
  Branches are added, moved and deleted with one key; the box-drawing lines
  are always redrawn correctly and every command is one undo step.

  Requirements: REQ-EDIT-001 .. REQ-EDIT-009, REQ-EDIT-012, REQ-KEY-001

  Background:
    Given Nodeon is open with the tree:
      """
      root/
      ├── a/
      │   ├── a1
      │   └── a2
      ├── b
      └── c
      """

  Scenario: TC-EDIT-001 Add an item with the toolbar button
    When I put the cursor at the end of line 3
    And I click the toolbar button "Add item"
    And I type "a3"
    Then the tree is:
      """
      root/
      ├── a/
      │   ├── a1
      │   ├── a3
      │   └── a2
      ├── b
      └── c
      """

  Scenario: TC-EDIT-002 Move a branch with its sub-items up
    When I put the cursor on "b"
    And I press "Alt+Shift+Up"
    Then the tree is:
      """
      root/
      ├── b
      ├── a/
      │   ├── a1
      │   └── a2
      └── c
      """

  Scenario: TC-EDIT-002 Move an item into the item above and back
    When I put the cursor on "c"
    And I press "Alt+Shift+Right"
    Then line 6 is "    └── c"
    When I press "Alt+Shift+Left"
    Then line 6 is "└── c"

  Scenario: TC-EDIT-004 Delete line keeps the sub-items and does not quit
    When I put the cursor on "a/"
    And I press "Ctrl+Q"
    Then the tree is:
      """
      root/
      ├── a1
      ├── a2
      ├── b
      └── c
      """
    And the window is still open

  Scenario: TC-EDIT-005 Insert an empty line that keeps the vertical lines
    When I put the cursor on "a1"
    And I press "Alt+Enter"
    Then line 4 is "│   │"
    And the tree has 7 lines

  Scenario: TC-EDIT-008 Undo restores the tree in one step
    When I put the cursor on "a/"
    And I press "Ctrl+Shift+Delete"
    Then the tree has 3 lines
    When I press "Ctrl+Z"
    Then the tree has 6 lines

  Scenario: TC-KEY-001 Typing a list with Enter and Tab
    When I put the cursor at the end of line 6
    And I press "Enter"
    And I type "d"
    And I press "Tab"
    Then line 7 is "    └── d"
