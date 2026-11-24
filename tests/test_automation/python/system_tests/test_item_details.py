"""
pytest system tests - the "Item details" panel (pictures, must-have features,
features to avoid) on the right side of Nodeon.

Every test is named test_TC_ITEM_<NNN>_... so the report generator links it to
its test case (specs/test_cases.yaml) and through it to the requirements.
"""
import json
import os
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

GARAGE = """garage/
│
├── Workbench/
│   ├── Cordless drill
│   ├── Hammer
│   └── Saw
├── Shelf B/
│   └── Paint cans
└── Bikes/
    └── City bike"""


@pytest.fixture
def garage(drv):
    drv.open_text(GARAGE, "garage.txt")
    return drv


def _pics(drv, n=3):
    colours = ["#d33", "#3a3", "#33d", "#aa3", "#3aa"]
    return [drv.make_picture(f"photo {i}.png", 60 + 10 * i, 40, colours[i]) for i in range(n)]


# ------------------------------------------------------------------ panel
@pytest.mark.req("REQ-ITEM-001")
def test_TC_ITEM_001_panel_on_the_right_shows_the_item_at_the_cursor(garage):
    drv = garage
    assert drv.panel.isVisible()
    from PySide6.QtCore import QPoint
    x_panel = drv.panel.mapTo(drv.win, QPoint(0, 0)).x()
    x_editor = drv.editor.mapTo(drv.win, QPoint(0, 0)).x()
    assert x_panel > x_editor + drv.editor.width() // 2       # right of the tree
    drv.show_item("Hammer")
    assert drv.item_title() == "Hammer"
    assert drv.panel.crumbs.text() == "garage/ › Workbench/"
    drv.cursor_start_of_line(2)                  # the empty line under garage/
    drv.sync_panel()
    assert drv.item_title() == ""
    assert "Put the cursor on an item" in drv.panel.placeholder.text()
    # hide / show via View menu, remembered for the next start
    drv.win.a_details.trigger()
    assert not drv.panel.isVisible()
    drv.reopen()
    assert not drv.panel.isVisible()
    drv.win.a_details.trigger()
    assert drv.panel.isVisible()


