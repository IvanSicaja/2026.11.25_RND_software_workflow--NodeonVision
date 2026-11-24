"""
itemdetails.py - pictures and feature lists for every item of a Nodeon tree.

The right-hand "Item details" panel of Nodeon shows, for the row at the
cursor:

    * the item's name (and where it sits in the tree),
    * its pictures - add by drag & drop, "Add images…" or pasting; zoom,
      pan, previous / next (slideshow), reorder, remove, open large,
    * "Must-have features" (green) and "Features to avoid" (red).

Storage ("database") - next to the tree, like the colour marks:

    garage.txt
    garage.txt.marks.json          colour marks (unchanged)
    garage.txt.items/
        items.json                 which row has which pictures / features
        images/3f9c0a1b2c3d4e5f.jpg  copies of the added pictures

Each row is identified by the same key Nodeon uses for colour marks: the
names from the top of the tree down to the row, each with its occurrence
number among equally named siblings. When a row is moved, renamed,
indented, outdented or brought back with Undo, the editor carries the key
over, so pictures and features always stay with their row.

Pictures and features are saved together with the tree (File > Save), so
the .txt file and the database always describe the same tree. A picture
that is added is copied into a private staging folder first; it moves into
<name>.txt.items/images/ when the tree is saved. "Discard changes" therefore
leaves the folder next to the tree untouched.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from PySide6.QtCore import QEvent, QMimeData, QObject, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QIcon, QImage, QImageReader, QKeySequence, QPainter, QPalette,
                           QPen, QPixmap)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDialog, QFileDialog, QFrame,
                               QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QHBoxLayout,
                               QLabel, QListView, QListWidget, QListWidgetItem, QMenu,
                               QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy, QSplitter,
                               QStackedWidget, QToolButton, QVBoxLayout, QWidget)

NodeKey = Tuple[Tuple[str, int], ...]

DB_FILE = "items.json"
IMAGES_DIR = "images"
FOLDER_SUFFIX = ".items"
DB_VERSION = 1
THUMB_SIZE = 60
_SAFE_FILE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,120}")
_EXT_RE = re.compile(r"\.[a-z0-9]{1,5}")
# Large photos from current phones exceed Qt's default 256 MB decode limit.
IMAGE_ALLOCATION_LIMIT_MB = 1024


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
class ItemDetails:
    """Pictures and feature lists of one tree row."""
    __slots__ = ("images", "must", "avoid")

    def __init__(self, images: Optional[List[Dict[str, str]]] = None,
                 must: str = "", avoid: str = "") -> None:
        # images: [{"file": "<stored file name>", "name": "<original file name>"}]
        self.images: List[Dict[str, str]] = [dict(i) for i in (images or [])]
        self.must: str = must
        self.avoid: str = avoid

    def is_empty(self) -> bool:
        return not self.images and not self.must.strip() and not self.avoid.strip()

    def copy(self) -> "ItemDetails":
        return ItemDetails(self.images, self.must, self.avoid)

    def files(self) -> List[str]:
        return [i["file"] for i in self.images]

    def __eq__(self, other) -> bool:
        return (isinstance(other, ItemDetails) and self.images == other.images
                and self.must == other.must and self.avoid == other.avoid)

    def __repr__(self) -> str:
        return f"ItemDetails(images={len(self.images)}, must={self.must!r}, avoid={self.avoid!r})"

    def to_json(self, key: NodeKey) -> dict:
        return {"path": [[name, nth] for name, nth in key],
                "images": [{"file": i["file"], "name": i.get("name", i["file"])}
                           for i in self.images],
                "must": self.must, "avoid": self.avoid}


def count_features(text: str) -> int:
    """Number of non-empty lines (one feature per line)."""
    return sum(1 for line in text.splitlines() if line.strip())


def key_of(node) -> NodeKey:
    """The stable key of a tree node - identical to treemodel.node_keys():
    names from the top down, each with its number among equally named
    siblings before it."""
    parts: List[Tuple[str, int]] = []
    n = node
    while n is not None and n.parent is not None:
        nth = 0
        for sib in n.parent.children:
            if sib is n:
                break
            if sib.name == n.name:
                nth += 1
        parts.append((n.name, nth))
        n = n.parent
    return tuple(reversed(parts))


def safe_file_name(name) -> bool:
    """Stored picture names are plain file names (never a path)."""
    return isinstance(name, str) and bool(_SAFE_FILE_RE.fullmatch(name)) and ".." not in name


def parse_db(data) -> List[Tuple[NodeKey, ItemDetails]]:
    """Entries of an items.json document. Invalid single entries are skipped;
    a document that is not Nodeon's item database raises ValueError."""
    if not isinstance(data, dict) or not isinstance(data.get("items", []), list):
        raise ValueError("not a Nodeon item database")
    out: List[Tuple[NodeKey, ItemDetails]] = []
    seen = set()
    for item in data.get("items", []):
        try:
            key = tuple((str(name), int(nth)) for name, nth in item["path"])
        except (KeyError, TypeError, ValueError):
            continue
        if not key or key in seen or any(nth < 0 for _n, nth in key):
            continue
        images = []
        for img in item.get("images", []) if isinstance(item.get("images", []), list) else []:
            if isinstance(img, dict) and safe_file_name(img.get("file")):
                name = img.get("name")
                images.append({"file": img["file"],
                               "name": name if isinstance(name, str) and name else img["file"]})
        must = item.get("must", "")
        avoid = item.get("avoid", "")
        details = ItemDetails(images, must if isinstance(must, str) else "",
                              avoid if isinstance(avoid, str) else "")
        if not details.is_empty():
            seen.add(key)
            out.append((key, details))
    return out


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
class ItemStore:
    """Where the pictures and the item database of one tree live."""

    def __init__(self) -> None:
        self.folder: Optional[str] = None       # <tree>.txt.items of the saved tree
        self._staging: Optional[str] = None     # pictures added since the last save
        self.load_error: Optional[str] = None   # items.json could not be read
        self._db_was_bad = False

    # -- locations -----------------------------------------------------------
    @staticmethod
    def folder_for(tree_path: str) -> str:
        return os.path.abspath(tree_path) + FOLDER_SUFFIX

    def staging_dir(self) -> str:
        if self._staging is None or not os.path.isdir(self._staging):
            self._staging = tempfile.mkdtemp(prefix="nodeon-items-")
        return self._staging

    def images_dir(self) -> Optional[str]:
        return os.path.join(self.folder, IMAGES_DIR) if self.folder else None

    def abs_path(self, file: str) -> Optional[str]:
        """Full path of a stored picture (None if the file is missing)."""
        if not safe_file_name(file):
            return None
        if self._staging:
            p = os.path.join(self._staging, file)
            if os.path.isfile(p):
                return p
        if self.folder:
            p = os.path.join(self.folder, IMAGES_DIR, file)
            if os.path.isfile(p):
                return p
        return None

    # -- lifecycle -----------------------------------------------------------
    def reset(self) -> None:
        """A new, unsaved tree: forget the folder, drop staged pictures."""
        self.cleanup()
        self.folder = None
        self.load_error = None
        self._db_was_bad = False

    def cleanup(self) -> None:
        if self._staging:
            shutil.rmtree(self._staging, ignore_errors=True)
        self._staging = None

    def open(self, tree_path: str) -> List[Tuple[NodeKey, ItemDetails]]:
        """Read <tree>.items/items.json. A broken database is reported in
        load_error and is never overwritten or cleaned up without a backup."""
        self.reset()
        self.folder = self.folder_for(tree_path)
        db = os.path.join(self.folder, DB_FILE)
        if not os.path.isfile(db):
            return []
        try:
            with open(db, encoding="utf-8") as f:
                data = json.load(f)
            return parse_db(data)
        except (OSError, ValueError, UnicodeDecodeError) as ex:
            self.load_error = str(ex) or type(ex).__name__
            self._db_was_bad = True
            return []

    # -- adding pictures -----------------------------------------------------
    @staticmethod
    def readable_image(path: str) -> bool:
        if not os.path.isfile(path):
            return False
        reader = QImageReader(path)
        return reader.canRead()

    def _new_name(self, ext: str) -> str:
        while True:
            name = secrets.token_hex(8) + ext
            if self.abs_path(name) is None:
                return name

    def import_file(self, src: str) -> Dict[str, str]:
        """Copy a picture into the staging folder. Raises ValueError for files
        that are not readable pictures, OSError if the copy fails."""
        if not self.readable_image(src):
            raise ValueError("not a picture Nodeon can read")
        ext = os.path.splitext(src)[1].lower()
        if not _EXT_RE.fullmatch(ext or ""):
            fmt = bytes(QImageReader(src).format()).decode("ascii", "ignore").lower()
            ext = "." + fmt if fmt and _EXT_RE.fullmatch("." + fmt) else ".img"
        name = self._new_name(ext)
        shutil.copyfile(src, os.path.join(self.staging_dir(), name))
        return {"file": name, "name": os.path.basename(src) or name}

    def import_image(self, image: QImage, name: str = "pasted image.png") -> Dict[str, str]:
        """Store an in-memory picture (clipboard, browser drop) as PNG."""
        if image is None or image.isNull():
            raise ValueError("empty picture")
        stored = self._new_name(".png")
        if not image.save(os.path.join(self.staging_dir(), stored), "PNG"):
            raise OSError("the picture could not be written")
        return {"file": stored, "name": name}

    # -- saving --------------------------------------------------------------
    def gc_allowed(self, folder: str) -> bool:
        if self._db_was_bad:
            return False
        try:
            return not any(f.startswith(DB_FILE + ".unreadable") for f in os.listdir(folder))
        except OSError:
            return True

    def save(self, tree_path: str, live: Sequence[Tuple[NodeKey, ItemDetails]],
             keep_files: Iterable[str]) -> None:
        """Write the database of the saved tree and put its pictures in place.

        live        entries of rows that exist in the saved tree (database)
        keep_files  every picture still referenced in memory (also rows that
                    were deleted but can come back with Undo) - never removed

        Raises OSError when something cannot be written."""
        new_folder = self.folder_for(tree_path)
        old_images = self.images_dir()
        new_images = os.path.join(new_folder, IMAGES_DIR)
        keep = {f for f in keep_files if safe_file_name(f)}
        live = [(k, d) for k, d in live if not d.is_empty()]

        # 1. Pictures: staged ones move in, ones from another folder (Save As) are copied.
        for f in sorted(keep):
            dst = os.path.join(new_images, f)
            if os.path.isfile(dst):
                staged = os.path.join(self._staging, f) if self._staging else None
                if staged and os.path.isfile(staged):
                    os.remove(staged)
                continue
            src = None
            if self._staging and os.path.isfile(os.path.join(self._staging, f)):
                src = os.path.join(self._staging, f)
            elif old_images and os.path.isfile(os.path.join(old_images, f)):
                src = os.path.join(old_images, f)
            if src is None:
                continue                                  # missing picture: keep the reference
            os.makedirs(new_images, exist_ok=True)
            if src.startswith(self._staging or "\0"):
                shutil.move(src, dst)
            else:
                shutil.copyfile(src, dst)

        # 2. A database that could not be read is kept as a backup, never lost.
        db = os.path.join(new_folder, DB_FILE)
        if self._db_was_bad and os.path.isfile(db) and new_folder == self.folder:
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            os.replace(db, db + f".unreadable-{stamp}")

        # 3. The database itself (atomic: temp file + rename).
        if live:
            os.makedirs(new_folder, exist_ok=True)
            data = {"app": "Nodeon", "version": DB_VERSION,
                    "file": os.path.basename(tree_path),
                    "items": [d.to_json(k) for k, d in live]}
            fd, tmp = tempfile.mkstemp(prefix=".items-", suffix=".tmp", dir=new_folder)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, db)
            except BaseException:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                raise
        elif os.path.isfile(db):
            os.remove(db)

        # 4. Pictures nobody refers to any more are removed - but never while
        #    an unreadable database (or its backup) exists: it may still
        #    refer to them, and pictures must not get lost.
        if self.gc_allowed(new_folder) and os.path.isdir(new_images):
            for f in os.listdir(new_images):
                p = os.path.join(new_images, f)
                if f not in keep and os.path.isfile(p) and safe_file_name(f):
                    os.remove(p)
        for d in (new_images, new_folder):
            try:
                if os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
            except OSError:
                pass

        self.folder = new_folder
        self.load_error = None
        self._db_was_bad = False


