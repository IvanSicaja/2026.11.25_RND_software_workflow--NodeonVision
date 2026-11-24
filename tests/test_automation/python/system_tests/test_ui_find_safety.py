"""pytest system tests - find bar, window / toolbar / themes / help, error handling."""
import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtTest import QTest

from nodeon_driver import ARROW

TOOLBAR_ORDER = [
    "Open", "Save", "Collapse all", "Collapse level", "Expand level", "Expand all",
    "Explanations ←", "Explanations →", "Column select", "Mark line", "Mark words",
    "Add item", "Add sub-item", "Empty line", "Explanation", "Move up", "Move down",
    "Move left", "Move right", "Format", "Delete line", "Delete branch",
]


def _find(drv, text, case=False):
    bar = drv.win.findbar
    bar.case.setChecked(case)
    bar.field.setText(text)
    QTest.keyClick(bar.field, Qt.Key.Key_Return)
    drv.wait(5)
    return drv.editor.textCursor().selectedText(), bar.info.text()


# ---------------------------------------------------------------------- FIND
@pytest.mark.req("REQ-FIND-001")
def test_TC_FIND_001_next_case_wrap_not_found_escape(drv):
    drv.open_test_file("tree_b_example_project.txt")
    drv.press("Ctrl+F")
    assert drv.win.findbar.isVisible()
    selected, _info = _find(drv, "models")
    assert selected.lower() == "models"
    infos = []
    for _ in range(8):
        drv.press("F3")
        infos.append(drv.win.findbar.info.text())
    assert "Wrapped around" in infos
    assert _find(drv, "MODELS", case=True)[1] == "Not found"
    assert _find(drv, "xyz-not-there")[1] == "Not found"
    QTest.keyClick(drv.win.findbar, Qt.Key.Key_Escape)
    assert not drv.win.findbar.isVisible()


@pytest.mark.req("REQ-FIND-002")
def test_TC_FIND_002_match_in_folded_branch_is_revealed(drv):
    drv.open_test_file("tree_b_example_project.txt")
    drv.press("Alt+1")
    drv.press("Ctrl+F")
    selected, _ = _find(drv, "02_tableau")
    assert selected == "02_tableau"
    assert drv.editor.textCursor().block().isVisible()


# ------------------------------------------------------------------------ UI
@pytest.mark.req("REQ-UI-001", "REQ-UI-002")
def test_TC_UI_001_toolbar_order_captions_tooltips(drv):
    drv.open_test_file("tree_a.txt")
    assert drv.toolbar_buttons() == TOOLBAR_ORDER
    buttons = {b._label: b for b in drv.win.findChildren(drv.m.ActionButton)}
    captions = {label: b._keys() for label, b in buttons.items()}
    assert captions["Collapse all"] == "Alt+1"
    assert captions["Delete line"] == "Ctrl+Q"
    assert captions["Delete branch"] == "Ctrl+Shift+Del"
    assert captions["Explanation"] == "Ctrl+Shift+E"
    assert captions["Mark line"] == "Alt+G/O/R/C"
    assert all(b.defaultAction().toolTip() for b in buttons.values())


@pytest.mark.req("REQ-UI-003")
def test_TC_UI_002_theme_switch_keeps_folds_and_is_remembered(drv):
    drv.open_test_file("tree_b_example_project.txt")
    drv.press("Ctrl+1")
    folded = drv.editor.collapsed_headers()
    for dark in (True, False, True):
        drv.win._set_dark(dark)
        assert drv.editor.collapsed_headers() == folded
        assert drv.editor._rev_ok()                       # fold arrows stay drawn
    assert QColor(drv.editor.theme.bg).name() == "#1e1f22"
    drv.new_window()                                       # restart
    assert drv.win.a_dark.isChecked()


@pytest.mark.req("REQ-UI-004")
def test_TC_UI_003_zoom_limits_reset_and_remembered(drv):
    drv.open_test_file("tree_a.txt")
    assert drv.editor.font_size() == 12
    drv.press("Ctrl+=", 3)
    assert drv.editor.font_size() == 15
    drv.press("Ctrl+0")
    assert drv.editor.font_size() == 12
    drv.press("Ctrl+-", 20)
    assert drv.editor.font_size() == 6                     # lower limit
    drv.new_window()                                       # closing saves the size
    assert drv.editor.font_size() == 6


@pytest.mark.req("REQ-UI-005")
def test_TC_UI_004_colours_of_lines_folders_files_explanations(drv):
    drv.open_test_file("tree_a.txt")
    t = drv.editor.theme
    assert drv.colours_of(2, "├──") == {QColor(t.guide).name()}
    assert drv.colour_of_text("src/") == {QColor(t.folder).name()}
    assert drv.colour_of_text("main.py") == {QColor(t.file).name()}
    assert drv.colour_of_text("Source code") == {QColor(t.comment).name()}
    block = drv.editor.document().findBlockByNumber(2)
    weights = {r.format.fontWeight() for r in block.layout().formats()
               if r.format.foreground().color().name() == QColor(t.folder).name()}
    assert weights == {QFont.Weight.DemiBold}


@pytest.mark.req("REQ-UI-006")
def test_TC_UI_005_status_bar_breadcrumb_and_position(drv):
    drv.open_test_file("tree_a.txt")
    drv.cursor_on("main.py", offset=2)
    assert drv.win.path_label.text().strip() == "project/ › src/ › main.py"
    assert drv.win.pos_label.text().startswith("Ln 4, Col ")


@pytest.mark.req("REQ-UI-007")
def test_TC_UI_006_help_lists_shortcuts_and_about(drv):
    drv.open_test_file("tree_a.txt")
    drv.press("F1")
    help_text = [t for k, t in drv.messages if k == "information"][-1]
    for expected in ("Collapse all / Expand all", "Delete line (sub-items kept)",
                     "Accepted", "Whole name: Alt+G"):
        assert expected in help_text, expected
    drv.win.a_about.trigger()
    about = [t for k, t in drv.messages if k == "about"][-1]
    assert "Nodeon" in about and drv.m.APP_VERSION in about and drv.m.APP_VERSION == "1.1.0"


@pytest.mark.req("REQ-UI-008")
def test_TC_UI_007_settings_minimum_column(drv):
    drv.open_test_file("tree_a.txt")

    def fill(dlg):
        dlg.min_col.setValue(40)
        dlg.accept()
    drv.when_dialog(fill)
    drv.win.a_settings.trigger()
    drv.wait(30)
    cols = [line.index(ARROW) for line in drv.lines()
            if ARROW in line and line[:line.index(ARROW)].strip("│ ")]
    assert min(cols) >= 40
    assert int(drv.win.settings.value("min_comment_column")) == 40


# ---------------------------------------------------------------------- SAFE
@pytest.mark.req("REQ-SAFE-001")
def test_TC_SAFE_001_unexpected_error_dialog_keeps_text(drv, monkeypatch):
    drv.open_test_file("tree_a.txt")
    before = drv.text()
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)   # restored afterwards
    drv.m._install_excepthook()
    try:
        raise RuntimeError("simulated failure")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    shown = [t for k, t in drv.messages if k == "critical"]
    assert shown and "unexpected error" in shown[-1] and "simulated failure" in shown[-1]
    assert drv.win.isVisible() and drv.text() == before