# ----------------------------------------------------------- add pictures
@pytest.mark.req("REQ-ITEM-002", "REQ-ITEM-003")
def test_TC_ITEM_002_add_pictures_by_drop_browse_and_paste(garage):
    drv = garage
    p = _pics(drv, 4)
    drv.show_item("Cordless drill")
    drv.drop_pictures(p[0], p[1])
    assert drv.picture_names("Cordless drill") == ["photo 0.png", "photo 1.png"]
    drv.browse_pictures(p[2])
    assert drv.picture_names("Cordless drill")[-1] == "photo 2.png"
    img = QImage(20, 20, QImage.Format.Format_RGB32)
    img.fill(QColor("#123456"))
    QApplication.clipboard().setImage(img)
    drv.panel.view.setFocus()
    QTest.keyClick(drv.panel.view, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    drv.wait(10)
    assert len(drv.picture_names("Cordless drill")) == 4
    assert drv.picture_counter() == "4 / 4"
    assert drv.win.isWindowModified()


@pytest.mark.req("REQ-ITEM-003")
def test_TC_ITEM_003_files_that_are_not_pictures_are_refused(garage):
    drv = garage
    drv.show_item("Saw")
    note = drv.workdir / "notes.txt"
    note.write_text("hello")
    fake = drv.workdir / "fake.jpg"
    fake.write_text("not really a jpeg")
    drv.drop_pictures(note, fake)
    assert drv.item_details("Saw") is None
    assert "not a picture" in drv.status()
    assert "notes.txt" in drv.status()


# -------------------------------------------------------------- slideshow
@pytest.mark.req("REQ-ITEM-004")
def test_TC_ITEM_004_previous_next_slideshow(garage):
    drv = garage
    drv.show_item("Cordless drill")
    drv.browse_pictures(*_pics(drv, 3))
    drv.panel.select_image(0)
    seen = []
    for _ in range(4):
        seen.append((drv.picture_counter(), drv.shown_picture_size()[0]))
        drv.panel.b_next.click()
    assert seen == [("1 / 3", 60), ("2 / 3", 70), ("3 / 3", 80), ("3 / 3", 80)]
    drv.panel.view.setFocus()
    QTest.keyClick(drv.panel.view, Qt.Key.Key_Left)
    assert drv.picture_counter() == "2 / 3"
    drv.panel.thumbs.setCurrentRow(0)
    assert drv.picture_counter() == "1 / 3"


@pytest.mark.req("REQ-ITEM-005")
def test_TC_ITEM_005_zoom_in_out_fit(garage):
    drv = garage
    drv.show_item("City bike")
    drv.browse_pictures(drv.make_picture("big.png", 2400, 1600))
    v = drv.panel.view
    fit = v.scale_factor()
    assert fit < 1
    drv.panel.b_zoom_in.click()
    drv.panel.b_zoom_in.click()
    assert v.scale_factor() == pytest.approx(fit * 1.25 * 1.25)
    assert drv.panel.zoom_label.text() == f"{v.zoom_percent()} %"
    drv.panel.b_zoom_out.click()
    assert v.scale_factor() == pytest.approx(fit * 1.25)
    drv.panel.b_fit.click()
    assert v.scale_factor() == pytest.approx(fit)
    # zoom is kept while the editor re-reads the text in the background
    drv.panel.b_zoom_in.click()
    zoomed = v.scale_factor()
    drv.sync_panel()
    assert v.scale_factor() == pytest.approx(zoomed)


@pytest.mark.req("REQ-ITEM-006")
def test_TC_ITEM_006_large_viewer(garage):
    drv = garage
    drv.show_item("Hammer")
    drv.browse_pictures(*_pics(drv, 2))
    drv.panel.select_image(0)
    dlg = drv.panel.open_viewer()
    drv.wait(10)
    assert dlg.isVisible() and dlg.counter.text() == "1 / 2"
    dlg.b_next.click()
    assert drv.picture_counter() == "2 / 2"
    dlg.b_close.click()
    drv.wait(10)
    assert drv.panel._viewer is None


# ---------------------------------------------------------- remove / order
@pytest.mark.req("REQ-ITEM-007")
def test_TC_ITEM_007_remove_picture_after_confirmation(garage):
    drv = garage
    drv.show_item("Hammer")
    drv.browse_pictures(*_pics(drv, 2))
    drv.panel.select_image(0)
    drv.answers.append("No")
    drv.panel.b_remove.click()
    assert len(drv.picture_names("Hammer")) == 2
    drv.answers.append("Yes")
    drv.panel.b_remove.click()
    assert drv.picture_names("Hammer") == ["photo 1.png"]
    assert any("Remove the picture" in t for _k, t in drv.messages)


@pytest.mark.req("REQ-ITEM-008")
def test_TC_ITEM_008_change_the_order(garage):
    drv = garage
    drv.show_item("Hammer")
    drv.browse_pictures(*_pics(drv, 3))
    drv.panel.select_image(0)
    drv.panel.b_move_right.click()
    assert drv.picture_names("Hammer") == ["photo 1.png", "photo 0.png", "photo 2.png"]
    files = drv.item_details("Hammer").files()
    drv.panel.thumbs.orderChanged.emit([files[2], files[0], files[1]])     # dragged thumbnail
    assert drv.picture_names("Hammer") == ["photo 2.png", "photo 1.png", "photo 0.png"]


# ---------------------------------------------------------------- features
@pytest.mark.req("REQ-ITEM-009", "REQ-ITEM-010", "REQ-ITEM-016")
def test_TC_ITEM_009_must_have_and_avoid_sections(garage):
    drv = garage
    drv.show_item("Cordless drill")
    drv.type_features("must", "18 V battery\n2 speeds")
    drv.type_features("avoid", "corded")
    d = drv.item_details("Cordless drill")
    assert (d.must, d.avoid) == ("18 V battery\n2 speeds", "corded")
    assert drv.panel.must.header.text().startswith("✓  Must-have features")
    assert drv.panel.must.header.text().endswith("·  2")
    assert drv.panel.avoid.header.text().startswith("✕  Features to avoid")
    for dark in (False, True):
        drv.win._set_dark(dark, save=False)
        g = QColor(drv.panel.must.header.styleSheet().split("background:")[1].split(";")[0].strip())
        r = QColor(drv.panel.avoid.header.styleSheet().split("background:")[1].split(";")[0].strip())
        assert 90 <= g.hslHue() <= 160, g.name()                 # green
        assert r.hslHue() >= 330 or r.hslHue() <= 15, r.name()   # red
        if not dark:
            assert g.lightness() > 190 and r.lightness() > 190   # light, soft
    drv.win._set_dark(False, save=False)
    drv.show_item("Saw")
    assert drv.panel.must.text() == "" and drv.panel.avoid.text() == ""
    drv.panel.must.body.setPlainText("\n".join(f"feature {i}" for i in range(200)))
    drv.wait(10)
    assert drv.panel.must.body.verticalScrollBar().maximum() > 0    # scrollable


# --------------------------------------------------------- database / save
@pytest.mark.req("REQ-ITEM-011")
def test_TC_ITEM_011_saved_with_the_tree_and_restored(garage):
    drv = garage
    drv.show_item("Cordless drill")
    drv.browse_pictures(*_pics(drv, 2))
    drv.type_features("must", "18 V")
    assert drv.items_db() is None, "nothing written before saving"
    drv.press("Ctrl+S")
    drv.wait(20)
    db = drv.items_db()
    assert db["items"][0]["path"] == [["garage/", 0], ["Workbench/", 0], ["Cordless drill", 0]]
    assert len(drv.stored_picture_files()) == 2
    assert drv.saved_text() == GARAGE + "\n"                  # the .txt stays pure text
    drv.reopen()
    drv.show_item("Cordless drill")
    assert drv.picture_counter() == "1 / 2"
    assert drv.panel.must.text() == "18 V"


@pytest.mark.req("REQ-ITEM-011")
def test_TC_ITEM_011_close_asks_to_save_picture_changes(garage):
    drv = garage
    drv.show_item("Saw")
    drv.browse_pictures(*_pics(drv, 1))
    drv.answers.append("Save")
    drv.win.close()
    drv.wait(10)
    drv.win = None
    assert len(drv.items_db()["items"]) == 1


# ----------------------------------------------------------- follow the row
@pytest.mark.req("REQ-ITEM-012")
def test_TC_ITEM_012_details_follow_their_row(garage):
    drv = garage
    drv.show_item("Saw")
    drv.browse_pictures(*_pics(drv, 1))
    drv.type_features("must", "saw-must")
    drv.show_item("Hammer")
    drv.type_features("must", "hammer-must")
    drv.show_item("Saw")
    drv.press("Alt+Shift+Up")                  # move up
    drv.press("Alt+Shift+Up")
    drv.press("Tab")                           # into nothing above -> stays / indent
    drv.show_item("Hammer")
    drv.press("Alt+Shift+Right")               # into the item above
    drv.cursor_after("Hammer")
    drv.type(" XL")                            # rename
    drv.show_item("Workbench/")
    drv.press("Ctrl+Q")                        # delete line: children move up a level
    drv.settle()
    assert drv.item_details("Saw").must == "saw-must"
    assert len(drv.item_details("Saw").images) == 1
    assert drv.item_details("Hammer XL").must == "hammer-must"
    for _ in range(30):
        drv.press("Ctrl+Z")
    drv.settle()
    assert drv.text() == GARAGE
    assert drv.item_details("Saw").must == "saw-must"
    assert drv.item_details("Hammer").must == "hammer-must"
    drv.show_item("Saw")
    assert drv.picture_counter() == "1 / 1"


# ----------------------------------------------------- discard / save as / gc
@pytest.mark.req("REQ-ITEM-013")
def test_TC_ITEM_013_discard_save_as_and_cleanup(garage, tmp_path):
    drv = garage
    drv.show_item("Saw")
    drv.browse_pictures(*_pics(drv, 2))
    drv.press("Ctrl+S")
    drv.wait(20)
    before = drv.stored_picture_files()
    db_before = drv.items_db()
    drv.show_item("Hammer")
    drv.browse_pictures(*_pics(drv, 1))
    drv.reopen()                                           # closed with "Discard"
    assert drv.stored_picture_files() == before
    assert drv.items_db() == db_before
    # Save As copies pictures, the original stays complete
    target = tmp_path / "copy" / "garage copy.txt"
    target.parent.mkdir()
    from PySide6.QtWidgets import QFileDialog
    orig = QFileDialog.getSaveFileName
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(target), ""))
    try:
        assert drv.win.save_as()
    finally:
        QFileDialog.getSaveFileName = orig
    assert len(os.listdir(str(target) + ".items/images")) == 2
    assert drv.stored_picture_files() == before
    # a removed picture is deleted from the folder when saving
    drv.path = target
    drv.show_item("Saw")
    drv.panel.delete_image(0, confirm=False)
    drv.press("Ctrl+S")
    drv.wait(20)
    assert len(os.listdir(str(target) + ".items/images")) == 1