# --------------------------------------------------------------------------- #
# Picture loading helpers
# --------------------------------------------------------------------------- #
def _configure_reader_limits() -> None:
    try:
        if QImageReader.allocationLimit() < IMAGE_ALLOCATION_LIMIT_MB:
            QImageReader.setAllocationLimit(IMAGE_ALLOCATION_LIMIT_MB)
    except AttributeError:                                 # pragma: no cover - old Qt
        pass


def load_image(path: Optional[str]) -> Tuple[Optional[QImage], str]:
    """(image, error text). EXIF rotation of phone photos is applied."""
    if not path:
        return None, "The picture file is missing."
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    img = reader.read()
    if img.isNull():
        return None, f"This picture cannot be shown ({reader.errorString()})."
    return img, ""


def load_thumbnail(path: Optional[str], size: int = THUMB_SIZE) -> Optional[QPixmap]:
    if not path:
        return None
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    s = reader.size()
    if s.isValid() and s.width() > 0 and s.height() > 0:
        reader.setScaledSize(s.scaled(QSize(size * 2, size * 2), Qt.AspectRatioMode.KeepAspectRatio))
    img = reader.read()
    if img.isNull():
        return None
    return QPixmap.fromImage(img.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation))


def _placeholder_icon(size: int, text: str, fg: str) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(fg), 1.5, Qt.PenStyle.DashLine))
    p.drawRoundedRect(QRectF(2, 2, size - 4, size - 4), 6, 6)
    p.setPen(QColor(fg))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, text)
    p.end()
    return QIcon(pm)


