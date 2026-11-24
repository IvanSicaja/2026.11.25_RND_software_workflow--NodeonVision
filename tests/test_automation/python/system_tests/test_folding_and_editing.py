"""pytest system tests - folding, structural editing and keyboard behaviour."""
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from nodeon_driver import ARROW

ASSETS_HIDDEN = 10        # lines inside 'assets/' in tree_b_example_project.txt


def _arrow_point(drv, line_number):
    """Middle of the fold arrow next to a line (gutter coordinates)."""
    block = drv.editor.document().findBlockByNumber(line_number - 1)
    geo = drv.editor.blockBoundingGeometry(block).translated(drv.editor.contentOffset())
    return QPoint(drv.editor.gutter.width() - 8, int(geo.center().y()))


# ---------------------------------------------------------------------- FOLD
@pytest.mark.req("REQ-FOLD-004", "REQ-FOLD-005")
def test_TC_FOLD_002_levels_change_one_by_one(drv):
    drv.open_test_file("tree_b_example_project.txt")
    seen = []
    for keys in ("Alt+2", "Alt+2", "Alt+2", "Alt+3", "Alt+3", "Alt+3"):
        drv.press(keys)
        seen.append(drv.level()[0])
    assert seen == [2, 1, 0, 1, 2, 3]
    assert drv.status().startswith("Showing") or "Expanded" in drv.status()


@pytest.mark.req("REQ-FOLD-005")
def test_TC_FOLD_003_levels_box_follows_and_controls(drv):
    drv.open_test_file("tree_b_example_project.txt")
    drv.press("Ctrl+1")
    assert drv.win.level_spin.value() == 1
    assert drv.win.level_spin.suffix() == " / 3"
    drv.win.level_spin.setValue(2)                       # the box itself
    assert drv.level() == (2, 3)


@pytest.mark.req("REQ-FOLD-001", "REQ-FOLD-002")
def test_TC_FOLD_004_arrow_click_and_alt_click(drv):
    drv.open_test_file("tree_b_example_project.txt")
    total = drv.visible_lines()
    QTest.mouseClick(drv.editor.gutter, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, _arrow_point(drv, 4))
    assert drv.visible_lines() == total - ASSETS_HIDDEN
    QTest.mouseClick(drv.editor.gutter, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, _arrow_point(drv, 4))
    assert drv.visible_lines() == total
    QTest.mouseClick(drv.editor.gutter, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.AltModifier, _arrow_point(drv, 4))
    assert {3, 5} <= drv.editor.collapsed_headers()       # assets/ and 01_media/


@pytest.mark.req("REQ-FOLD-006", "REQ-FOLD-002")
def test_TC_FOLD_005_fold_branch_at_cursor_fully(drv):
    drv.open_test_file("tree_b_example_project.txt")
    drv.cursor_on("assets/")
    drv.press("Ctrl+Shift+.")
    assert {3, 5} <= drv.editor.collapsed_headers()
    drv.press("Ctrl+Shift+,")
    assert drv.editor.collapsed_headers() == set()


@pytest.mark.req("REQ-FOLD-007")
def test_TC_FOLD_006_badge_counts_and_opens(drv):
    drv.open_test_file("tree_b_example_project.txt")
    drv.cursor_on("docs/")
    drv.press("Ctrl+.")
    line = drv.find("docs/")[0]
    block = drv.editor.document().findBlockByNumber(line)
    geo = drv.editor.blockBoundingGeometry(block).translated(drv.editor.contentOffset())
    rect, label = drv.editor._badge(block, geo)
    assert label == "⋯ 5 items"
    QTest.mouseClick(drv.editor.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, rect.center().toPoint())
    assert line not in drv.editor.collapsed_headers()


@pytest.mark.req("REQ-FOLD-008")
@pytest.mark.parametrize("action", ["type", "align", "mark", "move"])
def test_TC_FOLD_007_folds_survive_actions(drv, action):
    drv.open_test_file("tree_b_example_project.txt")
    drv.press("Ctrl+1")
    folded = drv.editor.collapsed_headers()
    if action == "type":
        drv.cursor_end_of_line(1)
        drv.type("x")
    elif action == "align":
        drv.press("Alt+Right")
    elif action == "mark":
        drv.cursor_on("bills/")
        drv.press("Alt+G")
    else:
        drv.cursor_on("bills/")
        drv.press("Alt+Shift+Up")
    assert len(drv.editor.collapsed_headers()) == len(folded)