# -------------------------------------------------------------- robustness
@pytest.mark.req("REQ-ITEM-014")
def test_TC_ITEM_014_unreadable_database_and_missing_pictures(garage):
    drv = garage
    drv.show_item("Saw")
    drv.browse_pictures(*_pics(drv, 2))
    drv.press("Ctrl+S")
    drv.wait(20)
    files = drv.stored_picture_files()
    (drv.items_folder() / "images" / files[0]).unlink()        # one picture lost
    drv.reopen()
    drv.show_item("Saw")
    assert drv.picture_counter() in ("1 / 2", "2 / 2")
    drv.panel.select_image(drv.item_details("Saw").files().index(files[0]))
    assert not drv.panel.view.has_image() and "missing" in drv.panel.view.message()
    # broken database
    (drv.items_folder() / "items.json").write_text("{broken", encoding="utf-8")
    drv.reopen()
    assert any(k == "warning" and "could not be read" in t for k, t in drv.messages)
    assert drv.text() == GARAGE
    drv.press("Ctrl+S")
    drv.wait(20)
    names = os.listdir(drv.items_folder())
    assert any(n.startswith("items.json.unreadable-") for n in names)
    assert files[1] in drv.stored_picture_files(), "no picture deleted"


@pytest.mark.req("REQ-ITEM-015")
def test_TC_ITEM_015_tree_commands_do_not_fire_while_typing_in_panel(garage):
    drv = garage
    drv.show_item("Saw")
    box = drv.panel.must.body
    box.setFocus()
    for keys in ("Ctrl+D", "Ctrl+Q", "Alt+G", "Ctrl+Return", "Alt+Shift+Up", "Ctrl+Shift+Delete"):
        from PySide6.QtGui import QKeySequence
        combo = QKeySequence(keys)[0]
        QTest.keyClick(box, combo.key(), combo.keyboardModifiers())
    drv.settle()
    assert drv.text() == GARAGE
    QTest.keyClicks(box, "sharp")
    QTest.keyClick(box, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)     # Save works
    drv.wait(20)
    assert not drv.win.isWindowModified()
    assert drv.items_db()["items"][0]["must"] == "sharp"


@pytest.mark.req("REQ-ITEM-017")
def test_TC_ITEM_017_large_tree_performance(drv):
    rows = ["warehouse/"]
    for a in range(40):
        last = a == 39
        rows.append(("└── " if last else "├── ") + f"aisle {a}/")
        for b in range(50):
            rows.append(("    " if last else "│   ") + ("└── " if b == 49 else "├── ") + f"box {a}-{b}")
    drv.open_text("\n".join(rows), "warehouse.txt")
    import itemdetails
    pic = drv.win.item_store.import_file(str(drv.make_picture("p.png")))
    drv.editor.ensure_parsed()
    for node in drv.editor._model.iter_nodes():
        if node.name.startswith("box") and node.name.endswith("0"):
            drv.editor.details[itemdetails.key_of(node)] = itemdetails.ItemDetails(
                [dict(pic)], "must\n" * 5, "avoid")
    count = len(drv.editor.details)
    t = time.perf_counter()
    assert drv.win.save()
    assert time.perf_counter() - t < 10
    t = time.perf_counter()
    drv.reopen()
    assert time.perf_counter() - t < 10
    assert len(drv.editor.details) == count