def mime_files(mime: QMimeData) -> List[str]:
    if mime is None or not mime.hasUrls():
        return []
    return [u.toLocalFile() for u in mime.urls() if u.isLocalFile() and u.toLocalFile()]


def mime_has_pictures(mime: QMimeData) -> bool:
    return bool(mime_files(mime)) or (mime is not None and mime.hasImage())


# --------------------------------------------------------------------------- #
# Keys: typing in the panel must never run tree commands
# --------------------------------------------------------------------------- #
# Commands that keep working while the panel has the keyboard focus.
PANEL_PASSTHROUGH_KEYS = ("Ctrl+S", "Ctrl+Shift+S", "Ctrl+O", "Ctrl+N", "F1", "Ctrl+F", "F3",
                          "Shift+F3", "Alt+F", "Alt+E", "Alt+T", "Alt+V", "Alt+H", "Alt+F4")


class _PanelKeyGuard(QObject):
    """Event filter for the panel's widgets: a key combination that is a
    window command (Ctrl+D duplicate branch, Ctrl+Q delete line, Alt+G colour,
    ...) does nothing while typing in the panel - it neither changes the tree
    nor types a letter. Normal editing keys (copy, paste, undo, word moves)
    keep working, AltGr characters (@, #, [ ...) can be typed, and the file
    commands (Ctrl+S, Ctrl+O, ...) still work."""

    _EDITING_KEYS = tuple(getattr(QKeySequence.StandardKey, n) for n in (
        "Undo", "Redo", "Copy", "Cut", "Paste", "SelectAll", "Delete", "Backspace",
        "MoveToNextWord", "MoveToPreviousWord", "SelectNextWord", "SelectPreviousWord",
        "MoveToStartOfDocument", "MoveToEndOfDocument", "SelectStartOfDocument",
        "SelectEndOfDocument", "MoveToStartOfLine", "MoveToEndOfLine", "SelectStartOfLine",
        "SelectEndOfLine", "MoveToStartOfBlock", "MoveToEndOfBlock", "SelectStartOfBlock",
        "SelectEndOfBlock", "DeleteStartOfWord", "DeleteEndOfWord", "DeleteEndOfLine",
        "DeleteCompleteLine", "MoveToNextPage", "MoveToPreviousPage", "SelectNextPage",
        "SelectPreviousPage", "InsertParagraphSeparator", "InsertLineSeparator")
        if hasattr(QKeySequence.StandardKey, n))
    _MODS = (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
             | Qt.KeyboardModifier.MetaModifier)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._pass = {QKeySequence(k)[0].toCombined() for k in PANEL_PASSTHROUGH_KEYS}
        self._mac = sys.platform == "darwin"

    def _command_key(self, event) -> bool:
        """A Ctrl / Alt combination that is not text input and not an editing key."""
        mods = event.modifiers() & self._MODS
        if not mods:
            return False
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        if ctrl and alt and event.text():
            return False                       # AltGr on Windows: a character (@, #, [ ...)
        if self._mac and alt and not ctrl and event.text():
            return False                       # Option+key on a Mac: a character
        if event.key() in (Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift,
                           Qt.Key.Key_Meta, Qt.Key.Key_AltGr):
            return False
        return not any(event.matches(k) for k in self._EDITING_KEYS)

    def eventFilter(self, obj, event) -> bool:
        t = event.type()
        if t == QEvent.Type.ShortcutOverride:
            if event.keyCombination().toCombined() not in self._pass:
                event.accept()                 # the panel gets the key, not a window command
            return False
        if t == QEvent.Type.KeyPress and self._command_key(event) \
                and event.keyCombination().toCombined() not in self._pass:
            if isinstance(obj, ImageView) and event.matches(QKeySequence.StandardKey.Paste):
                return False
            event.accept()
            return True                        # swallowed: nothing happens
        return False


