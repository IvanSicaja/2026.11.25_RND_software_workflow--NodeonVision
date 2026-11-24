"""
nodeon_driver.py - drives the real Nodeon application for system tests.

This is the "page object" / "application driver" layer of the test
architecture:

    Gherkin feature  ->  step definitions (Behave / pytest-bdd)  ->  THIS DRIVER  ->  Nodeon
    pytest test      ------------------------------------------>  THIS DRIVER  ->  Nodeon

The tests describe WHAT to check; the driver knows HOW to operate the
application (keys, toolbar buttons, dialogs) and how to read results
(text, colours, legend, level indicator). When the user interface changes,
only the driver changes - not the hundreds of tests.

The application runs in the same process, without a visible window
(Qt "offscreen" platform), so the tests also run on a Linux build server
or inside Docker. Each driver works in its own temporary folder with its own
settings and default-legend file, so tests never touch the tester's real
Nodeon settings.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Callable, List, Optional, Set, Tuple

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAIN_PY = PROJECT_ROOT / "main" / "main.py"
TEST_DATA = PROJECT_ROOT / "tests" / "test_automation" / "specs" / "test_data"
ARROW = "➡️"

from PySide6.QtCore import QEvent, QPoint, QPointF, QSettings, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QKeySequence, QTextCursor  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

_APP_MODULE = None


def app_module():
    """Load main/main.py once, by its path (the name 'main' alone would clash
    with the main/ folder)."""
    global _APP_MODULE
    if _APP_MODULE is None:
        spec = importlib.util.spec_from_file_location("nodeon_app_under_test", MAIN_PY)
        module = importlib.util.module_from_spec(spec)
        sys.modules["nodeon_app_under_test"] = module
        spec.loader.exec_module(module)
        _APP_MODULE = module
    return _APP_MODULE


def u16(text: str) -> int:
    """Length in Qt (UTF-16) positions - the ➡️ arrow counts as 2."""
    return len(text.encode("utf-16-le")) // 2


class NodeonDriver:
    """One Nodeon window plus everything needed to operate and observe it."""

    def __init__(self, workdir: Path) -> None:
        self.m = app_module()
        self.qapp = QApplication.instance() or QApplication([])
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.win = None
        self.path: Optional[Path] = None
        # Answers for message boxes the application may ask (FIFO). Anything
        # not answered makes the test fail instead of hanging.
        self.answers: List[str] = []
        self.messages: List[Tuple[str, str]] = []      # (kind, text) of shown boxes
        self._patch()

    # ------------------------------------------------------------------ setup
    def _patch(self) -> None:
        m = self.m
        ini = str(self.workdir / "settings.ini")
        self._orig = {
            "QSettings": m.QSettings,
            "question": m.QMessageBox.question,
            "warning": m.QMessageBox.warning,
            "critical": m.QMessageBox.critical,
            "information": m.QMessageBox.information,
            "about": m.QMessageBox.about,
            "exec": m.QMessageBox.exec,
            "env": os.environ.get(m.DEFAULT_COLOURS_ENV),
        }
        m.QSettings = lambda *a: QSettings(ini, QSettings.Format.IniFormat)
        os.environ[m.DEFAULT_COLOURS_ENV] = str(self.workdir / "default_colours.json")
        drv = self

        def record(kind):
            def box(*args, **kwargs):
                texts = [a for a in args if isinstance(a, str)]
                drv.messages.append((kind, " | ".join(texts)))
                if kind == "question":
                    if not drv.answers:
                        raise AssertionError(f"Unexpected question: {texts}")
                    answer = drv.answers.pop(0)
                    return getattr(QMessageBox.StandardButton, answer)
                return QMessageBox.StandardButton.Ok
            return staticmethod(box)

        for kind in ("question", "warning", "critical", "information", "about"):
            setattr(m.QMessageBox, kind, record(kind))

        def box_exec(box):
            drv.messages.append(("box", box.text() + " | " + box.informativeText()))
            if not drv.answers:
                raise AssertionError(f"Unexpected message box: {box.text()}")
            wanted = drv.answers.pop(0)
            for b in box.buttons():
                if b.text() == wanted or box.standardButton(b) == getattr(
                        QMessageBox.StandardButton, wanted, None):
                    b.click()
                    return 0
            raise AssertionError(f"No button {wanted!r} in message box {box.text()!r}")
        m.QMessageBox.exec = box_exec

    def restore(self) -> None:
        """Undo all patches (call once at the very end)."""
        m = self.m
        m.QSettings = self._orig["QSettings"]
        for kind in ("question", "warning", "critical", "information", "about", "exec"):
            setattr(m.QMessageBox, kind, self._orig[kind])
        if self._orig["env"] is None:
            os.environ.pop(m.DEFAULT_COLOURS_ENV, None)
        else:
            os.environ[m.DEFAULT_COLOURS_ENV] = self._orig["env"]

    # --------------------------------------------------------------- lifecycle
    def open_text(self, text: str, name: str = "tree.txt") -> Path:
        """Write `text` to a file in the work folder and open it in Nodeon."""
        path = self.workdir / name
        path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        for extra in (path.with_name(path.name + ".marks.json"),):
            if extra.exists():
                extra.unlink()
        return self.open_file(path)

    def open_test_file(self, name: str) -> Path:
        """Copy a file from specs/test_data and open the copy."""
        src = TEST_DATA / name
        dst = self.workdir / name
        dst.write_bytes(src.read_bytes())
        marks = dst.with_name(dst.name + ".marks.json")
        if marks.exists():
            marks.unlink()
        return self.open_file(dst)

    def open_file(self, path: Path) -> Path:
        self.close()
        self.path = Path(path)
        self.win = self.m.MainWindow(str(self.path))
        self.win.show()
        self.wait(30)
        self.editor.setFocus()
        return self.path

    def new_window(self) -> None:
        """A fresh application start without a file."""
        self.close()
        self.path = None
        self.win = self.m.MainWindow(None)
        self.win.show()
        self.wait(30)
        self.editor.setFocus()

    def reopen(self) -> None:
        assert self.path is not None, "the tree was never saved"
        self.open_file(self.path)

    def close(self) -> None:
        if self.win is not None:
            self.win.editor.document().setModified(False)
            self.win.close()
            self.win.deleteLater()
            self.win = None
            self.wait(10)

    @property
    def editor(self):
        return self.win.editor

    def wait(self, ms: int = 10) -> None:
        QTest.qWait(ms)

    def settle(self) -> None:
        """Let the editor re-read the text after typing (debounce timer)."""
        self.wait(300)

    # ---------------------------------------------------------------- keyboard
    def press(self, keys: str, times: int = 1) -> None:
        """Press a key combination like 'Alt+Shift+G', 'Ctrl+Enter', 'Tab'."""
        seq = QKeySequence(keys)
        if seq.isEmpty():
            raise ValueError(f"Unknown key combination: {keys!r}")
        combo = seq[0]
        key, mods = combo.key(), combo.keyboardModifiers()
        if key == Qt.Key.Key_Tab and mods & Qt.KeyboardModifier.ShiftModifier:
            key = Qt.Key.Key_Backtab                 # what a real keyboard sends
        for _ in range(times):
            QTest.keyClick(self.editor, key, mods)
            self.wait(5)

    def type(self, text: str) -> None:
        """Type text. Non-ASCII text (e.g. ➡️) is inserted like an emoji keyboard does."""
        if text.isascii():
            QTest.keyClicks(self.editor, text)
        else:
            self.editor.insertPlainText(text)
        self.settle()

    def paste(self, text: str) -> None:
        QApplication.clipboard().setText(text)
        self.press("Ctrl+V")
        self.wait(10)

    # ------------------------------------------------------------------ cursor
    def click_into_editor(self) -> None:
        """What a mouse click into the text does: activate the window and give
        the editor the keyboard focus."""
        self.win.activateWindow()
        self.editor.setFocus()
        self.wait(5)

    def _set_cursor(self, line: int, col: int, anchor: Optional[Tuple[int, int]] = None) -> None:
        self.click_into_editor()
        doc = self.editor.document()
        cur = QTextCursor(doc)
        if anchor is not None:
            ab = doc.findBlockByNumber(anchor[0])
            cur.setPosition(ab.position() + u16(ab.text()[:anchor[1]]))
        b = doc.findBlockByNumber(line)
        mode = QTextCursor.MoveMode.KeepAnchor if anchor is not None else QTextCursor.MoveMode.MoveAnchor
        cur.setPosition(b.position() + u16(b.text()[:col]), mode)
        self.editor.setTextCursor(cur)

    def find(self, text: str) -> Tuple[int, int]:
        """(line index 0-based, column) of the first occurrence of text."""
        for i, line in enumerate(self.lines()):
            if text in line:
                return i, line.index(text)
        raise AssertionError(f"{text!r} not found in the tree:\n{self.text()}")

    def cursor_end_of_line(self, number: int) -> None:
        """Line numbers as shown in Nodeon's margin (1 = first line)."""
        self._set_cursor(number - 1, len(self.lines()[number - 1]))

    def cursor_start_of_line(self, number: int) -> None:
        self._set_cursor(number - 1, 0)

    def cursor_on(self, text: str, offset: int = 1) -> None:
        """Cursor `offset` characters inside the first occurrence of text."""
        line, col = self.find(text)
        self._set_cursor(line, col + offset)

    def cursor_after(self, text: str) -> None:
        line, col = self.find(text)
        self._set_cursor(line, col + len(text))

    def select(self, text: str) -> None:
        line, col = self.find(text)
        self._set_cursor(line, col + len(text), anchor=(line, col))

    def select_lines(self, first: int, last: int) -> None:
        self._set_cursor(last - 1, len(self.lines()[last - 1]), anchor=(first - 1, 0))

    # ----------------------------------------------------------------- toolbar
    def toolbar_buttons(self) -> List[str]:
        return [b._label for b in self.win.findChildren(self.m.ActionButton)]

    def click_toolbar(self, label: str) -> None:
        buttons = {b._label: b for b in self.win.findChildren(self.m.ActionButton)}
        if label not in buttons:
            raise AssertionError(f"No toolbar button {label!r}; there are {sorted(buttons)}")
        btn = buttons[label]
        if btn.menu() is not None:
            raise AssertionError(f"{label!r} opens a menu - use menu_actions()")
        btn.defaultAction().trigger()
        self.wait(10)

    # ------------------------------------------------------------------ dialogs
    def when_dialog(self, handle: Callable[[QDialog], None], timeout_ms: int = 5000) -> None:
        """Run `handle(dialog)` as soon as a modal dialog is open (the code that
        opens it blocks until the dialog is closed)."""
        state = {"left": timeout_ms}

        def poll():
            dlg = QApplication.activeModalWidget()
            if isinstance(dlg, QDialog) and dlg.isVisible():
                handle(dlg)
                return
            state["left"] -= 20
            if state["left"] > 0:
                QTimer.singleShot(20, poll)
        QTimer.singleShot(20, poll)

    def add_colour(self, meaning: str, color: Optional[str] = None) -> None:
        """Add a colour through the legend button and the real colour dialog
        (suggested colour and shortcuts are accepted)."""
        def fill(dlg):
            dlg.meaning.setText(meaning)
            if color:
                dlg.set_colour(color)
            err = dlg.validate()
            if err:
                dlg.reject()
                raise AssertionError(err)
            dlg.accept()
        self.when_dialog(fill)
        add = [b for b in self.win.legend.findChildren(self.m.QToolButton)
               if b.text() == "+ Add colour"][0]
        add.click()
        self.wait(20)

    # ------------------------------------------------------------- observation
    def text(self) -> str:
        return self.editor.toPlainText()

    def lines(self) -> List[str]:
        return self.text().split("\n")

    def visible_lines(self) -> int:
        doc = self.editor.document()
        return sum(1 for i in range(doc.blockCount()) if doc.findBlockByNumber(i).isVisible())

    def level(self) -> Tuple[int, int]:
        self.editor.ensure_parsed()
        return self.editor.current_level(), self.editor.max_level()

    def status(self) -> str:
        return self.win.statusBar().currentMessage()

    def colours_of(self, line_index: int, text: str) -> Set[str]:
        """Colours (hex) used to draw `text` in a line (0-based)."""
        block = self.editor.document().findBlockByNumber(line_index)
        t = block.text()
        start = u16(t[:t.index(text)])
        out = set()
        for pos in range(start, start + u16(text)):
            col = None
            for r in block.layout().formats():
                if r.start <= pos < r.start + r.length:
                    col = r.format.foreground().color().name()
            out.add(col)
        return out

    def colour_of_text(self, text: str) -> Set[str]:
        line, _ = self.find(text)
        return self.colours_of(line, text)

    def legend(self) -> List[Tuple[str, str]]:
        """[(meaning, colour hex)] of the legend, left to right."""
        return [(c.legend_label, c.legend_color) for c in self.win.legend.chips]

    def meaning_colour(self, meaning: str, name: str = "") -> str:
        """Colour the legend shows for a meaning. For the default text colour,
        folder names (ending with /) keep their folder colour."""
        pal, theme = self.editor.colours, self.editor.theme
        if meaning == pal.text_label and name.endswith(("/", "\\")):
            return QColor(theme.folder).name()
        for label, color in self.legend():
            if label == meaning:
                return color
        raise AssertionError(f"{meaning!r} is not in the legend: {self.legend()}")

    def explanation_colour(self) -> str:
        return QColor(self.editor.colours.explanation_colour(self.editor.theme)).name()

    def saved_text(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def marks_file(self) -> Optional[dict]:
        mf = self.path.with_name(self.path.name + ".marks.json")
        return json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else None

    # ------------------------------------------- item details (pictures, features)
    @property
    def panel(self):
        """The 'Item details' panel on the right."""
        return self.win.details_panel

    def make_picture(self, name: str, width: int = 80, height: int = 60,
                     color: str = "#3366cc") -> Path:
        """Create a picture file in the work folder (like a photo the user has)."""
        from PySide6.QtGui import QImage
        path = self.workdir / "photos" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        img = QImage(width, height, QImage.Format.Format_RGB32)
        img.fill(QColor(color))
        assert img.save(str(path)), path
        return path

    def show_item(self, name: str) -> None:
        """Put the cursor on a branch name; the panel shows that item."""
        self.cursor_on(name)
        self.sync_panel()

    def sync_panel(self) -> None:
        self.settle()
        self.win._sync_details_panel()

    def drop_pictures(self, *paths: Path) -> None:
        """Drag files from the file manager and drop them on the picture."""
        from PySide6.QtCore import QMimeData, QUrl
        from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
        view = self.panel.view.viewport()
        pos = QPointF(view.width() / 2, view.height() / 2)
        args = (Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier)
        # what the window system sends during a real drag & drop
        QApplication.sendEvent(view, QDragEnterEvent(pos.toPoint(), *args))
        QApplication.sendEvent(view, QDragMoveEvent(pos.toPoint(), *args))
        QApplication.sendEvent(view, QDropEvent(pos, *args))
        self.wait(10)

    def browse_pictures(self, *paths: Path) -> None:
        """'+ Add images…' and choose files in the file dialog."""
        from PySide6.QtWidgets import QFileDialog
        orig = QFileDialog.getOpenFileNames
        QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([str(p) for p in paths], ""))
        try:
            self.panel.b_add.click()
        finally:
            QFileDialog.getOpenFileNames = orig
        self.wait(10)

    def item_title(self) -> str:
        return self.panel.title.text() if self.panel.stack.currentIndex() == 1 else ""

    def picture_counter(self) -> str:
        return self.panel.counter.text()

    def shown_picture_size(self) -> Tuple[int, int]:
        s = self.panel.view.image_size()
        return s.width(), s.height()

    def item_details(self, name: str):
        """Stored details (pictures, features) of the first row named `name`."""
        import itemdetails
        self.editor.ensure_parsed()
        for node in self.editor._model.iter_nodes():
            if node.name == name:
                return self.editor.details.get(itemdetails.key_of(node))
        raise AssertionError(f"No row named {name!r}:\n{self.text()}")

    def picture_names(self, name: str) -> List[str]:
        d = self.item_details(name)
        return [i["name"] for i in d.images] if d else []

    def type_features(self, which: str, text: str) -> None:
        """Type into 'Must-have features' (which='must') or 'Features to avoid'."""
        box = (self.panel.must if which == "must" else self.panel.avoid).body
        box.setFocus()
        for i, line in enumerate(text.split("\n")):
            if i:
                QTest.keyClick(box, Qt.Key.Key_Return)
            QTest.keyClicks(box, line)
        self.wait(10)

    def items_folder(self) -> Path:
        return self.path.with_name(self.path.name + ".items")

    def items_db(self) -> Optional[dict]:
        db = self.items_folder() / "items.json"
        return json.loads(db.read_text(encoding="utf-8")) if db.exists() else None

    def stored_picture_files(self) -> List[str]:
        d = self.items_folder() / "images"
        return sorted(p.name for p in d.iterdir()) if d.exists() else []
