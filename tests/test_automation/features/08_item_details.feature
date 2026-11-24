Feature: Item details - pictures and features of every item
  On the right of the tree, the "Item details" panel shows the item at the
  cursor: its name, its pictures (add, browse, zoom, previous / next,
  reorder, remove) and two lists - "Must-have features" (green) and
  "Features to avoid" (red). They are saved with the tree in
  <name>.txt.items/ and always stay with their row.

  Requirements: REQ-ITEM-001 ... REQ-ITEM-017
  The scenarios use the Python driver only: the Windows (Reqnroll + FlaUI)
  suite has no driver for the panel yet, so they are tagged @python_only.

  Background:
    Given Nodeon is open with the tree:
      """
      garage/
      │
      ├── Workbench/
      │   ├── Cordless drill
      │   ├── Hammer
      │   └── Saw
      └── Bikes/
          └── City bike
      """

  @python_only
  Scenario: TC-ITEM-001 The panel shows the item at the cursor
    When I put the cursor on "Hammer"
    Then the item panel shows "Hammer"

  @python_only
  Scenario: TC-ITEM-002 Drop pictures onto an item and browse through them
    When I put the cursor on "Cordless drill"
    And I drop 3 pictures onto the item panel
    Then the item "Cordless drill" has 3 pictures
    And the picture counter shows "1 / 3"
    When I show the next picture
    And I show the next picture
    Then the picture counter shows "3 / 3"

  @python_only
  Scenario: TC-ITEM-009 Must-have features and features to avoid
    When I put the cursor on "Saw"
    And I write the must-have features "sharp teeth"
    And I write the features to avoid "plastic handle"
    Then the item "Saw" must have "sharp teeth"
    And the item "Saw" avoids "plastic handle"

  @python_only
  Scenario: TC-ITEM-012 Pictures stay with their row when it moves and after saving
    When I put the cursor on "Saw"
    And I drop 2 pictures onto the item panel
    And I write the must-have features "folding"
    And I press "Alt+Shift+Up"
    And I press "Alt+Shift+Up"
    And I save the tree
    And I reopen the tree
    Then line 4 is "│   ├── Saw"
    And the item "Saw" has 2 pictures
    And the item "Saw" must have "folding"
    And the item "Cordless drill" has 0 pictures