@pytest.mark.req("REQ-FOLD-009")
def test_TC_FOLD_008_cursor_skips_folded_and_backspace_unfolds(drv):
    drv.open_test_file("tree_b_example_project.txt")
    drv.cursor_on("assets/")
    drv.press("Ctrl+.")
    before = drv.text()
    drv.press("Down")
    cur = drv.editor.textCursor()
    assert cur.block().isVisible()
    assert cur.blockNumber() > 3 + ASSETS_HIDDEN - 1
    drv.press("Home")
    drv.press("Backspace")
    assert drv.text() == before
    assert drv.status() == "Expanded the folded branch first"


# ---------------------------------------------------------------------- EDIT
@pytest.mark.req("REQ-EDIT-001", "REQ-EDIT-002")
def test_TC_EDIT_001_add_item_and_sub_item_by_keys(drv):
    drv.open_test_file("tree_a.txt")
    drv.cursor_on("main.py")
    drv.press("Ctrl+Enter")
    drv.type("util.py")
    drv.press("Ctrl+Shift+Enter")
    drv.type("inner.txt")
    assert drv.lines()[4] == "│   ├── util.py"
    assert drv.lines()[5] == "│   │   └── inner.txt"


@pytest.mark.req("REQ-EDIT-003")
def test_TC_EDIT_002_first_item_cannot_move_further_up(drv):
    drv.open_test_file("tree_a.txt")
    drv.cursor_on("src/")
    before = drv.text()
    drv.press("Alt+Shift+Up")
    assert drv.text() == before
    assert drv.status() == "Already the first item in its branch"


@pytest.mark.req("REQ-EDIT-005", "REQ-EDIT-006")
def test_TC_EDIT_003_duplicate_then_delete_branch(drv):
    drv.open_test_file("tree_a.txt")
    drv.cursor_on("src/")
    drv.press("Ctrl+D")
    assert drv.text().count("main.py") == 2              # copy with its sub-items
    assert drv.editor.textCursor().blockNumber() > drv.find("src/")[0]   # cursor on the copy
    drv.press("Ctrl+Shift+Delete")
    assert drv.text().count("main.py") == 1
    assert drv.text().count("src/") == 1
    assert drv.status() == "Deleted branch and 2 sub-item(s) - Ctrl+Z to undo"
    # Note: the empty line copied with the branch stays (see ANOMALY-002).


@pytest.mark.req("REQ-EDIT-010")
def test_TC_EDIT_006_edit_dialog_name_and_two_line_explanation(drv):
    drv.open_test_file("tree_a.txt")
    drv.cursor_on("README.md")
    drv.press("F2")
    assert drv.text().count(ARROW) == 6                    # F2 did nothing
    seen = {}

    def fill(dlg):
        seen["title"] = dlg.windowTitle()
        seen["name"] = dlg.name.text()
        dlg.explanation.setPlainText("Overview\nRead me first")
        dlg.accept()
    drv.when_dialog(fill)
    drv.press("Ctrl+Shift+E")
    drv.wait(50)
    assert seen == {"title": "Edit branch", "name": "README.md"}
    readme = drv.find("README.md")[0]
    first, second = drv.lines()[readme], drv.lines()[readme + 1]
    assert first.endswith(f"{ARROW} Overview") and second.endswith(f"{ARROW} Read me first")
    assert first.index(ARROW) == second.index(ARROW)


@pytest.mark.req("REQ-EDIT-010")
def test_TC_EDIT_006_ctrl_e_focuses_the_explanation(drv):
    drv.open_test_file("tree_a.txt")
    drv.cursor_on("README.md")
    seen = {}

    def check(dlg):
        drv.wait(20)
        seen["focus"] = dlg.focusWidget() is dlg.explanation
        dlg.reject()
    drv.when_dialog(check)
    drv.press("Ctrl+E")
    drv.wait(50)
    assert seen == {"focus": True}


@pytest.mark.req("REQ-EDIT-011")
def test_TC_EDIT_007_invalid_name_refused(drv):
    drv.open_test_file("tree_a.txt")
    drv.cursor_on("README.md")
    seen = {}

    def fill(dlg):
        dlg.name.setText(f"a {ARROW} b")
        dlg.accept()                                    # refused -> stays open
        seen["still_open"] = dlg.isVisible()
        dlg.reject()
    drv.when_dialog(fill)
    drv.press("Ctrl+Shift+E")
    drv.wait(50)
    assert seen == {"still_open": True}
    assert any("Invalid name" in t for k, t in drv.messages if k == "warning")
    assert "README.md" in drv.text()


