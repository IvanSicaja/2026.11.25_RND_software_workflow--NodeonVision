"""GUI tests for the "Item details" panel (pictures, must-have features,
features to avoid) - drive the real Nodeon window headless.

Run from the project root:
    python -m unittest discover tests
Uses temporary settings and folders; your real Nodeon preferences are untouched.
"""
import json
import os
import random
import shutil
import sys
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "main"))

try:
    from PySide6.QtCore import QMimeData, QPoint, QPointF, QSettings, Qt, QUrl
    from PySide6.QtGui import QColor, QDropEvent, QDragEnterEvent, QImage, QTextCursor, QWheelEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox
except ImportError:                                     # pragma: no cover
    QApplication = None

if QApplication is not None:
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        "nodeon_app_panel", os.path.join(PROJECT_ROOT, "main", "main.py"))
    app_module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(app_module)
    import itemdetails as idt
    import treemodel as tm

M = Qt.KeyboardModifier if QApplication is not None else None
K = Qt.Key if QApplication is not None else None

PER_STEP = bool(os.environ.get('PER_STEP'))
GARAGE = ("garage/\n"
          "│\n"
          "├── shelf A/\n"
          "│   ├── drill\n"
          "│   ├── hammer\n"
          "│   └── saw\n"
          "├── shelf B/\n"
          "│   └── paint\n"
          "└── bike")


