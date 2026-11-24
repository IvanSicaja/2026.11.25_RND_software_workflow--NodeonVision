"""Unit tests for main/itemdetails.py - the item database and picture storage
(no window needed). Run from the project root:
    python -m unittest discover tests
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "main"))

try:
    from PySide6.QtGui import QColor, QGuiApplication, QImage
except ImportError:                                     # pragma: no cover
    QGuiApplication = None

if QGuiApplication is not None:
    import itemdetails as idt
    import treemodel as tm


def make_image(path, w=40, h=30, color="#3366cc", fmt=None):
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(color))
    assert img.save(path, fmt), path
    return path


@unittest.skipIf(QGuiApplication is None, "PySide6 is not installed")
class ItemDetailsDataTests(unittest.TestCase):
    def test_empty_and_copy(self):
        d = idt.ItemDetails()
        self.assertTrue(d.is_empty())
        d.must = "   \n  "
        self.assertTrue(d.is_empty(), "whitespace only is empty")
        d.avoid = "noisy"
        self.assertFalse(d.is_empty())
        c = d.copy()
        self.assertEqual(c, d)
        c.images.append({"file": "a.png", "name": "a.png"})
        self.assertEqual(d.images, [], "copy is independent")

    def test_count_features(self):
        self.assertEqual(idt.count_features(""), 0)
        self.assertEqual(idt.count_features("a\n\n  \nb\nc  "), 3)

    def test_key_of_matches_treemodel_node_keys(self):
        text = ("root/\n├── a\n│   ├── x\n│   ├── x\n│   └── y\n├── a\n│   └── x\n"
                "└── b\n    └── a\n        └── a")
        doc, _ = tm.parse(text)
        keys = tm.node_keys(doc)
        for node in doc.iter_nodes():
            self.assertEqual(idt.key_of(node), keys[id(node)], node.path())

    def test_safe_file_names(self):
        for ok in ("abc.png", "3f9c0a1b2c3d4e5f.jpg", "A-b_c.1.webp"):
            self.assertTrue(idt.safe_file_name(ok), ok)
        for bad in ("", "../x.png", "a/b.png", "a\\b.png", ".hidden", "..", "a..png", None, 5,
                    "x" * 200):
            self.assertFalse(idt.safe_file_name(bad), bad)

    def test_parse_db_tolerant(self):
        data = {"items": [
            {"path": [["root/", 0], ["a", 0]], "images": [{"file": "f1.png", "name": "drill.png"}],
             "must": "18 V", "avoid": "corded"},
            {"path": [["root/", 0], ["a", 0]], "must": "duplicate key is skipped"},
            {"path": "broken"},
            {"path": [["root/", 0], ["b", -1]], "must": "negative index"},
            {"path": [], "must": "empty path"},
            {"path": [["root/", 0], ["c", 0]], "images": [{"file": "../../etc/passwd"}],
             "must": ""},                                     # only an unsafe file -> empty
            {"path": [["root/", 0], ["d", 0]], "images": "nope", "must": 5, "avoid": "x"},
        ]}
        entries = idt.parse_db(data)
        self.assertEqual([k for k, _ in entries],
                         [(("root/", 0), ("a", 0)), (("root/", 0), ("d", 0))])
        a = entries[0][1]
        self.assertEqual(a.images, [{"file": "f1.png", "name": "drill.png"}])
        self.assertEqual((a.must, a.avoid), ("18 V", "corded"))
        d = entries[1][1]
        self.assertEqual((d.images, d.must, d.avoid), ([], "", "x"))
        for bad in ([], "x", {"items": "x"}, None):
            with self.assertRaises(ValueError):
                idt.parse_db(bad)

    def test_json_round_trip(self):
        key = (("Garage/", 0), ("Shelf ünïcødé ➡️", 1))
        d = idt.ItemDetails([{"file": "a.png", "name": "Ä b.png"}], "x\ny", "z")
        back = idt.parse_db(json.loads(json.dumps({"items": [d.to_json(key)]})))
        self.assertEqual(back, [(key, d)])


@unittest.skipIf(QGuiApplication is None, "PySide6 is not installed")
class ItemStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="nodeon-store-")
        self.tree = os.path.join(self.tmp, "garage.txt")
        with open(self.tree, "w", encoding="utf-8") as f:
            f.write("garage/\n└── drill\n")
        self.store = idt.ItemStore()
        self.png = make_image(os.path.join(self.tmp, "photo one.png"))
        self.jpg = make_image(os.path.join(self.tmp, "photo.JPG"), color="#cc3333")

    def tearDown(self):
        self.store.cleanup()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def key(self, name="drill"):
        return (("garage/", 0), (name, 0))

    def test_folder_name(self):
        self.assertEqual(idt.ItemStore.folder_for(self.tree), os.path.abspath(self.tree) + ".items")

    def test_import_copies_into_staging_not_next_to_tree(self):
        ref = self.store.import_file(self.png)
        self.assertEqual(ref["name"], "photo one.png")
        self.assertTrue(ref["file"].endswith(".png"))
        self.assertTrue(idt.safe_file_name(ref["file"]))
        p = self.store.abs_path(ref["file"])
        self.assertTrue(os.path.isfile(p))
        self.assertFalse(p.startswith(self.tmp), "staged outside the user's folder")
        self.assertTrue(os.path.isfile(self.png), "the original is never moved")
        ref2 = self.store.import_file(self.jpg)
        self.assertTrue(ref2["file"].endswith(".jpg"), "extension lower-cased")
        self.assertNotEqual(ref["file"], ref2["file"])

    def test_import_rejects_non_pictures(self):
        txt = os.path.join(self.tmp, "notes.png")
        with open(txt, "w") as f:
            f.write("not a picture")
        for bad in (txt, os.path.join(self.tmp, "missing.png"), self.tmp):
            with self.assertRaises(ValueError):
                self.store.import_file(bad)

    def test_import_without_extension_uses_format(self):
        noext = os.path.join(self.tmp, "picture")
        make_image(noext, fmt="PNG")
        ref = self.store.import_file(noext)
        self.assertTrue(ref["file"].endswith(".png"), ref)

    def test_import_qimage(self):
        img = QImage(10, 10, QImage.Format.Format_ARGB32)
        img.fill(QColor("#00ff00"))
        ref = self.store.import_image(img, "clip.png")
        self.assertEqual(ref["name"], "clip.png")
        self.assertFalse(QImage(self.store.abs_path(ref["file"])).isNull())
        with self.assertRaises(ValueError):
            self.store.import_image(QImage())

    def test_save_moves_staged_pictures_and_writes_db(self):
        ref = self.store.import_file(self.png)
        d = idt.ItemDetails([ref], "18 V", "corded")
        self.store.save(self.tree, [(self.key(), d)], {ref["file"]})
        folder = self.tree + ".items"
        self.assertTrue(os.path.isfile(os.path.join(folder, "images", ref["file"])))
        with open(os.path.join(folder, "items.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["file"], "garage.txt")
        self.assertEqual(idt.parse_db(data), [(self.key(), d)])
        self.assertEqual(self.store.abs_path(ref["file"]),
                         os.path.join(folder, "images", ref["file"]))
        # reopen
        other = idt.ItemStore()
        self.assertEqual(other.open(self.tree), [(self.key(), d)])
        self.assertIsNone(other.load_error)
        self.assertTrue(os.path.isfile(other.abs_path(ref["file"])))

    def test_no_temp_files_left_and_no_folder_for_empty_tree(self):
        self.store.save(self.tree, [], set())
        self.assertFalse(os.path.exists(self.tree + ".items"), "nothing to store, no folder")
        ref = self.store.import_file(self.png)
        self.store.save(self.tree, [(self.key(), idt.ItemDetails([ref]))], {ref["file"]})
        leftovers = [f for f in os.listdir(self.tree + ".items") if f.endswith(".tmp")]
        self.assertEqual(leftovers, [])
        # everything removed again -> folder disappears
        self.store.save(self.tree, [], set())
        self.assertFalse(os.path.exists(self.tree + ".items"))

    def test_garbage_collection_keeps_referenced_pictures(self):
        r1, r2, r3 = (self.store.import_file(self.png) for _ in range(3))
        d = idt.ItemDetails([r1, r2])
        self.store.save(self.tree, [(self.key(), d)], {r1["file"], r2["file"], r3["file"]})
        imgs = os.path.join(self.tree + ".items", "images")
        self.assertEqual(len(os.listdir(imgs)), 3, "r3 kept: an Undo may bring it back")
        self.store.save(self.tree, [(self.key(), idt.ItemDetails([r1]))], {r1["file"]})
        self.assertEqual(os.listdir(imgs), [r1["file"]])
        # foreign files of the user are not ours to delete if they don't look like ours
        with open(os.path.join(imgs, ".DS_Store"), "w") as f:
            f.write("x")
        self.store.save(self.tree, [(self.key(), idt.ItemDetails([r1]))], {r1["file"]})
        self.assertIn(".DS_Store", os.listdir(imgs))

    def test_save_as_copies_pictures_and_keeps_the_original_folder(self):
        ref = self.store.import_file(self.png)
        d = idt.ItemDetails([ref], "m")
        self.store.save(self.tree, [(self.key(), d)], {ref["file"]})
        new_tree = os.path.join(self.tmp, "sub dir", "copy ünï.txt")
        os.makedirs(os.path.dirname(new_tree))
        self.store.save(new_tree, [(self.key(), d)], {ref["file"]})
        for t in (self.tree, new_tree):
            self.assertTrue(os.path.isfile(os.path.join(t + ".items", "images", ref["file"])), t)
            self.assertTrue(os.path.isfile(os.path.join(t + ".items", "items.json")), t)
        self.assertEqual(self.store.folder, os.path.abspath(new_tree) + ".items")

    def test_missing_picture_keeps_its_reference(self):
        d = idt.ItemDetails([{"file": "gone1234.png", "name": "gone.png"}], "m")
        self.store.save(self.tree, [(self.key(), d)], {"gone1234.png"})
        entries = idt.ItemStore().open(self.tree)
        self.assertEqual(entries[0][1].images[0]["file"], "gone1234.png")
        self.assertIsNone(self.store.abs_path("gone1234.png"))

    def test_unreadable_database_is_backed_up_and_pictures_never_deleted(self):
        ref = self.store.import_file(self.png)
        self.store.save(self.tree, [(self.key(), idt.ItemDetails([ref]))], {ref["file"]})
        db = os.path.join(self.tree + ".items", "items.json")
        with open(db, "w", encoding="utf-8") as f:
            f.write("{ broken json")
        store = idt.ItemStore()
        self.assertEqual(store.open(self.tree), [])
        self.assertTrue(store.load_error)
        store.save(self.tree, [], set())
        folder = self.tree + ".items"
        backups = [f for f in os.listdir(folder) if f.startswith("items.json.unreadable-")]
        self.assertEqual(len(backups), 1)
        self.assertTrue(os.path.isfile(os.path.join(folder, "images", ref["file"])),
                        "picture of the unreadable database must survive")
        # Later sessions still never clean up while the backup exists.
        store2 = idt.ItemStore()
        store2.open(self.tree)
        store2.save(self.tree, [], set())
        self.assertTrue(os.path.isfile(os.path.join(folder, "images", ref["file"])))

    def test_reset_and_cleanup_remove_staging(self):
        self.store.import_file(self.png)
        staging = self.store.staging_dir()
        self.assertTrue(os.path.isdir(staging))
        self.store.reset()
        self.assertFalse(os.path.exists(staging))
        self.assertIsNone(self.store.folder)

    def test_discarded_pictures_never_reach_the_tree_folder(self):
        self.store.open(self.tree)
        self.store.import_file(self.png)
        self.store.cleanup()                       # window closed without saving
        self.assertFalse(os.path.exists(self.tree + ".items"))

    def test_unsafe_names_are_never_resolved(self):
        self.store.folder = self.tmp
        self.assertIsNone(self.store.abs_path("../garage.txt"))
        self.assertIsNone(self.store.abs_path("/etc/passwd"))

    def test_load_image_and_thumbnail(self):
        img, err = idt.load_image(self.png)
        self.assertEqual((img.width(), img.height(), err), (40, 30, ""))
        img, err = idt.load_image(None)
        self.assertIsNone(img)
        self.assertIn("missing", err)
        big = make_image(os.path.join(self.tmp, "big.png"), 1600, 900)
        thumb = idt.load_thumbnail(big)
        self.assertLessEqual(max(thumb.width(), thumb.height()), idt.THUMB_SIZE)
        self.assertIsNone(idt.load_thumbnail(os.path.join(self.tmp, "missing.png")))


if __name__ == "__main__":
    unittest.main()