@pytest.mark.req("REQ-EDIT-012", "REQ-SAFE-002")
@pytest.mark.parametrize("keys, where", [
    ("Alt+Shift+Up", "docs/"), ("Alt+Shift+Down", "src/"), ("Alt+Shift+Right", "README.md"),
    ("Alt+Shift+Left", "main.py"), ("Ctrl+D", "src/"), ("Ctrl+Shift+Delete", "src/"),
    ("Ctrl+Q", "src/"), ("Alt+Enter", "main.py"), ("Ctrl+Enter", "docs/"),
    ("Ctrl+Shift+Enter", "README.md"), ("Alt+Right", None), ("Alt+Left", None),
])
def test_TC_EDIT_008_every_command_is_one_undo_step(drv, keys, where):
    drv.open_test_file("tree_a.txt")
    before = drv.text()
    if where:
        drv.cursor_on(where)
    drv.press(keys)
    after = drv.text()
    assert after != before, f"{keys} changed nothing"
    drv.press("Ctrl+Z")
    assert drv.text() == before
    drv.press("Ctrl+Y")
    assert drv.text() == after


@pytest.mark.req("REQ-SAFE-002")
@pytest.mark.parametrize("keys, where", [
    ("Alt+Shift+Up", "docs/"), ("Alt+Shift+Down", "bills/"), ("Alt+Shift+Right", "data/"),
    ("Alt+Shift+Left", "raw/"), ("Alt+Enter", "02_figures/"), ("Alt+Right", None),
    ("Alt+Left", None), ("Ctrl+Alt+L", None),
])
def test_TC_SAFE_002_commands_keep_every_name(drv, keys, where):
    """Invariant: moving / spacing / aligning never loses or changes a name."""
    drv.open_test_file("tree_b_example_project.txt")
    drv.editor.ensure_parsed()
    names = sorted(n.name for n in drv.editor._model.iter_nodes())
    comments = sorted(c for n in drv.editor._model.iter_nodes() for c in n.comment)
    if where:
        drv.cursor_on(where)
    drv.press(keys)
    drv.editor.ensure_parsed()
    assert sorted(n.name for n in drv.editor._model.iter_nodes()) == names
    assert sorted(c for n in drv.editor._model.iter_nodes() for c in n.comment) == comments


# ----------------------------------------------------------------------- KEY
@pytest.mark.req("REQ-KEY-002")
def test_TC_KEY_002_split_and_insert_before(drv):
    drv.open_test_file("tree_a.txt")
    drv.cursor_on("main.py", offset=4)
    drv.press("Enter")
    assert drv.lines()[3].startswith("│   ├── main") and drv.lines()[4].startswith("│   ├── .py")
    drv.press("Ctrl+Z")
    drv.cursor_on("main.py", offset=0)
    drv.press("Enter")
    assert drv.lines()[3] == "│   ├── "
    assert drv.lines()[4].startswith("│   ├── main.py")


@pytest.mark.req("REQ-KEY-003")
def test_TC_KEY_003_enter_outdents_backspace_removes(drv):
    drv.open_test_file("tree_a.txt")
    original = drv.text()
    drv.cursor_after("main.py")
    drv.press("Enter")
    assert drv.lines()[4] == "│   ├── "
    drv.press("Enter")
    assert drv.lines()[5] == "├── "
    drv.press("Backspace")
    assert drv.text() == original


@pytest.mark.req("REQ-KEY-004")
def test_TC_KEY_004_tab_on_empty_line_and_shift_enter(drv):
    drv.open_test_file("tree_a.txt")
    drv.cursor_start_of_line(2)
    drv.press("Tab")
    assert drv.lines()[1] == "    │"
    drv.cursor_end_of_line(1)
    drv.press("Shift+Enter")
    assert drv.lines()[0] == "project/" and drv.lines()[1] == ""


@pytest.mark.req("REQ-KEY-005")
@pytest.mark.parametrize("keys, where, check", [
    ("Alt+Shift+Up", "docs/", lambda t: t.index("docs/") < t.index("src/")),
    ("Ctrl+Shift+Delete", "docs/", lambda t: "docs/" not in t),
    ("Ctrl+Enter", "src/", lambda t: t.count("├── ") == 4),
])
def test_TC_KEY_005_application_shortcuts_win(drv, keys, where, check):
    drv.open_test_file("tree_a.txt")
    drv.cursor_on(where)
    drv.press(keys)
    assert check(drv.text()), drv.text()