def make_image(path, w=64, h=48, color="#3366cc", fmt=None):
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(color))
    assert img.save(path, fmt), path
    return path


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class PanelTestBase(unittest.TestCase):
    TEXT = GARAGE

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.tmp = tempfile.mkdtemp(prefix="nodeon-panel-")
        ini = os.path.join(cls.tmp, "settings.ini")
        cls._orig_settings = app_module.QSettings
        app_module.QSettings = lambda *a: QSettings(ini, QSettings.Format.IniFormat)
        cls._orig_env = os.environ.get(app_module.DEFAULT_COLOURS_ENV)
        os.environ[app_module.DEFAULT_COLOURS_ENV] = os.path.join(cls.tmp, "colours.json")
        cls._orig = {k: getattr(QMessageBox, k) for k in ("question", "warning", "critical",
                                                          "information", "exec")}
        cls.answers = []
        cls.boxes = []

        def record(kind):
            def box(*args, **kwargs):
                cls.boxes.append((kind, " | ".join(a for a in args if isinstance(a, str))))
                if kind == "question":
                    if not cls.answers:
                        raise AssertionError(f"unexpected question: {args}")
                    return cls.answers.pop(0)
                return QMessageBox.StandardButton.Ok
            return staticmethod(box)
        for kind in ("question", "warning", "critical", "information"):
            setattr(QMessageBox, kind, record(kind))

        def unexpected(box):
            raise AssertionError(f"unexpected message box: {box.text()}")
        QMessageBox.exec = unexpected
        # a few pictures to add
        cls.pics = []
        for i, c in enumerate(("#ff0000", "#00aa00", "#0000ff", "#999900", "#00cccc")):
            cls.pics.append(make_image(os.path.join(cls.tmp, f"pic{i} ä.png"), 60 + 10 * i,
                                       40 + 5 * i, c))
        cls.big = make_image(os.path.join(cls.tmp, "big.jpg"), 3000, 2000, "#884422")
        cls.notpic = os.path.join(cls.tmp, "readme.txt")
        with open(cls.notpic, "w") as f:
            f.write("text")

    @classmethod
    def tearDownClass(cls):
        app_module.QSettings = cls._orig_settings
        for k, v in cls._orig.items():
            setattr(QMessageBox, k, v)
        if cls._orig_env is None:
            os.environ.pop(app_module.DEFAULT_COLOURS_ENV, None)
        else:
            os.environ[app_module.DEFAULT_COLOURS_ENV] = cls._orig_env
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.answers.clear()
        self.boxes.clear()
        self.work = tempfile.mkdtemp(prefix="case-", dir=self.tmp)
        self.path = os.path.join(self.work, "garage.txt")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(self.TEXT + "\n")
        self.win = app_module.MainWindow(self.path)
        self.win.show()
        QTest.qWait(20)
        self.ed = self.win.editor
        self.panel = self.win.details_panel
        self.ed.setFocus()

    def tearDown(self):
        if self.win is not None:
            self.ed.document().setModified(False)
            self.win.close()
            self.win.deleteLater()
            QTest.qWait(5)

    # helpers --------------------------------------------------------------
    def lines(self):
        return self.ed.toPlainText().split("\n")

    def goto_name(self, name, nth=0, end=False):
        """Cursor onto the n-th line whose branch name is exactly `name`."""
        self.ed.ensure_parsed()
        found = [i for i, n in enumerate(self.ed._map.nodes)
                 if n is not None and self.ed._map.kinds[i] == tm.KIND_NODE and n.name == name]
        line = found[nth]
        block = self.ed.document().findBlockByNumber(line)
        cur = QTextCursor(block)
        if end:
            cur.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        else:
            col = self.ed._map.name_col.get(id(self.ed._map.nodes[line]), 0)
            cur.setPosition(block.position() + len(block.text()[:col].encode("utf-16-le")) // 2)
        self.ed.setTextCursor(cur)
        self.sync()
        return line

    def sync(self):
        QTest.qWait(1)
        self.ed.ensure_parsed()
        self.win._sync_details_panel()

    def settle(self):
        QTest.qWait(260)
        self.sync()

    def key(self, k, mods=None, widget=None):
        QTest.keyClick(widget or self.ed, k, mods if mods is not None else M.NoModifier)
        QTest.qWait(3)

    def details_of(self, name, nth=0):
        self.ed.ensure_parsed()
        for node in self.ed._model.iter_nodes():
            if node.name == name:
                if nth == 0:
                    return self.ed.details.get(idt.key_of(node))
                nth -= 1
        raise AssertionError(f"no node {name!r}")

    def give(self, name, must="", avoid="", pics=0, nth=0):
        """Put the cursor on `name` and give it features / pictures via the panel."""
        self.goto_name(name, nth)
        if must:
            self.panel.must.body.setPlainText(must)
        if avoid:
            self.panel.avoid.body.setPlainText(avoid)
        if pics:
            self.panel.add_files(self.pics[:pics])
        return self.details_of(name, nth)

    def drop(self, widget, mime):
        pos = QPointF(widget.width() / 2, widget.height() / 2)
        enter = QDragEnterEvent(pos.toPoint(), Qt.DropAction.CopyAction, mime,
                                Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(widget, enter)
        ev = QDropEvent(pos, Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(widget, ev)
        QTest.qWait(5)
        return enter.isAccepted(), ev.isAccepted()

    def url_mime(self, *paths):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
        return mime

    def save(self):
        self.assertTrue(self.win.save())
        QTest.qWait(5)

    def reopen(self):
        self.ed.document().setModified(False)
        self.win.close()
        self.win.deleteLater()
        QTest.qWait(5)
        self.win = app_module.MainWindow(self.path)
        self.win.show()
        QTest.qWait(20)
        self.ed = self.win.editor
        self.panel = self.win.details_panel

    def folder(self):
        return self.path + ".items"

    def db(self):
        with open(os.path.join(self.folder(), "items.json"), encoding="utf-8") as f:
            return json.load(f)


class PanelBasicsTests(PanelTestBase):
    def test_panel_is_on_the_right_and_visible(self):
        self.assertTrue(self.panel.isVisible())
        self.assertIs(self.win.centralWidget(), self.win.main_splitter)
        self.assertIs(self.win.main_splitter.widget(1), self.win.details_area)
        self.assertIs(self.win.details_area.widget(), self.panel)
        x_panel = self.panel.mapTo(self.win, QPoint(0, 0)).x()
        x_editor = self.ed.mapTo(self.win, QPoint(0, 0)).x()
        self.assertGreater(x_panel, x_editor + self.ed.width() // 2)
        self.assertGreaterEqual(self.panel.width(), self.panel.minimumWidth())

    def test_default_width_until_the_user_drags_the_divider(self):
        self.win.setMinimumSize(1200, 700)
        self.win.resize(1200, 700)
        QTest.qWait(30)
        self.assertEqual(self.win.main_splitter.sizes()[1], 360)
        self.win.setMinimumSize(1500, 700)
        self.win.resize(1500, 700)
        QTest.qWait(30)
        self.assertEqual(self.win.main_splitter.sizes()[1], 360, "tree gets the extra width")
        total = sum(self.win.main_splitter.sizes())
        self.win.main_splitter.setSizes([total - 500, 500])
        self.win.main_splitter.splitterMoved.emit(total - 500, 1)       # the user dragged
        self.win.setMinimumSize(1400, 700)
        self.win.resize(1400, 700)
        QTest.qWait(30)
        self.assertEqual(self.win.main_splitter.sizes()[1], 500, "the user's width is kept")
        self.win.setMinimumSize(0, 0)
        self.reopen()                                   # ... and remembered
        self.win.setMinimumSize(1400, 700)
        self.win.resize(1400, 700)
        QTest.qWait(30)
        self.assertEqual(self.win.main_splitter.sizes()[1], 500)
        self.win.setMinimumSize(0, 0)
        app_module.QSettings().remove("details_splitter")

    def test_shows_name_and_path_of_the_row_at_the_cursor(self):
        self.goto_name("hammer")
        self.assertEqual(self.panel.stack.currentIndex(), 1)
        self.assertEqual(self.panel.title.text(), "hammer")
        self.assertEqual(self.panel.crumbs.text(), "garage/ › shelf A/")
        self.assertEqual(self.panel.key, (("garage/", 0), ("shelf A/", 0), ("hammer", 0)))
        self.goto_name("garage/")
        self.assertEqual(self.panel.crumbs.text(), "Top level")

    def test_spacer_line_shows_placeholder(self):
        self.ed.setTextCursor(QTextCursor(self.ed.document().findBlockByNumber(1)))
        self.sync()
        self.assertEqual(self.panel.stack.currentIndex(), 0)
        self.assertIsNone(self.panel.key)
        n, rejected = self.panel.add_files(self.pics[:1])
        self.assertEqual((n, rejected), (0, []))
        self.assertEqual(self.ed.details, {})

    def test_panel_follows_cursor_moves_by_keyboard(self):
        self.goto_name("drill", end=True)
        self.key(K.Key_Down)
        QTest.qWait(60)
        self.assertEqual(self.panel.title.text(), "hammer")
        self.key(K.Key_Down)
        QTest.qWait(60)
        self.assertEqual(self.panel.title.text(), "saw")

    def test_empty_state(self):
        self.goto_name("saw")
        self.assertFalse(self.panel.view.has_image())
        self.assertEqual(self.panel.counter.text(), "0 / 0")
        self.assertFalse(self.panel.b_remove.isEnabled())
        self.assertFalse(self.panel.b_prev.isEnabled())
        self.assertFalse(self.panel.b_next.isEnabled())
        self.assertFalse(self.panel.thumbs.isVisible())
        self.assertIsNone(self.panel.open_viewer())

    def test_toggle_panel_from_view_menu_is_remembered(self):
        self.win.a_details.trigger()
        self.assertFalse(self.panel.isVisible())
        self.reopen()
        self.assertFalse(self.panel.isVisible())
        self.assertFalse(self.win.a_details.isChecked())
        self.win.a_details.trigger()
        self.assertTrue(self.panel.isVisible())
        self.assertIn(self.win.a_details, self.win.menuBar().actions()[3].menu().actions())

    def test_dark_and_light_section_colours(self):
        def bg(widget):
            ss = widget.styleSheet()
            return ss.split("background:")[1].split(";")[0].strip()
        for dark in (False, True):
            self.win._set_dark(dark, save=False)
            g, r = QColor(bg(self.panel.must.header)), QColor(bg(self.panel.avoid.header))
            # green header, red header
            self.assertTrue(90 <= g.hslHue() <= 160, (dark, g.name()))
            self.assertTrue(r.hslHue() >= 330 or r.hslHue() <= 15, (dark, r.name()))
            # light, soft (not glaring) in light mode; dark backgrounds in dark mode
            if not dark:
                self.assertGreater(g.lightness(), 190)
                self.assertGreater(r.lightness(), 190)
                self.assertLess(g.hslSaturation(), 200)
            else:
                self.assertLess(g.lightness(), 90)
                self.assertLess(r.lightness(), 90)
        self.win._set_dark(False, save=False)

    def test_section_titles_and_counts(self):
        self.goto_name("drill")
        self.assertIn("Must-have features", self.panel.must.header.text())
        self.assertIn("Features to avoid", self.panel.avoid.header.text())
        self.panel.must.body.setPlainText("18 V\n\n2 speeds\n  \nmetal chuck")
        self.assertTrue(self.panel.must.header.text().endswith("·  3"))
        self.panel.avoid.body.setPlainText("corded")
        self.assertTrue(self.panel.avoid.header.text().endswith("·  1"))


class PictureTests(PanelTestBase):
    def test_add_files_shows_first_added_and_counter(self):
        self.goto_name("drill")
        n, rejected = self.panel.add_files(self.pics[:3])
        self.assertEqual((n, rejected), (3, []))
        self.assertEqual(self.panel.counter.text(), "1 / 3")
        self.assertTrue(self.panel.view.has_image())
        self.assertEqual(self.panel.view.image_size().width(), 60)
        self.assertEqual(self.panel.thumbs.count(), 3)
        self.assertTrue(self.panel.thumbs.isVisible())
        names = [i["name"] for i in self.details_of("drill").images]
        self.assertEqual(names, ["pic0 ä.png", "pic1 ä.png", "pic2 ä.png"])
        self.assertTrue(self.ed.document().isModified(), "unsaved change is shown")
        self.assertTrue(self.win.isWindowModified())
        # adding more shows the first of the new ones
        self.panel.add_files(self.pics[3:5])
        self.assertEqual(self.panel.counter.text(), "4 / 5")

    def test_non_pictures_are_rejected_with_a_message(self):
        self.goto_name("drill")
        n, rejected = self.panel.add_files([self.notpic, self.pics[0], self.work,
                                            os.path.join(self.work, "missing.png")])
        self.assertEqual(n, 1)
        self.assertEqual(len(rejected), 3)
        self.assertIn("readme.txt", rejected)
        self.assertIn("not a picture", self.win.statusBar().currentMessage())
        n, rejected = self.panel.add_files([self.notpic])
        self.assertEqual(n, 0)
        self.assertEqual(len(self.details_of("drill").images), 1)

    def test_drag_and_drop_files_onto_picture_strip_and_panel(self):
        self.goto_name("hammer")
        entered, dropped = self.drop(self.panel.view.viewport(), self.url_mime(self.pics[0]))
        self.assertTrue(entered and dropped)
        self.assertEqual(len(self.details_of("hammer").images), 1)
        self.drop(self.panel.view.viewport(), self.url_mime(self.pics[1], self.pics[2]))
        self.assertEqual(len(self.details_of("hammer").images), 3)
        self.drop(self.panel.thumbs.viewport(), self.url_mime(self.pics[3]))
        self.assertEqual(len(self.details_of("hammer").images), 4)
        self.drop(self.panel, self.url_mime(self.pics[4]))
        self.assertEqual(len(self.details_of("hammer").images), 5)
        entered, dropped = self.drop(self.panel.view.viewport(), QMimeData())
        self.assertFalse(dropped)
        self.assertEqual(len(self.details_of("hammer").images), 5)

    def test_drop_image_data_from_a_browser(self):
        self.goto_name("saw")
        mime = QMimeData()
        img = QImage(30, 20, QImage.Format.Format_ARGB32)
        img.fill(QColor("#123456"))
        mime.setImageData(img)
        self.drop(self.panel.view.viewport(), mime)
        imgs = self.details_of("saw").images
        self.assertEqual(len(imgs), 1)
        self.assertEqual(imgs[0]["name"], "dropped image.png")
        self.assertEqual(self.panel.view.image_size().width(), 30)

    def test_paste_picture_from_clipboard(self):
        self.goto_name("saw")
        QApplication.clipboard().clear()
        self.panel.paste_image()
        self.assertIsNone(self.details_of("saw"))
        self.assertIn("no picture", self.win.statusBar().currentMessage())
        img = QImage(25, 25, QImage.Format.Format_RGB32)
        img.fill(QColor("#ff00ff"))
        QApplication.clipboard().setImage(img)
        self.panel.view.setFocus()
        QTest.keyClick(self.panel.view, K.Key_V, M.ControlModifier)
        QTest.qWait(5)
        self.assertEqual(len(self.details_of("saw").images), 1)
        self.assertEqual(self.ed.toPlainText().count("saw"), 1, "tree text not pasted into")

    def test_slideshow_previous_next(self):
        self.give("drill", pics=4)
        p = self.panel
        p.select_image(0)
        self.assertFalse(p.b_prev.isEnabled())
        widths = []
        for _ in range(5):                         # one more than available: stays at the end
            widths.append(p.view.image_size().width())
            p.b_next.click()
        self.assertEqual(widths, [60, 70, 80, 90, 90])
        self.assertEqual(p.counter.text(), "4 / 4")
        self.assertFalse(p.b_next.isEnabled())
        p.b_prev.click()
        self.assertEqual(p.counter.text(), "3 / 4")
        # keyboard in the picture
        p.view.setFocus()
        self.key(K.Key_Left, widget=p.view)
        self.assertEqual(p.counter.text(), "2 / 4")
        self.key(K.Key_Right, widget=p.view)
        self.key(K.Key_Right, widget=p.view)
        self.assertEqual(p.counter.text(), "4 / 4")
        # clicking a thumbnail
        p.thumbs.setCurrentRow(0)
        self.assertEqual(p.counter.text(), "1 / 4")
        self.assertEqual(p.view.image_size().width(), 60)

    def test_zoom_in_out_fit_and_limits(self):
        self.goto_name("bike")
        self.panel.add_files([self.big])
        v = self.panel.view
        self.assertTrue(v.is_fit())
        fit = v.scale_factor()
        self.assertLess(fit, 1.0, "big picture fitted into the panel")
        self.panel.b_zoom_in.click()
        self.assertAlmostEqual(v.scale_factor(), fit * 1.25, places=6)
        self.assertFalse(v.is_fit())
        self.assertEqual(self.panel.zoom_label.text(), f"{v.zoom_percent()} %")
        self.panel.b_zoom_out.click()
        self.panel.b_zoom_out.click()
        self.assertAlmostEqual(v.scale_factor(), fit / 1.25, places=6)
        self.panel.b_fit.click()
        self.assertAlmostEqual(v.scale_factor(), fit, places=6)
        for _ in range(80):
            v.zoom_in()
        self.assertAlmostEqual(v.scale_factor(), v.MAX_SCALE)
        for _ in range(200):
            v.zoom_out()
        self.assertAlmostEqual(v.scale_factor(), v.MIN_SCALE)
        v.setFocus()
        self.key(K.Key_0, widget=v)
        self.assertTrue(v.is_fit())
        self.key(K.Key_1, widget=v)
        self.assertAlmostEqual(v.scale_factor(), 1.0)
        self.key(K.Key_Plus, widget=v)
        self.assertAlmostEqual(v.scale_factor(), 1.25)
        self.key(K.Key_Minus, widget=v)
        self.assertAlmostEqual(v.scale_factor(), 1.0)

    def test_mouse_wheel_zooms_picture(self):
        self.goto_name("bike")
        self.panel.add_files([self.big])
        v = self.panel.view
        before = v.scale_factor()
        pos = QPointF(v.viewport().width() / 2, v.viewport().height() / 2)
        ev = QWheelEvent(pos, v.viewport().mapToGlobal(pos), QPoint(0, 0), QPoint(0, 120),
                         Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                         Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(v.viewport(), ev)
        self.assertAlmostEqual(v.scale_factor(), before * 1.15, places=5)

    def test_small_picture_is_not_enlarged_when_fitted(self):
        self.goto_name("bike")
        self.panel.add_files(self.pics[:1])
        self.assertAlmostEqual(self.panel.view.scale_factor(), 1.0)

    def test_remove_picture_asks_and_can_be_cancelled(self):
        self.give("drill", pics=3)
        self.panel.select_image(1)
        self.answers.append(QMessageBox.StandardButton.No)
        self.panel.b_remove.click()
        self.assertEqual(len(self.details_of("drill").images), 3)
        self.answers.append(QMessageBox.StandardButton.Yes)
        self.panel.b_remove.click()
        names = [i["name"] for i in self.details_of("drill").images]
        self.assertEqual(names, ["pic0 ä.png", "pic2 ä.png"])
        self.assertEqual(self.panel.counter.text(), "2 / 2")
        self.assertIn("pic1", self.boxes[-1][1])
        # Delete key in the picture
        self.panel.view.setFocus()
        self.answers.append(QMessageBox.StandardButton.Yes)
        self.key(K.Key_Delete, widget=self.panel.view)
        self.assertEqual(len(self.details_of("drill").images), 1)
        self.assertEqual(self.ed.toPlainText().count("drill"), 1, "Delete did not edit the tree")
        # removing the last picture of an item without features forgets the item
        self.panel.delete_image(confirm=False)
        self.assertIsNone(self.details_of("drill"))
        self.assertEqual(self.panel.counter.text(), "0 / 0")

    def test_reorder_with_buttons(self):
        self.give("drill", pics=3)
        p = self.panel
        p.select_image(0)
        self.assertFalse(p.b_move_left.isEnabled())
        p.b_move_right.click()
        names = [i["name"][:4] for i in self.details_of("drill").images]
        self.assertEqual(names, ["pic1", "pic0", "pic2"])
        self.assertEqual(p.counter.text(), "2 / 3", "the moved picture stays shown")
        p.b_move_right.click()
        self.assertFalse(p.b_move_right.isEnabled())
        self.assertEqual([i["name"][:4] for i in self.details_of("drill").images],
                         ["pic1", "pic2", "pic0"])
        p.b_move_left.click()
        p.b_move_left.click()
        self.assertEqual([i["name"][:4] for i in self.details_of("drill").images],
                         ["pic0", "pic1", "pic2"])
        self.assertFalse(p.move_image(-1, index=0))
        self.assertFalse(p.move_image(5))

    def test_reorder_by_dragging_thumbnails(self):
        self.give("drill", pics=3)
        p = self.panel
        files = [i["file"] for i in self.details_of("drill").images]
        p.select_image(0)
        # what the strip reports after an internal drag & drop
        p.thumbs.orderChanged.emit([files[2], files[0], files[1]])
        self.assertEqual(self.details_of("drill").files(), [files[2], files[0], files[1]])
        self.assertEqual(p.counter.text(), "2 / 3", "the shown picture is still shown")
        self.assertEqual([p.thumbs.item(i).data(Qt.ItemDataRole.UserRole) for i in range(3)],
                         [files[2], files[0], files[1]])
        # a broken order report never loses pictures
        p.thumbs.orderChanged.emit([files[0]])
        self.assertEqual(len(self.details_of("drill").images), 3)
        self.assertEqual(p.thumbs.count(), 3)

    def test_real_internal_move_in_the_strip(self):
        self.give("drill", pics=3)
        p = self.panel
        files = self.details_of("drill").files()
        model = p.thumbs.model()
        from PySide6.QtCore import QModelIndex
        moved = model.moveRow(QModelIndex(), 2, QModelIndex(), 0)
        if moved:
            p.thumbs.orderChanged.emit(p.thumbs.files())
            self.assertEqual(self.details_of("drill").files(), [files[2], files[0], files[1]])

    def test_open_large_viewer_navigation_syncs_panel(self):
        self.give("drill", pics=3)
        self.panel.select_image(1)
        dlg = self.panel.open_viewer()
        QTest.qWait(10)
        self.assertTrue(dlg.isVisible())
        self.assertTrue(dlg.isModal())
        self.assertEqual(dlg.counter.text(), "2 / 3")
        self.assertEqual(dlg.view.image_size().width(), 70)
        dlg.b_next.click()
        self.assertEqual(dlg.counter.text(), "3 / 3")
        self.assertEqual(self.panel.counter.text(), "3 / 3", "panel follows the viewer")
        self.assertFalse(dlg.b_next.isEnabled())
        dlg.view.setFocus()
        self.key(K.Key_Left, widget=dlg.view)
        self.assertEqual(dlg.counter.text(), "2 / 3")
        dlg.b_in.click()
        self.assertFalse(dlg.view.is_fit())
        dlg.b_close.click()
        QTest.qWait(10)
        self.assertIsNone(self.panel._viewer)

    def test_double_click_opens_viewer(self):
        self.give("drill", pics=2)
        v = self.panel.view.viewport()
        QTest.mouseDClick(v, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                          QPoint(v.width() // 2, v.height() // 2))
        QTest.qWait(10)
        self.assertIsNotNone(self.panel._viewer)
        self.panel._viewer.accept()
        QTest.qWait(5)

    def test_missing_picture_file_shows_message_not_crash(self):
        self.give("drill", pics=2)
        self.save()
        f = self.details_of("drill").images[0]["file"]
        os.remove(os.path.join(self.folder(), "images", f))
        self.reopen()
        self.goto_name("drill")
        self.assertEqual(self.panel.counter.text(), "1 / 2")
        self.assertFalse(self.panel.view.has_image())
        self.assertIn("missing", self.panel.view.message())
        self.assertIn("missing", self.panel.thumbs.item(0).toolTip())
        self.panel.next_image()
        self.assertTrue(self.panel.view.has_image())
        self.panel.delete_image(0, confirm=False)
        self.assertEqual(len(self.details_of("drill").images), 1)

    def test_corrupt_picture_file_shows_message(self):
        bad = os.path.join(self.work, "bad.png")
        with open(bad, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
        self.goto_name("drill")
        n, rejected = self.panel.add_files([bad])
        if n:                                          # header looked fine: shown as error
            self.assertFalse(self.panel.view.has_image())
            self.assertIn("cannot be shown", self.panel.view.message())
        else:
            self.assertEqual(rejected, ["bad.png"])


class FeatureTests(PanelTestBase):
    def test_features_are_stored_per_item(self):
        self.goto_name("drill")
        self.panel.must.body.setPlainText("18 V\n2 speeds")
        self.panel.avoid.body.setPlainText("corded")
        self.goto_name("hammer")
        self.assertEqual(self.panel.must.text(), "")
        self.assertEqual(self.panel.avoid.text(), "")
        self.panel.must.body.setPlainText("fibreglass handle")
        self.goto_name("drill")
        self.assertEqual(self.panel.must.text(), "18 V\n2 speeds")
        self.assertEqual(self.panel.avoid.text(), "corded")
        self.assertEqual(self.details_of("hammer").must, "fibreglass handle")
        self.assertTrue(self.ed.document().isModified())

    def test_typing_in_feature_box(self):
        self.goto_name("saw")
        body = self.panel.must.body
        body.setFocus()
        QTest.keyClicks(body, "sharp")
        self.key(K.Key_Return, widget=body)
        QTest.keyClicks(body, "folding")
        self.settle()                          # editor re-reads: the text box is not reset
        QTest.keyClicks(body, "!")
        self.assertEqual(self.details_of("saw").must, "sharp\nfolding!")
        self.assertEqual(body.textCursor().position(), len("sharp\nfolding!"))
        # Undo inside the text box undoes the text box, not the tree
        tree_before = self.ed.toPlainText()
        self.key(K.Key_Z, M.ControlModifier, widget=body)
        self.assertEqual(self.ed.toPlainText(), tree_before)
        self.assertNotEqual(self.details_of("saw").must, "sharp\nfolding!")

    def test_tree_shortcuts_do_not_fire_while_typing_in_the_panel(self):
        self.goto_name("saw")
        before = self.ed.toPlainText()
        body = self.panel.avoid.body
        body.setFocus()
        for k, mods in ((K.Key_D, M.ControlModifier), (K.Key_Q, M.ControlModifier),
                        (K.Key_G, M.AltModifier), (K.Key_Return, M.ControlModifier),
                        (K.Key_Up, M.AltModifier | M.ShiftModifier),
                        (K.Key_Delete, M.ControlModifier | M.ShiftModifier),
                        (K.Key_1, M.AltModifier), (K.Key_E, M.ControlModifier)):
            self.key(k, mods, widget=body)
        self.settle()
        self.assertEqual(self.ed.toPlainText(), before)
        self.assertEqual(self.ed.export_marks(), [])

    def test_command_keys_type_nothing_but_altgr_characters_do(self):
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        self.goto_name("saw")
        body = self.panel.must.body
        body.setFocus()
        QTest.keyClicks(body, "a")
        for k, mods in ((K.Key_G, M.AltModifier), (K.Key_O, M.AltModifier),
                        (K.Key_D, M.ControlModifier), (K.Key_E, M.ControlModifier)):
            QApplication.sendEvent(body, QKeyEvent(QEvent.Type.KeyPress, k, mods,
                                                   chr(k).lower()))
        self.assertEqual(body.toPlainText(), "a", "command keys type nothing")
        # AltGr on Windows (Ctrl+Alt) with a character: typed (e.g. Swiss "@" = AltGr+2)
        ev = QKeyEvent(QEvent.Type.KeyPress, K.Key_2, M.ControlModifier | M.AltModifier, "@")
        QApplication.sendEvent(body, ev)
        self.assertEqual(body.toPlainText(), "a@")
        # editing shortcuts still work in the box
        self.key(K.Key_A, M.ControlModifier, widget=body)
        self.key(K.Key_C, M.ControlModifier, widget=body)
        self.assertEqual(QApplication.clipboard().text(), "a@")
        self.key(K.Key_End, widget=body)
        self.key(K.Key_V, M.ControlModifier, widget=body)
        self.assertEqual(body.toPlainText(), "a@a@")
        self.key(K.Key_Left, M.ControlModifier | M.ShiftModifier, widget=body)
        self.assertTrue(body.textCursor().hasSelection())
        self.assertEqual(self.details_of("saw").must, "a@a@")

    def test_save_shortcut_still_works_from_the_panel(self):
        self.goto_name("saw")
        body = self.panel.must.body
        body.setFocus()
        QTest.keyClicks(body, "sharp")
        self.key(K.Key_S, M.ControlModifier, widget=body)
        self.assertFalse(self.ed.document().isModified())
        self.assertEqual(self.db()["items"][0]["must"], "sharp")

    def test_clearing_features_forgets_the_item(self):
        self.goto_name("saw")
        self.panel.must.body.setPlainText("x")
        self.assertIsNotNone(self.details_of("saw"))
        self.panel.must.body.setPlainText("")
        self.assertIsNone(self.details_of("saw"))

    def test_long_feature_lists_scroll(self):
        self.goto_name("saw")
        self.panel.must.body.setPlainText("\n".join(f"feature {i}" for i in range(300)))
        QTest.qWait(10)
        sb = self.panel.must.body.verticalScrollBar()
        self.assertGreater(sb.maximum(), 0)
        self.assertTrue(self.panel.must.header.text().endswith("·  300"))


class SaveLoadTests(PanelTestBase):
    def test_save_and_reopen_restores_everything(self):
        self.give("drill", "18 V\n2 speeds", "corded", pics=3)
        self.give("paint", avoid="oil based")
        self.panel.select_image(0)
        self.save()
        self.assertFalse(self.ed.document().isModified())
        data = self.db()
        self.assertEqual(data["app"], "Nodeon")
        self.assertEqual(data["file"], "garage.txt")
        self.assertEqual([it["path"][-1][0] for it in data["items"]], ["drill", "paint"])
        files = os.listdir(os.path.join(self.folder(), "images"))
        self.assertEqual(len(files), 3)
        with open(self.path, encoding="utf-8") as fh:
            saved = fh.read()
        self.assertEqual(saved, GARAGE + "\n",
                         "the .txt stays pure text")
        self.reopen()
        self.goto_name("drill")
        self.assertEqual(self.panel.counter.text(), "1 / 3")
        self.assertEqual(self.panel.must.text(), "18 V\n2 speeds")
        self.assertEqual(self.panel.avoid.text(), "corded")
        self.assertTrue(self.panel.view.has_image())
        self.goto_name("paint")
        self.assertEqual(self.panel.avoid.text(), "oil based")
        self.assertFalse(self.ed.document().isModified())

    def test_discard_leaves_folder_untouched(self):
        self.give("drill", "18 V", pics=1)
        self.save()
        before = sorted(os.listdir(os.path.join(self.folder(), "images")))
        db_before = self.db()
        self.give("hammer", "steel", pics=2)
        self.give("drill", pics=1)
        self.reopen()                                       # = close and "Discard"
        self.assertEqual(sorted(os.listdir(os.path.join(self.folder(), "images"))), before)
        self.assertEqual(self.db(), db_before)
        self.goto_name("hammer")
        self.assertEqual(self.panel.counter.text(), "0 / 0")

    def test_close_asks_to_save_after_picture_change(self):
        self.give("drill", pics=1)
        self.assertTrue(self.ed.document().isModified())
        self.answers.append(QMessageBox.StandardButton.Save)
        self.win.close()
        QTest.qWait(10)
        self.assertEqual(len(self.db()["items"]), 1)
        self.win.deleteLater()
        self.win = None

    def test_removed_pictures_are_deleted_on_save(self):
        self.give("drill", pics=3)
        self.save()
        imgs = os.path.join(self.folder(), "images")
        self.assertEqual(len(os.listdir(imgs)), 3)
        self.panel.delete_image(1, confirm=False)
        self.assertEqual(len(os.listdir(imgs)), 3, "nothing deleted before saving")
        self.save()
        self.assertEqual(sorted(os.listdir(imgs)), sorted(self.details_of("drill").files()))

    def test_nothing_written_for_a_tree_without_details(self):
        self.save()
        self.assertFalse(os.path.exists(self.folder()))
        self.give("drill", "x")
        self.save()
        self.assertTrue(os.path.isfile(os.path.join(self.folder(), "items.json")))
        self.give("drill")
        self.panel.must.body.setPlainText("")
        self.save()
        self.assertFalse(os.path.exists(self.folder()))

    def test_untitled_tree_then_save_as(self):
        self.win.new_file(ask=False)
        self.sync()
        self.ed.moveCursor(QTextCursor.MoveOperation.Start)
        self.sync()
        self.assertEqual(self.panel.title.text(), "new-project/")
        self.panel.add_files(self.pics[:2])
        self.panel.must.body.setPlainText("root feature")
        staged = [self.win.item_store.abs_path(f) for f in self.ed.details[(("new-project/", 0),)].files()]
        target = os.path.join(self.work, "new tree.txt")
        orig = app_module.QFileDialog.getSaveFileName
        app_module.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (target, ""))
        try:
            self.assertTrue(self.win.save())
        finally:
            app_module.QFileDialog.getSaveFileName = orig
        for p in staged:
            self.assertFalse(os.path.exists(p), "staged copy moved in")
        self.assertEqual(len(os.listdir(target + ".items/images")), 2)
        self.path = target
        self.reopen()
        self.ed.moveCursor(QTextCursor.MoveOperation.Start)
        self.sync()
        self.assertEqual(self.panel.counter.text(), "1 / 2")
        self.assertEqual(self.panel.must.text(), "root feature")

    def test_save_as_copies_pictures_to_the_new_place(self):
        self.give("drill", "18 V", pics=2)
        self.save()
        target = os.path.join(self.work, "copy", "garage copy.txt")
        os.makedirs(os.path.dirname(target))
        orig = app_module.QFileDialog.getSaveFileName
        app_module.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (target, ""))
        try:
            self.assertTrue(self.win.save_as())
        finally:
            app_module.QFileDialog.getSaveFileName = orig
        self.assertEqual(len(os.listdir(target + ".items/images")), 2)
        self.assertEqual(len(os.listdir(self.folder() + "/images")), 2, "original kept")
        self.panel.delete_image(0, confirm=False)
        self.save()                                     # saves to the copy now
        self.assertEqual(len(os.listdir(target + ".items/images")), 1)
        self.assertEqual(len(os.listdir(self.folder() + "/images")), 2)

    def test_open_other_file_switches_details(self):
        self.give("drill", "A", pics=1)
        self.save()
        other = os.path.join(self.work, "other.txt")
        with open(other, "w", encoding="utf-8") as f:
            f.write("other/\n└── drill\n")
        self.ed.document().setModified(False)
        self.assertTrue(self.win.load_file(other))
        self.goto_name("drill")
        self.assertEqual(self.panel.must.text(), "")
        self.assertEqual(self.panel.counter.text(), "0 / 0")
        self.assertTrue(self.win.load_file(self.path))
        self.goto_name("drill")
        self.assertEqual(self.panel.must.text(), "A")

    def test_corrupt_database_warns_backs_up_and_keeps_pictures(self):
        self.give("drill", "x", pics=1)
        self.save()
        f = self.details_of("drill").files()[0]
        with open(os.path.join(self.folder(), "items.json"), "w") as fh:
            fh.write("{oops")
        self.reopen()
        self.assertTrue(any(k == "warning" and "could not be read" in t for k, t in self.boxes))
        self.assertEqual(self.ed.toPlainText(), GARAGE, "the tree itself is fine")
        self.give("hammer", "y")
        self.save()
        names = os.listdir(self.folder())
        self.assertTrue(any(n.startswith("items.json.unreadable-") for n in names))
        self.assertTrue(os.path.isfile(os.path.join(self.folder(), "images", f)))
        self.assertEqual([it["path"][-1][0] for it in self.db()["items"]], ["hammer"])

    def test_read_only_folder_reports_error(self):
        if os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0):
            self.skipTest("permissions are not enforced for this user")
        self.give("drill", "x", pics=1)
        os.chmod(self.work, 0o555)
        try:
            self.win._save_details(self.path)
        finally:
            os.chmod(self.work, 0o755)
        self.assertTrue(any(k == "warning" for k, _ in self.boxes))

    def test_save_errors_are_reported_and_keep_unsaved_state(self):
        self.give("drill", "x", pics=1)
        orig = idt.ItemStore.save

        def fail(*a, **k):
            raise OSError("disk full")
        idt.ItemStore.save = fail
        try:
            self.assertTrue(self.win.save())
        finally:
            idt.ItemStore.save = orig
        self.assertTrue(any(k == "warning" and "disk full" in t for k, t in self.boxes))
        self.assertTrue(self.ed.document().isModified(), "still marked unsaved")
        self.save()
        self.assertEqual(len(self.db()["items"]), 1)

    def test_crlf_and_bom_files_keep_details(self):
        with open(self.path, "wb") as f:
            f.write(("﻿" + GARAGE.replace("\n", "\r\n") + "\r\n").encode("utf-8"))
        self.reopen()
        self.give("saw", "sharp", pics=1)
        self.save()
        self.reopen()
        self.goto_name("saw")
        self.assertEqual(self.panel.must.text(), "sharp")
        with open(self.path, "rb") as fh:
            self.assertEqual(fh.read().count(b"\r\n"), GARAGE.count("\n") + 1)


class FollowTheRowTests(PanelTestBase):
    """Pictures and features always stay with their row."""

    def setUp(self):
        super().setUp()
        self.give("drill", "drill-must", pics=1)
        self.give("hammer", "hammer-must", pics=2)
        self.give("saw", "saw-must")
        self.give("shelf A/", "shelfA-must")
        self.give("paint", "paint-must", pics=1)
        self.give("bike", "bike-must")
        self.snapshot = {n: self.details_of(n).copy()
                         for n in ("drill", "hammer", "saw", "shelf A/", "paint", "bike")}

    def assert_intact(self, renamed=None):
        renamed = renamed or {}
        for name, d in self.snapshot.items():
            now = self.details_of(renamed.get(name, name))
            self.assertEqual(now, d, f"{name}: {now} != {d}\n{self.ed.toPlainText()}")
        self.assertEqual(len(self.ed.details), len(self.snapshot), self.ed.details.keys())

    def test_move_up_and_down(self):
        self.goto_name("saw")
        self.win.a_up.trigger()
        self.win.a_up.trigger()
        self.assertEqual(self.lines()[3], "│   ├── saw")
        self.assert_intact()
        self.goto_name("saw")
        self.assertEqual(self.panel.must.text(), "saw-must")
        self.goto_name("shelf B/")
        self.win.a_up.trigger()
        self.assert_intact()
        self.win.a_down.trigger()
        self.win.a_down.trigger()
        self.assert_intact()

    def test_indent_and_outdent_change_the_level(self):
        self.goto_name("hammer")
        self.win.a_right.trigger()                 # into drill
        self.assertIn(("drill", 0), self.details_key_parts("hammer"))
        self.assert_intact()
        self.goto_name("hammer")
        self.win.a_left.trigger()
        self.win.a_left.trigger()                  # to the shelf level
        self.assert_intact()
        self.goto_name("hammer")
        self.assertEqual(self.panel.counter.text(), "1 / 2")
        self.assertEqual(self.panel.must.text(), "hammer-must")

    def details_key_parts(self, name):
        for node in self.ed._model.iter_nodes():
            if node.name == name:
                return idt.key_of(node)

    def test_tab_and_shift_tab_keys(self):
        self.goto_name("saw")
        self.key(K.Key_Tab)
        self.settle()
        self.assert_intact()
        self.goto_name("saw")
        self.key(K.Key_Backtab, M.ShiftModifier)
        self.settle()
        self.assert_intact()

    def test_parent_moves_carry_children(self):
        self.goto_name("shelf B/")
        self.win.a_up.trigger()                    # shelf B with paint above shelf A
        self.assert_intact()
        self.goto_name("shelf A/")
        self.win.a_right.trigger()                 # shelf A into shelf B
        self.assert_intact()
        self.goto_name("drill")
        self.assertEqual(self.panel.crumbs.text(), "garage/ › shelf B/ › shelf A/")
        self.assertEqual(self.panel.must.text(), "drill-must")

    def test_rename_by_typing(self):
        self.goto_name("drill", end=True)
        QTest.keyClicks(self.ed, " XL")
        self.settle()
        self.assert_intact({"drill": "drill XL"})
        self.assertEqual(self.panel.title.text(), "drill XL")
        self.assertEqual(self.panel.must.text(), "drill-must")
        # rename a parent: every child keeps its details
        self.goto_name("shelf A/")
        cur = self.ed.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 5)
        self.ed.setTextCursor(cur)
        QTest.keyClicks(self.ed, "Rack")
        self.settle()
        self.assert_intact({"drill": "drill XL", "shelf A/": "Rack A/"})

    def test_rename_by_select_all_and_typing_new_name(self):
        line = self.goto_name("bike")
        block = self.ed.document().findBlockByNumber(line)
        cur = QTextCursor(block)
        cur.setPosition(block.position() + 4)
        cur.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        self.ed.setTextCursor(cur)
        QTest.keyClicks(self.ed, "Bicycle")
        self.settle()
        self.assert_intact({"bike": "Bicycle"})

    def test_rename_with_edit_dialog(self):
        self.goto_name("paint")
        node = self.ed.current_item()
        self.ed.run_op(lambda n: (setattr(n, "name", "paint (white)") or n, "end"))
        self.settle()
        self.assert_intact({"paint": "paint (white)"})

    def test_new_rows_above_and_below(self):
        self.goto_name("drill", end=True)
        self.key(K.Key_Return)                      # new item below drill
        QTest.keyClicks(self.ed, "screwdriver")
        self.settle()
        self.goto_name("garage/", end=True)
        self.win.a_add_child.trigger()
        QTest.keyClicks(self.ed, "new first")
        self.settle()
        self.goto_name("shelf A/")
        self.win.a_add_sibling.trigger()
        self.win.a_spacer.trigger()
        self.settle()
        self.assert_intact()
        self.goto_name("screwdriver")
        self.assertEqual(self.panel.counter.text(), "0 / 0")
        self.assertEqual(self.panel.must.text(), "")

    def test_shift_enter_and_plain_newlines(self):
        self.goto_name("drill", end=True)
        self.key(K.Key_Return, M.ShiftModifier)
        self.settle()
        self.key(K.Key_Backspace)
        self.settle()
        self.assert_intact()

    def test_delete_branch_and_undo(self):
        self.goto_name("shelf A/")
        self.win.a_delete.trigger()
        self.settle()
        self.assertNotIn("drill", self.ed.toPlainText())
        self.goto_name("paint")
        self.assertEqual(self.panel.must.text(), "paint-must")
        self.ed.undo()
        self.settle()
        self.assert_intact()
        self.ed.redo()
        self.settle()
        self.ed.undo()
        self.settle()
        self.assert_intact()

    def test_deleted_rows_are_not_saved_but_undo_after_save_brings_them_back(self):
        self.goto_name("hammer")
        self.win.a_delete.trigger()
        self.settle()
        self.save()
        names = [it["path"][-1][0] for it in self.db()["items"]]
        self.assertNotIn("hammer", names)
        hammer_files = self.snapshot["hammer"].files()
        for f in hammer_files:                       # kept: Undo can still bring them back
            self.assertIsNotNone(self.win.item_store.abs_path(f))
        self.ed.undo()
        self.settle()
        self.assert_intact()
        self.goto_name("hammer")
        self.assertTrue(self.panel.view.has_image())
        self.save()
        self.assertIn("hammer", [it["path"][-1][0] for it in self.db()["items"]])

    def test_delete_line_keeps_children_details(self):
        self.goto_name("shelf A/")
        self.win.a_delete_line.trigger()
        self.settle()
        for n in ("drill", "hammer", "saw"):
            self.assertEqual(self.details_of(n), self.snapshot[n], n)
        self.ed.undo()
        self.settle()
        self.assert_intact()

    def test_duplicate_does_not_steal_details(self):
        self.goto_name("hammer")
        self.win.a_duplicate.trigger()
        self.settle()
        self.assertEqual(self.details_of("hammer", 0), self.snapshot["hammer"])
        self.assertIsNone(self.details_of("hammer", 1))
        self.assert_intact()

    def test_undo_redo_of_moves(self):
        self.goto_name("hammer")
        self.win.a_down.trigger()
        self.win.a_right.trigger()
        self.goto_name("bike")
        self.win.a_up.trigger()
        self.win.a_up.trigger()
        self.assert_intact()
        for _ in range(4):
            self.ed.undo()
            self.settle()
            self.assert_intact()
        self.assertEqual(self.ed.toPlainText(), GARAGE)
        for _ in range(4):
            self.ed.redo()
            self.settle()
            self.assert_intact()

    def test_format_document_and_explanations(self):
        self.goto_name("drill")
        self.ed.run_op(lambda n: (setattr(n, "comment", ["cordless"]) or n, "end"))
        self.win.a_format.trigger()
        self.win.a_expl_right.trigger()
        self.settle()
        self.assert_intact()
        # cursor on the explanation part still shows the item
        line = self.goto_name("drill", end=True)
        self.assertEqual(self.panel.title.text(), "drill")

    def test_multi_line_explanation_lines_show_their_item(self):
        self.goto_name("drill")
        self.ed.run_op(lambda n: (setattr(n, "comment", ["line one", "line two"]) or n, "end"))
        self.settle()
        line = self.goto_name("drill")
        self.ed.setTextCursor(QTextCursor(self.ed.document().findBlockByNumber(line + 1)))
        self.sync()
        self.assertEqual(self.panel.title.text(), "drill")
        self.assertEqual(self.panel.must.text(), "drill-must")

    def test_paste_lines(self):
        self.goto_name("saw", end=True)
        self.key(K.Key_Return)
        QApplication.clipboard().setText("glue\nnails\nscrews")
        self.ed.paste()
        self.settle()
        self.assertIn("screws", self.ed.toPlainText())
        self.assert_intact()

    def test_folding_does_not_affect_details(self):
        self.win.a_collapse_all.trigger()
        self.win.a_expand_all.trigger()
        self.settle()
        self.assert_intact()

    def test_follow_survives_save_and_reopen_after_moves(self):
        self.goto_name("hammer")
        self.win.a_up.trigger()
        self.win.a_left.trigger()
        self.goto_name("bike", end=True)
        QTest.keyClicks(self.ed, "2")
        self.settle()
        self.save()
        self.reopen()
        self.assert_intact({"bike": "bike2"})


class StressTests(PanelTestBase):
    """Random editing with many items; nothing may ever get lost or swapped."""

    def test_random_structural_editing_keeps_every_item_with_its_row(self):
        names = [f"item{i:02d}" for i in range(24)]
        text = "store/\n" + "\n".join(
            ("├── " if i < len(names) - 1 else "└── ") + n for i, n in enumerate(names))
        self.ed.set_document_text(text)
        self.win.item_store.reset()
        self.sync()
        rng = random.Random(1234)
        for n in names[::2]:
            self.give(n, must=f"token:{n}", pics=1 if rng.random() < 0.3 else 0)
        original = {n: self.details_of(n).copy() for n in names[::2]}
        ops = [self.win.a_up, self.win.a_down, self.win.a_left, self.win.a_right,
               self.win.a_add_sibling, self.win.a_add_child, self.win.a_spacer]
        done = 0
        for step in range(250):
            live = [n.name for n in self.ed._model.iter_nodes() if n.name.startswith("item")]
            self.goto_name(rng.choice(live))
            r = rng.random()
            if r < 0.08:
                self.ed.undo()
            elif r < 0.12:
                self.ed.redo()
            elif r < 0.20:
                self.goto_name(self.ed.current_item().name, end=True)
                QTest.keyClicks(self.ed, "x")
            else:
                rng.choice(ops).trigger()
                done += 1
            self.settle() if step % 25 == 0 else self.sync()
            self.ed.ensure_parsed()
            # invariant: every details entry of a live row belongs to that row
            for node in self.ed._model.iter_nodes():
                d = self.ed.details.get(idt.key_of(node))
                if d is not None:
                    token = d.must.split(":", 1)[1]
                    self.assertTrue(node.name.startswith(token),
                                    f"step {step}: {node.name} got {d}\n{self.ed.toPlainText()}")
        # Every original item still has its details (possibly renamed with x's)
        self.settle()
        for n, d in original.items():
            node = next(x for x in self.ed._model.iter_nodes() if x.name.rstrip("x") == n)
            self.assertEqual(self.ed.details.get(idt.key_of(node)), d, n)
        # Save, reopen: identical
        before = {k: v.copy() for k, v in self.ed.export_details()}
        self.save()
        self.reopen()
        self.assertEqual({k: v for k, v in self.ed.export_details()}, before)
        self.assertGreater(done, 150)

    def test_random_editing_then_undo_everything_restores_every_item(self):
        """All kinds of edits (also deleting, duplicating, pasting), then Undo
        back to the very start: every item has exactly its original pictures
        and features again; Redo to the end: still no item has foreign data."""
        names = [f"thing{i:02d}" for i in range(18)]
        base = ("depot/\n├── left/\n" + "".join(f"│   ├── {n}\n" for n in names[:8])
                + "│   └── lonely\n├── right/\n" + "".join(f"│   ├── {n}\n" for n in names[8:17])
                + f"│   └── {names[17]}\n└── end")
        seeds = int(os.environ.get("NODEON_STRESS_SEEDS", "6"))
        for seed in range(1, seeds + 1):
            with self.subTest(seed=seed):
                self.ed.set_document_text(base)
                self.ed.details = {}
                self.win.item_store.reset()
                self.sync()
                rng = random.Random(seed)
                for n in names:
                    if rng.random() < 0.6:
                        self.give(n, must=f"token:{n}", avoid=f"a-{n}",
                                  pics=1 if rng.random() < 0.25 else 0)
                original = {k: v.copy() for k, v in self.ed.details.items()}
                self.assertTrue(original)
                ops = [self.win.a_up, self.win.a_down, self.win.a_left, self.win.a_right,
                       self.win.a_add_sibling, self.win.a_add_child, self.win.a_spacer,
                       self.win.a_delete, self.win.a_delete_line, self.win.a_duplicate,
                       self.win.a_format, self.win.a_up, self.win.a_down, self.win.a_right]
                for step in range(int(os.environ.get("NODEON_STRESS_STEPS", "120"))):
                    live = [n.name for n in self.ed._model.iter_nodes()
                            if n.name.startswith("thing")]
                    if not live:
                        break
                    self.goto_name(rng.choice(live))
                    r = rng.random()
                    if r < 0.10:
                        self.goto_name(self.ed.current_item().name, end=True)
                        QTest.keyClicks(self.ed, "z")
                    elif r < 0.14:
                        self.goto_name(self.ed.current_item().name, end=True)
                        self.key(K.Key_Return)
                        QApplication.clipboard().setText("p1\np2")
                        self.ed.paste()
                    else:
                        rng.choice(ops).trigger()
                    self.sync()
                    self.check_no_foreign(step)
                # Undo everything
                guard = 0
                while self.ed.document().isUndoAvailable() and guard < 2000:
                    self.ed.undo()
                    guard += 1
                    if PER_STEP or guard % (1 + seed % 10) == 0:
                        self.sync()
                        self.check_no_foreign(f"undo {guard}")
                self.settle()
                self.assertEqual(self.ed.toPlainText(), base)
                now = {k: v for k, v in self.ed.details.items()}
                for k, v in original.items():
                    self.assertEqual(now.get(k), v, f"seed {seed}: {k}")
                # Redo everything
                while self.ed.document().isRedoAvailable() and guard < 4000:
                    self.ed.redo()
                    guard += 1
                    if guard % 10 == 0:
                        self.sync()
                        self.check_no_foreign(f"redo {guard}")
                self.settle()
                self.check_no_foreign("end")

    def check_no_foreign(self, where):
        self.ed.ensure_parsed()
        for node in self.ed._model.iter_nodes():
            d = self.ed.details.get(idt.key_of(node))
            if d is not None:
                token = d.must.split(":", 1)[1]
                self.assertTrue(node.name.startswith(token),
                                f"{where}: {node.name!r} shows {d}\n{self.ed.toPlainText()}")

    def test_large_tree_with_many_items_saves_and_loads_fast(self):
        parts = ["warehouse/"]
        for a in range(40):
            last_a = a == 39
            parts.append(("└── " if last_a else "├── ") + f"aisle {a}/")
            pre = "    " if last_a else "│   "
            for b in range(50):
                parts.append(pre + ("└── " if b == 49 else "├── ") + f"box {a}-{b}")
        text = "\n".join(parts)                               # 2041 rows
        self.ed.set_document_text(text)
        self.win.item_store.reset()
        self.ed.ensure_parsed()
        pic = self.win.item_store.import_file(self.pics[0])
        for node in self.ed._model.iter_nodes():
            if node.name.startswith("box") and node.name.endswith(("0", "5")):
                self.ed.details[idt.key_of(node)] = idt.ItemDetails(
                    [dict(pic)], f"must {node.name}\n" * 5, f"avoid {node.name}")
        count = len(self.ed.details)
        self.assertGreater(count, 350)
        self.win.path = self.path
        t = time.perf_counter()
        self.save()
        save_s = time.perf_counter() - t
        t = time.perf_counter()
        self.reopen()
        load_s = time.perf_counter() - t
        self.assertEqual(len(self.ed.details), count)
        self.assertLess(save_s, 10)
        self.assertLess(load_s, 10)
        # moving a whole aisle (50 rows) keeps every box's details
        self.goto_name("aisle 3/")
        before = {n.name: self.ed.details.get(idt.key_of(n))
                  for n in self.ed._model.iter_nodes()}
        t = time.perf_counter()
        self.win.a_down.trigger()
        self.win.a_right.trigger()
        self.settle()
        self.assertLess(time.perf_counter() - t, 10)
        after = {n.name: self.ed.details.get(idt.key_of(n)) for n in self.ed._model.iter_nodes()}
        self.assertEqual(before, after)
        # moving the cursor through the tree is quick
        t = time.perf_counter()
        for line in range(0, 2000, 7):
            self.ed.setTextCursor(QTextCursor(self.ed.document().findBlockByNumber(line)))
            self.win._sync_details_panel()
        self.assertLess(time.perf_counter() - t, 10)

    def test_many_pictures_on_one_item(self):
        self.goto_name("drill")
        paths = []
        for i in range(120):
            paths.append(make_image(os.path.join(self.work, f"p{i}.png"), 30 + i % 50, 30,
                                    f"#{(i * 2) % 256:02x}4080"))
        t = time.perf_counter()
        n, rejected = self.panel.add_files(paths)
        self.assertEqual((n, rejected), (120, []))
        self.assertLess(time.perf_counter() - t, 30)
        for _ in range(130):
            self.panel.next_image()
        self.assertEqual(self.panel.counter.text(), "120 / 120")
        for _ in range(60):
            self.panel.move_image(-1)
        self.assertEqual(self.panel.counter.text(), "60 / 120")
        self.save()
        self.reopen()
        self.goto_name("drill")
        self.assertEqual(self.panel.counter.text(), "1 / 120")
        self.assertEqual(len(os.listdir(os.path.join(self.folder(), "images"))), 120)
        for _ in range(119):
            self.panel.delete_image(0, confirm=False)
        self.save()
        self.assertEqual(len(os.listdir(os.path.join(self.folder(), "images"))), 1)

    def test_rapid_switching_between_items(self):
        for n in ("drill", "hammer", "saw", "paint", "bike"):
            self.give(n, must=n, pics=2)
        rng = random.Random(7)
        for _ in range(300):
            n = rng.choice(["drill", "hammer", "saw", "paint", "bike"])
            self.goto_name(n)
            self.assertEqual(self.panel.must.text(), n)
            self.assertEqual(self.panel.thumbs.count(), 2)
            if rng.random() < 0.3:
                self.panel.next_image()

    def test_repeated_save_reopen_cycles_are_stable(self):
        self.give("drill", "a\nb", "c", pics=2)
        self.give("bike", "d", pics=1)
        first = None
        for _ in range(5):
            self.save()
            data = self.db()
            if first is None:
                first = data
            self.assertEqual(data, first)
            self.reopen()
        self.assertEqual(len(os.listdir(os.path.join(self.folder(), "images"))), 3)


if __name__ == "__main__":
    unittest.main()