# --------------------------------------------------------------------------- #
# Picture view: zoom, pan, previous / next
# --------------------------------------------------------------------------- #
class ImageView(QGraphicsView):
    navigate = Signal(int)              # -1 previous, +1 next
    activated = Signal()                # double-click
    emptyClicked = Signal()             # click on the empty "drop here" view
    picturesDropped = Signal(object)    # QMimeData
    zoomChanged = Signal()
    deleteRequested = Signal()
    pasteRequested = Signal()

    MIN_SCALE = 0.02
    MAX_SCALE = 32.0

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self._item = QGraphicsPixmapItem()
        self._item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.scene().addItem(self._item)
        self._fit = True
        self._message = ""
        self._has_image = False
        self.setRenderHints(QPainter.RenderHint.Antialiasing
                            | QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setToolTip("Mouse wheel: zoom  ·  drag: move  ·  ← / →: previous / next  ·  "
                        "+ / − / 0: zoom in / out / fit  ·  double-click: open large")
        self._drop_hover = False

    # -- content ---------------------------------------------------------------
    def set_image(self, image: Optional[QImage], message: str = "") -> None:
        self._message = message
        if image is None or image.isNull():
            self._item.setPixmap(QPixmap())
            self._has_image = False
            self.scene().setSceneRect(QRectF(0, 0, 1, 1))
        else:
            self._item.setPixmap(QPixmap.fromImage(image))
            self._has_image = True
            self.scene().setSceneRect(QRectF(self._item.boundingRect()))
        self._fit = True
        self.fit()
        self.viewport().update()

    def has_image(self) -> bool:
        return self._has_image

    def message(self) -> str:
        return self._message

    def image_size(self) -> QSize:
        return self._item.pixmap().size()

    # -- zoom ------------------------------------------------------------------
    def scale_factor(self) -> float:
        return self.transform().m11()

    def zoom_percent(self) -> int:
        return round(self.scale_factor() * 100)

    def is_fit(self) -> bool:
        return self._fit

    def fit(self) -> None:
        """Whole picture visible (never enlarged beyond 100 %)."""
        self._fit = True
        self.resetTransform()
        if self._has_image:
            r = self._item.boundingRect()
            vw, vh = max(1, self.viewport().width() - 4), max(1, self.viewport().height() - 4)
            s = min(vw / max(1.0, r.width()), vh / max(1.0, r.height()), 1.0)
            s = max(s, self.MIN_SCALE)
            self.scale(s, s)
            self.centerOn(self._item)
        self.zoomChanged.emit()

    def zoom(self, factor: float) -> None:
        if not self._has_image or factor <= 0:
            return
        cur = self.scale_factor()
        target = max(self.MIN_SCALE, min(self.MAX_SCALE, cur * factor))
        if abs(target - cur) < 1e-9:
            return
        self._fit = False
        f = target / cur
        self.scale(f, f)
        self.zoomChanged.emit()

    def zoom_in(self) -> None:
        self.zoom(1.25)

    def zoom_out(self) -> None:
        self.zoom(1 / 1.25)

    def actual_size(self) -> None:
        if self._has_image:
            self.zoom(1.0 / self.scale_factor())

    # -- events ----------------------------------------------------------------
    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        if self._fit:
            self.fit()

    def wheelEvent(self, e) -> None:
        if not self._has_image:
            e.ignore()
            return
        dy = e.angleDelta().y()
        if dy:
            self.zoom(1.15 ** (dy / 120.0))
        e.accept()

    def keyPressEvent(self, e) -> None:
        k, mods = e.key(), e.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        if k in (Qt.Key.Key_Left, Qt.Key.Key_PageUp) and not ctrl:
            self.navigate.emit(-1)
        elif k in (Qt.Key.Key_Right, Qt.Key.Key_PageDown, Qt.Key.Key_Space) and not ctrl:
            self.navigate.emit(1)
        elif k in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_in()
        elif k in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
            self.zoom_out()
        elif k == Qt.Key.Key_0:
            self.fit()
        elif k == Qt.Key.Key_1:
            self.actual_size()
        elif k == Qt.Key.Key_Delete and not ctrl:
            self.deleteRequested.emit()
        elif k == Qt.Key.Key_V and ctrl:
            self.pasteRequested.emit()
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activated.emit()
        else:
            super().keyPressEvent(e)
            return
        e.accept()

    def mouseDoubleClickEvent(self, e) -> None:
        if self._has_image:
            self.activated.emit()
        e.accept()

    def mouseReleaseEvent(self, e) -> None:
        super().mouseReleaseEvent(e)
        if not self._has_image and e.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.emptyClicked.emit()

    def dragEnterEvent(self, e) -> None:
        if mime_has_pictures(e.mimeData()):
            self._drop_hover = True
            self.viewport().update()
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e) -> None:
        if mime_has_pictures(e.mimeData()):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragLeaveEvent(self, e) -> None:
        self._drop_hover = False
        self.viewport().update()
        super().dragLeaveEvent(e)

    def dropEvent(self, e) -> None:
        self._drop_hover = False
        self.viewport().update()
        if mime_has_pictures(e.mimeData()):
            e.acceptProposedAction()
            self.picturesDropped.emit(e.mimeData())
        else:
            e.ignore()

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawForeground(painter, rect)
        if self._has_image and not self._drop_hover:
            return
        painter.save()
        painter.resetTransform()
        vr = QRectF(self.viewport().rect()).adjusted(8, 8, -8, -8)
        pal = self.palette()
        muted = pal.color(QPalette.ColorRole.PlaceholderText)
        if self._drop_hover:
            hl = pal.color(QPalette.ColorRole.Highlight)
            fill = QColor(hl)
            fill.setAlpha(40)
            painter.setBrush(fill)
            painter.setPen(QPen(hl, 2, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(vr, 10, 10)
            painter.setPen(hl)
            painter.drawText(vr, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             "Drop to add the pictures to this item")
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(muted, 1.5, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(vr, 10, 10)
            painter.setPen(muted)
            text = self._message or ("Drop pictures here\nor click to browse…" if self.isEnabled()
                                     else "")
            painter.drawText(vr.adjusted(10, 10, -10, -10),
                             Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)
        painter.restore()


# --------------------------------------------------------------------------- #
# Thumbnail strip (drag to reorder, drop files to add)
# --------------------------------------------------------------------------- #
class ThumbStrip(QListWidget):
    orderChanged = Signal(list)          # stored file names in the new order
    picturesDropped = Signal(object)     # QMimeData from outside
    deleteRequested = Signal()
    pasteRequested = Signal()
    activated = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setViewMode(QListView.ViewMode.ListMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(False)
        self.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        self.setUniformItemSizes(True)
        self.setSpacing(3)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        sb = self.style().pixelMetric(self.style().PixelMetric.PM_ScrollBarExtent)
        self.setFixedHeight(THUMB_SIZE + 14 + sb)
        self.setToolTip("Drag a picture to change the order  ·  Delete: remove  ·  "
                        "double-click: open large")
        self.itemDoubleClicked.connect(lambda _i: self.activated.emit())

    def files(self) -> List[str]:
        return [self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count())]

    def _external(self, e) -> bool:
        return e.source() is not self and mime_has_pictures(e.mimeData())

    def dragEnterEvent(self, e) -> None:
        if self._external(e):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e) -> None:
        if self._external(e):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e) -> None:
        if self._external(e):
            e.acceptProposedAction()
            self.picturesDropped.emit(e.mimeData())
            return
        before = self.files()
        super().dropEvent(e)
        after = self.files()
        if after != before and sorted(after) == sorted(before):
            self.orderChanged.emit(after)

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key.Key_Delete:
            self.deleteRequested.emit()
            e.accept()
            return
        if e.key() == Qt.Key.Key_V and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.pasteRequested.emit()
            e.accept()
            return
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activated.emit()
            e.accept()
            return
        super().keyPressEvent(e)


# --------------------------------------------------------------------------- #
# Feature lists
# --------------------------------------------------------------------------- #
class FeatureSection(QFrame):
    """A coloured header and a scrollable text box (one feature per line)."""
    edited = Signal(str)

    def __init__(self, title: str, symbol: str, placeholder: str, kind: str,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self._title, self._symbol = title, symbol
        self.setObjectName(f"section_{kind}")
        self.setFrameShape(QFrame.Shape.NoFrame)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.header = QLabel()
        self.header.setObjectName(f"header_{kind}")
        self.header.setTextFormat(Qt.TextFormat.PlainText)
        self.body = QPlainTextEdit()
        self.body.setObjectName(f"body_{kind}")
        self.body.setPlaceholderText(placeholder)
        self.body.setTabChangesFocus(True)
        self.body.setMinimumHeight(60)
        self.body.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        lay.addWidget(self.header)
        lay.addWidget(self.body, 1)
        self._loading = False
        self.body.textChanged.connect(self._changed)
        self._update_header()

    def sizeHint(self) -> QSize:                   # the picture gets most of the room
        return QSize(260, 150)

    def _changed(self) -> None:
        self._update_header()
        if not self._loading:
            self.edited.emit(self.body.toPlainText())

    def _update_header(self) -> None:
        n = count_features(self.body.toPlainText())
        self.header.setText(f"{self._symbol}  {self._title}" + (f"  ·  {n}" if n else ""))

    def text(self) -> str:
        return self.body.toPlainText()

    def set_text(self, text: str) -> None:
        if self.body.toPlainText() == text:
            self._update_header()
            return
        self._loading = True
        try:
            self.body.setPlainText(text)
        finally:
            self._loading = False
        self._update_header()

    def apply_colours(self, header_bg: str, header_fg: str, border: str, body_bg: str,
                      body_fg: str) -> None:
        self.header.setStyleSheet(
            f"QLabel#header_{self.kind} {{ background: {header_bg}; color: {header_fg}; "
            f"font-weight: 600; padding: 5px 8px; border: 1px solid {border}; "
            f"border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; }}")
        self.body.setStyleSheet(
            f"QPlainTextEdit#body_{self.kind} {{ background: {body_bg}; color: {body_fg}; "
            f"border: 1px solid {border}; border-bottom-left-radius: 6px; "
            f"border-bottom-right-radius: 6px; padding: 2px 4px; "
            f"selection-background-color: {border}; selection-color: {body_fg}; }}")


# Light, soft colours that are easy on the eyes (header, text, border, body, body text).
SECTION_COLOURS = {
    False: {"must": ("#d9f5e3", "#17663a", "#a8dfbd", "#f3fbf6", "#1f2a24"),
            "avoid": ("#fbe1e1", "#9b2c2c", "#f1b9b9", "#fdf5f5", "#2d2222")},
    True: {"must": ("#1f3a2c", "#9ee6bb", "#2f5a44", "#18241e", "#e3e8e5"),
           "avoid": ("#45242a", "#f5b5b5", "#6a3238", "#271a1d", "#ece3e4")},
}


# --------------------------------------------------------------------------- #
# Large viewer window
# --------------------------------------------------------------------------- #
class ImageViewerDialog(QDialog):
    """A big window for one item's pictures (zoom, pan, previous / next)."""
    indexChanged = Signal(int)

    def __init__(self, parent: QWidget, title: str, paths: List[Optional[str]],
                 names: List[str], index: int) -> None:
        super().__init__(parent)
        self.setObjectName("image_viewer")
        self.setWindowTitle(title)
        self.setModal(True)
        self.paths, self.names = paths, names
        self.index = max(0, min(index, len(paths) - 1))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.view = ImageView(self)
        self.view.setAcceptDrops(False)
        lay.addWidget(self.view, 1)
        row = QHBoxLayout()
        self.b_prev = _tool("‹  Previous", "Previous picture (←)", self.prev)
        self.b_next = _tool("Next  ›", "Next picture (→)", self.next)
        self.counter = QLabel()
        self.caption = QLabel()
        self.caption.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.b_out = _tool("−", "Zoom out (−)", self.view.zoom_out)
        self.zoom_label = QLabel()
        self.zoom_label.setMinimumWidth(48)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.b_in = _tool("+", "Zoom in (+)", self.view.zoom_in)
        self.b_fit = _tool("Fit", "Show the whole picture (0)", self.view.fit)
        self.b_100 = _tool("100 %", "Actual size (1)", self.view.actual_size)
        self.b_close = QPushButton("Close")
        self.b_close.clicked.connect(self.accept)
        for w in (self.b_prev, self.counter, self.b_next):
            row.addWidget(w)
        row.addSpacing(12)
        row.addWidget(self.caption, 1)
        for w in (self.b_out, self.zoom_label, self.b_in, self.b_fit, self.b_100):
            row.addWidget(w)
        row.addSpacing(12)
        row.addWidget(self.b_close)
        lay.addLayout(row)
        self.view.navigate.connect(lambda d: self.next() if d > 0 else self.prev())
        self.view.zoomChanged.connect(self._update_zoom)
        screen = (parent.screen() if parent is not None else None) or QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            self.resize(int(avail.width() * 0.8), int(avail.height() * 0.85))
        self._show()

    def _show(self) -> None:
        n = len(self.paths)
        if n == 0:
            self.view.set_image(None, "No pictures")
        else:
            img, err = load_image(self.paths[self.index])
            self.view.set_image(img, err)
            self.caption.setText(self.names[self.index])
        self.counter.setText(f"{self.index + 1} / {n}" if n else "0 / 0")
        self.b_prev.setEnabled(self.index > 0)
        self.b_next.setEnabled(self.index < n - 1)
        self._update_zoom()
        self.view.setFocus()

    def _update_zoom(self) -> None:
        self.zoom_label.setText(f"{self.view.zoom_percent()} %" if self.view.has_image() else "")

    def prev(self) -> None:
        if self.index > 0:
            self.index -= 1
            self._show()
            self.indexChanged.emit(self.index)

    def next(self) -> None:
        if self.index < len(self.paths) - 1:
            self.index += 1
            self._show()
            self.indexChanged.emit(self.index)


def _tool(text: str, tip: str, slot: Callable[[], None]) -> QToolButton:
    b = QToolButton()
    b.setText(text)
    b.setToolTip(tip)
    b.setAutoRaise(True)
    b.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    b.clicked.connect(lambda _=False: slot())
    return b


# --------------------------------------------------------------------------- #
# The panel
# --------------------------------------------------------------------------- #
class ItemPanel(QWidget):
    """Right-hand panel: name, pictures and feature lists of the row at the
    cursor. The data lives in a registry {key: ItemDetails} owned by the
    editor (so it follows rows when they move); the panel edits it in place
    and emits detailsChanged after every change."""
    detailsChanged = Signal()
    statusMessage = Signal(str)

    IMAGE_FILTER_FALLBACK = "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tif *.tiff *.svg *.ico"

    def __init__(self, registry: Callable[[], Dict[NodeKey, ItemDetails]], store: ItemStore,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        _configure_reader_limits()
        self.setObjectName("item_panel")
        self.registry = registry
        self.store = store
        self.key: Optional[NodeKey] = None
        self.index = 0                             # shown picture
        self.last_dir = ""                         # folder of the last "Add images…"
        self._dark = False
        self._shown_files: Optional[List[str]] = []
        self._displayed: Optional[str] = None      # picture now in the view
        self._thumb_cache: Dict[Tuple[str, float], Optional[QPixmap]] = {}
        self._viewer: Optional[ImageViewerDialog] = None
        self.setMinimumWidth(280)
        self.setAcceptDrops(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(4)
        caption = QLabel("ITEM DETAILS")
        caption.setObjectName("panel_caption")
        f = caption.font()
        f.setPointSizeF(max(6.0, f.pointSizeF() * 0.8))
        f.setBold(True)
        f.setLetterSpacing(f.SpacingType.PercentageSpacing, 110)
        caption.setFont(f)
        outer.addWidget(caption)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        # page 0: nothing selected
        self.placeholder = QLabel("Put the cursor on an item in the tree to see and add its "
                                  "pictures and features.")
        self.placeholder.setWordWrap(True)
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setObjectName("panel_placeholder")
        self.stack.addWidget(self.placeholder)

        # page 1: the item
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.title = QLabel()
        self.title.setObjectName("item_title")
        self.title.setWordWrap(True)
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        tf = self.title.font()
        tf.setPointSizeF(tf.pointSizeF() * 1.25)
        tf.setBold(True)
        self.title.setFont(tf)
        self.crumbs = QLabel()
        self.crumbs.setObjectName("item_path")
        self.crumbs.setWordWrap(True)
        self.crumbs.setTextFormat(Qt.TextFormat.PlainText)
        lay.addWidget(self.title)
        lay.addWidget(self.crumbs)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setObjectName("details_splitter")
        self.splitter.setChildrenCollapsible(False)
        lay.addWidget(self.splitter, 1)

        pics = QWidget()
        pl = QVBoxLayout(pics)
        pl.setContentsMargins(0, 4, 0, 4)
        pl.setSpacing(3)
        self.view = ImageView()
        self.view.setObjectName("item_image")
        pl.addWidget(self.view, 1)

        nav = QHBoxLayout()
        nav.setSpacing(2)
        self.b_prev = _tool("‹", "Previous picture (← in the picture)", self.prev_image)
        self.counter = QLabel()
        self.counter.setObjectName("image_counter")
        self.counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.counter.setMinimumWidth(44)
        self.b_next = _tool("›", "Next picture (→ in the picture)", self.next_image)
        self.b_zoom_out = _tool("−", "Zoom out (− or mouse wheel)", self.view.zoom_out)
        self.zoom_label = QLabel()
        self.zoom_label.setObjectName("zoom_label")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setMinimumWidth(42)
        self.b_zoom_in = _tool("+", "Zoom in (+ or mouse wheel)", self.view.zoom_in)
        self.b_fit = _tool("Fit", "Show the whole picture (0)", self.view.fit)
        self.b_large = _tool("⤢", "Open the pictures in a large window (double-click)",
                             self.open_viewer)
        for w in (self.b_prev, self.counter, self.b_next):
            nav.addWidget(w)
        nav.addStretch(1)
        for w in (self.b_zoom_out, self.zoom_label, self.b_zoom_in, self.b_fit, self.b_large):
            nav.addWidget(w)
        pl.addLayout(nav)

        self.thumbs = ThumbStrip()
        self.thumbs.setObjectName("item_thumbs")
        pl.addWidget(self.thumbs)

        acts = QHBoxLayout()
        acts.setSpacing(4)
        self.b_add = QPushButton("+ Add images…")
        self.b_add.setObjectName("add_images")
        self.b_add.setToolTip("Choose pictures from a folder (you can also drag & drop them "
                              "here, or paste with Ctrl+V in the picture)")
        self.b_add.clicked.connect(lambda _=False: self.browse())
        self.b_move_left = _tool("◂", "Move the shown picture one place to the left "
                                      "(or drag its thumbnail)", lambda: self.move_image(-1))
        self.b_move_right = _tool("▸", "Move the shown picture one place to the right "
                                       "(or drag its thumbnail)", lambda: self.move_image(1))
        self.b_remove = _tool("Remove", "Remove the shown picture from this item (Delete)",
                              lambda: self.delete_image())
        self.b_remove.setObjectName("remove_image")
        acts.addWidget(self.b_add)
        acts.addStretch(1)
        move_label = QLabel("Order")
        move_label.setObjectName("order_label")
        acts.addWidget(move_label)
        acts.addWidget(self.b_move_left)
        acts.addWidget(self.b_move_right)
        acts.addWidget(self.b_remove)
        pl.addLayout(acts)
        self.splitter.addWidget(pics)

        self.must = FeatureSection(
            "Must-have features", "✓",
            "One feature per line – what this item (or a replacement you buy later) must have.\n"
            "e.g. 18 V battery, 2 speeds, metal chuck", "must")
        self.avoid = FeatureSection(
            "Features to avoid", "✕",
            "One feature per line – what you do not want.\n"
            "e.g. corded, heavier than 2 kg, plastic gears", "avoid")
        self.splitter.addWidget(self.must)
        self.splitter.addWidget(self.avoid)
        self.splitter.setStretchFactor(0, 5)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setStretchFactor(2, 2)
        self.sections_restored = False             # True: the user's own sizes were restored
        self._sections_sized = False
        self.stack.addWidget(page)

        # signals
        self.view.navigate.connect(lambda d: self.next_image() if d > 0 else self.prev_image())
        self.view.activated.connect(self.open_viewer)
        self.view.emptyClicked.connect(self.browse)
        self.view.picturesDropped.connect(self.add_from_mime)
        self.view.zoomChanged.connect(self._update_zoom_label)
        self.view.deleteRequested.connect(lambda: self.delete_image())
        self.view.pasteRequested.connect(self.paste_image)
        self.thumbs.currentRowChanged.connect(self._thumb_selected)
        self.thumbs.orderChanged.connect(self._reordered)
        self.thumbs.picturesDropped.connect(self.add_from_mime)
        self.thumbs.deleteRequested.connect(lambda: self.delete_image())
        self.thumbs.pasteRequested.connect(self.paste_image)
        self.thumbs.activated.connect(self.open_viewer)
        self.thumbs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.thumbs.customContextMenuRequested.connect(self._thumb_menu)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(
            lambda pos: self._thumb_menu(pos, self.view))
        self.must.edited.connect(lambda t: self._set_text("must", t))
        self.avoid.edited.connect(lambda t: self._set_text("avoid", t))

        self._guard = _PanelKeyGuard(self)
        for w in (self.view, self.thumbs, self.must.body, self.avoid.body, self.b_add):
            w.installEventFilter(self._guard)

        self.set_dark(False)
        self.show_item(None)

    # ------------------------------------------------------------------ data
    def entry(self) -> Optional[ItemDetails]:
        if self.key is None:
            return None
        return self.registry().get(self.key)

    def _entry_for_write(self) -> ItemDetails:
        reg = self.registry()
        e = reg.get(self.key)
        if e is None:
            e = ItemDetails()
            reg[self.key] = e
        return e

    def _committed(self) -> None:
        reg = self.registry()
        e = reg.get(self.key)
        if e is not None and e.is_empty():
            del reg[self.key]
        self.detailsChanged.emit()

    def images(self) -> List[Dict[str, str]]:
        e = self.entry()
        return list(e.images) if e else []

    # -------------------------------------------------------------- showing
    def show_item(self, key: Optional[NodeKey], name: str = "",
                  path: Sequence[str] = ()) -> None:
        """Show the row with this key (None = no item at the cursor)."""
        same = key is not None and key == self.key
        self.key = key
        if key is None:
            self.stack.setCurrentIndex(0)
            self._shown_files = []
            self._displayed = None
            self.thumbs.clear()
            self.view.set_image(None)
            self.must.set_text("")
            self.avoid.set_text("")
            self._close_viewer()
            return
        self.stack.setCurrentIndex(1)
        self.title.setText(name.strip() or "(item without a name)")
        self.title.setToolTip(name)
        parents = [p for p in list(path)[:-1]]
        self.crumbs.setText(" › ".join(p.strip() or "…" for p in parents) if parents
                            else "Top level")
        e = self.entry()
        if not same and (e.files() if e else []) != self._shown_files:
            self.index = 0                         # another item (not just renamed)
            self._displayed = None
            self._close_viewer()
        self.must.set_text(e.must if e else "")
        self.avoid.set_text(e.avoid if e else "")
        self._refresh_images()

    def refresh(self) -> None:
        """Re-read the registry (after loading a file, Undo, ...)."""
        self._shown_files = None                   # rebuild the thumbnails
        self._displayed = None
        self._thumb_cache.clear()
        if self.key is None:
            return
        e = self.entry()
        self.must.set_text(e.must if e else "")
        self.avoid.set_text(e.avoid if e else "")
        self._refresh_images()

    def _thumb(self, file: str) -> Optional[QPixmap]:
        p = self.store.abs_path(file)
        if p is None:
            return None
        try:
            stamp = os.path.getmtime(p)
        except OSError:
            return None
        ck = (p, stamp)
        if ck not in self._thumb_cache:
            if len(self._thumb_cache) > 600:
                self._thumb_cache.clear()
            self._thumb_cache[ck] = load_thumbnail(p)
        return self._thumb_cache[ck]

    def _refresh_images(self) -> None:
        imgs = self.images()
        files = [i["file"] for i in imgs]
        self.index = max(0, min(self.index, len(imgs) - 1)) if imgs else 0
        if files != self._shown_files:
            self._shown_files = files
            self.thumbs.blockSignals(True)
            self.thumbs.clear()
            muted = self.palette().color(QPalette.ColorRole.PlaceholderText).name()
            for img in imgs:
                pm = self._thumb(img["file"])
                if pm is not None:
                    icon = QIcon(pm)
                    icon.addPixmap(pm, QIcon.Mode.Selected)      # no colour tint when selected
                else:
                    icon = _placeholder_icon(THUMB_SIZE, "missing", muted)
                it = QListWidgetItem(icon, "")
                it.setData(Qt.ItemDataRole.UserRole, img["file"])
                it.setToolTip(img.get("name", img["file"]) + ("" if pm is not None
                                                               else "\n(the file is missing)"))
                it.setSizeHint(QSize(THUMB_SIZE + 8, THUMB_SIZE + 8))
                self.thumbs.addItem(it)
            self.thumbs.blockSignals(False)
        self._show_current()

    def _show_current(self) -> None:
        imgs = self.images()
        n = len(imgs)
        if n:
            path = self.store.abs_path(imgs[self.index]["file"])
            shown = path or imgs[self.index]["file"]
            if shown != self._displayed:          # reload only when it changed: keeps zoom
                self._displayed = shown
                img, err = load_image(path)
                if err:
                    err += f"\n{imgs[self.index].get('name', '')}"
                self.view.set_image(img, err)
            self.thumbs.blockSignals(True)
            self.thumbs.setCurrentRow(self.index)
            self.thumbs.blockSignals(False)
            item = self.thumbs.item(self.index)
            if item is not None:
                self.thumbs.scrollToItem(item)
        else:
            self._displayed = None
            self.view.set_image(None)
        self.counter.setText(f"{self.index + 1} / {n}" if n else "0 / 0")
        self.b_prev.setEnabled(n > 0 and self.index > 0)
        self.b_next.setEnabled(n > 0 and self.index < n - 1)
        for b in (self.b_zoom_in, self.b_zoom_out, self.b_fit):
            b.setEnabled(self.view.has_image())
        for b in (self.b_remove, self.b_large):
            b.setEnabled(n > 0)
        self.b_move_left.setEnabled(n > 1 and self.index > 0)
        self.b_move_right.setEnabled(n > 1 and self.index < n - 1)
        self.thumbs.setVisible(n > 0)
        self._update_zoom_label()

    def _update_zoom_label(self) -> None:
        self.zoom_label.setText(f"{self.view.zoom_percent()} %" if self.view.has_image() else "")

    # ------------------------------------------------------------ navigation
    def select_image(self, index: int) -> None:
        n = len(self.images())
        if n and 0 <= index < n and index != self.index:
            self.index = index
            self._show_current()

    def next_image(self) -> None:
        self.select_image(self.index + 1)

    def prev_image(self) -> None:
        self.select_image(self.index - 1)

    def _thumb_selected(self, row: int) -> None:
        if row >= 0:
            self.select_image(row)

    # -------------------------------------------------------------- editing
    def _set_text(self, which: str, text: str) -> None:
        if self.key is None:
            return
        e = self.registry().get(self.key)
        if (getattr(e, which) if e else "") == text:
            return
        setattr(self._entry_for_write(), which, text)
        self._committed()

    def add_files(self, paths: Iterable[str]) -> Tuple[int, List[str]]:
        """Add picture files to the item at the cursor.
        Returns (number added, names that are not pictures / failed)."""
        if self.key is None:
            self.statusMessage.emit("Put the cursor on an item first")
            return 0, []
        added: List[Dict[str, str]] = []
        rejected: List[str] = []
        for p in paths:
            if os.path.isdir(p):
                rejected.append(os.path.basename(p.rstrip("/\\")) + " (folder)")
                continue
            try:
                added.append(self.store.import_file(p))
            except (ValueError, OSError):
                rejected.append(os.path.basename(p) or p)
        if added:
            e = self._entry_for_write()
            e.images.extend(added)
            self.index = len(e.images) - len(added)
            self._committed()
            self._refresh_images()
        self._report(len(added), rejected)
        return len(added), rejected

    def add_image(self, image: QImage, name: str = "pasted image.png") -> bool:
        if self.key is None:
            self.statusMessage.emit("Put the cursor on an item first")
            return False
        try:
            ref = self.store.import_image(image, name)
        except (ValueError, OSError) as ex:
            self.statusMessage.emit(f"The picture could not be added: {ex}")
            return False
        e = self._entry_for_write()
        e.images.append(ref)
        self.index = len(e.images) - 1
        self._committed()
        self._refresh_images()
        self._report(1, [])
        return True

    def _report(self, added: int, rejected: List[str]) -> None:
        msg = []
        if added:
            msg.append(f"{added} picture{'s' if added != 1 else ''} added - saved with the tree")
        if rejected:
            shown = ", ".join(rejected[:5]) + (" …" if len(rejected) > 5 else "")
            msg.append(f"not a picture, skipped: {shown}")
        if msg:
            self.statusMessage.emit("; ".join(msg))

    def add_from_mime(self, mime: QMimeData) -> None:
        files = mime_files(mime)
        if files:
            self.add_files(files)
        elif mime is not None and mime.hasImage():
            img = mime.imageData()
            if isinstance(img, QPixmap):
                img = img.toImage()
            if isinstance(img, QImage):
                self.add_image(img, "dropped image.png")

    def paste_image(self) -> None:
        mime = QApplication.clipboard().mimeData()
        if mime is None or not mime_has_pictures(mime):
            self.statusMessage.emit("The clipboard has no picture")
            return
        self.add_from_mime(mime)

    def image_filter(self) -> str:
        fmts = sorted({bytes(f).decode("ascii", "ignore").lower()
                       for f in QImageReader.supportedImageFormats()})
        pats = " ".join(f"*.{f}" for f in fmts if f) or self.IMAGE_FILTER_FALLBACK
        return f"Pictures ({pats});;All files (*)"

    def browse(self) -> None:
        if self.key is None:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Add pictures to this item",
                                                self.last_dir, self.image_filter())
        if paths:
            self.last_dir = os.path.dirname(paths[0])
            self.add_files(paths)

    def delete_image(self, index: Optional[int] = None, confirm: bool = True) -> bool:
        imgs = self.images()
        if not imgs:
            return False
        i = self.index if index is None else index
        if not 0 <= i < len(imgs):
            return False
        if confirm:
            r = QMessageBox.question(
                self, "Remove picture",
                f"Remove the picture “{imgs[i].get('name', '')}” from this item?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes:
                return False
        e = self._entry_for_write()
        del e.images[i]
        self.index = min(i, len(e.images) - 1) if e.images else 0
        self._committed()
        self._refresh_images()
        self.statusMessage.emit("Picture removed from this item")
        return True

    def move_image(self, delta: int, index: Optional[int] = None) -> bool:
        imgs = self.images()
        i = self.index if index is None else index
        j = i + delta
        if not (0 <= i < len(imgs) and 0 <= j < len(imgs)) or delta == 0:
            return False
        e = self._entry_for_write()
        e.images[i], e.images[j] = e.images[j], e.images[i]
        self.index = j
        self._committed()
        self._refresh_images()
        return True

    def _reordered(self, files: List[str]) -> None:
        e = self.entry()
        if e is None or sorted(files) != sorted(e.files()):
            self._shown_files = None
            self._refresh_images()
            return
        current = e.images[self.index]["file"] if e.images else None
        by_file: Dict[str, List[Dict[str, str]]] = {}
        for img in e.images:
            by_file.setdefault(img["file"], []).append(img)
        e.images = [by_file[f].pop(0) for f in files]
        if current in files:
            self.index = files.index(current)
        self._committed()
        self._shown_files = None                   # rebuild the strip in the stored order
        self._refresh_images()

    def _thumb_menu(self, pos, widget=None) -> None:
        widget = widget or self.thumbs
        if widget is self.thumbs:
            item = self.thumbs.itemAt(pos)
            if item is not None:
                self.select_image(self.thumbs.row(item))
        m = QMenu(self)
        has = bool(self.images())
        m.addAction("Open large", self.open_viewer).setEnabled(has)
        m.addSeparator()
        m.addAction("Add images…", self.browse)
        m.addAction("Paste picture", self.paste_image)
        m.addSeparator()
        m.addAction("Move left", lambda: self.move_image(-1)).setEnabled(
            has and self.index > 0)
        m.addAction("Move right", lambda: self.move_image(1)).setEnabled(
            has and self.index < len(self.images()) - 1)
        m.addSeparator()
        m.addAction("Remove picture", lambda: self.delete_image()).setEnabled(has)
        m.popup(widget.mapToGlobal(pos))

    # --------------------------------------------------------------- viewer
    def open_viewer(self) -> Optional[ImageViewerDialog]:
        imgs = self.images()
        if not imgs:
            return None
        self._close_viewer()
        dlg = ImageViewerDialog(self.window(), self.title.text(),
                                [self.store.abs_path(i["file"]) for i in imgs],
                                [i.get("name", i["file"]) for i in imgs], self.index)
        dlg.indexChanged.connect(self.select_image)
        dlg.finished.connect(lambda _r: setattr(self, "_viewer", None))
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._viewer = dlg
        dlg.show()
        return dlg

    def _close_viewer(self) -> None:
        if self._viewer is not None:
            v, self._viewer = self._viewer, None
            v.close()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        if not self._sections_sized and not self.sections_restored:
            self._sections_sized = True
            QTimer.singleShot(0, self._default_section_sizes)

    def _default_section_sizes(self) -> None:
        h = sum(self.splitter.sizes())
        if h > 0:
            pic = int(h * 0.62)
            self.splitter.setSizes([pic, (h - pic) // 2, h - pic - (h - pic) // 2])

    # ---------------------------------------------------------- drag & drop
    def dragEnterEvent(self, e) -> None:
        if self.key is not None and mime_has_pictures(e.mimeData()):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e) -> None:
        self.dragEnterEvent(e)

    def dropEvent(self, e) -> None:
        if self.key is not None and mime_has_pictures(e.mimeData()):
            e.acceptProposedAction()
            self.add_from_mime(e.mimeData())
        else:
            e.ignore()

    # ---------------------------------------------------------------- theme
    def set_dark(self, dark: bool) -> None:
        self._dark = bool(dark)
        cols = SECTION_COLOURS[self._dark]
        self.must.apply_colours(*cols["must"])
        self.avoid.apply_colours(*cols["avoid"])
        muted = "#9aa0aa" if self._dark else "#6b7280"
        self.crumbs.setStyleSheet(f"color: {muted};")
        self.placeholder.setStyleSheet(f"color: {muted}; padding: 16px;")
        self.findChild(QLabel, "panel_caption").setStyleSheet(f"color: {muted};")
        self.counter.setStyleSheet(f"color: {muted};")
        self.findChild(QLabel, "order_label").setStyleSheet(f"color: {muted};")
        self.zoom_label.setStyleSheet(f"color: {muted};")
        bg = "#1b1d22" if self._dark else "#f4f5f7"
        self.view.setBackgroundBrush(QColor(bg))
        hl = "#5b9cf5" if self._dark else "#2f6fde"
        self.thumbs.setStyleSheet(
            "QListWidget#item_thumbs { border: none; background: transparent; }"
            "QListWidget#item_thumbs::item { border: 2px solid transparent; border-radius: 5px;"
            " padding: 1px; background: transparent; }"
            f"QListWidget#item_thumbs::item:selected {{ border: 2px solid {hl};"
            " background: transparent; }"
            f"QListWidget#item_thumbs::item:hover:!selected {{ border: 2px solid {muted}; }}")
        self.view.viewport().update()
        if self._shown_files:
            self._shown_files = None
            self._refresh_images()
