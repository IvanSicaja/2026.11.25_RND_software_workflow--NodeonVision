"""
pytest system tests - start-up, files and the tree format.

Every test is named test_TC_<AREA>_<NNN>_... so the report generator links it
to its test case (and through it to the requirements). The `req` marker
repeats the requirement ids for people reading the code and for `-m` filters.

pytest strengths shown here: fixtures (drv, tmp_path), parametrize (one test,
many data sets), skipif (platform), markers.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from nodeon_driver import ARROW, MAIN_PY, PROJECT_ROOT, TEST_DATA, app_module

LINUX = sys.platform.startswith("linux")


def _launch(args, cwd, tmp_path, seconds=4):
    """Start Nodeon as its own process; still running after `seconds` = started OK."""
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", HOME=str(tmp_path),
               XDG_CONFIG_HOME=str(tmp_path / "config"),
               NODEON_COLORS_FILE=str(tmp_path / "colours.json"))
    proc = subprocess.Popen([sys.executable, *args], cwd=cwd, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        out, _ = proc.communicate(timeout=seconds)
        return proc.returncode, out
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate()
        return None, out                       # None = was still running


# ----------------------------------------------------------------------- GEN
@pytest.mark.req("REQ-GEN-001", "REQ-GEN-006")
def test_TC_GEN_001_start_without_and_with_a_file(drv):
    drv.new_window()
    assert drv.win.windowTitle() == "Untitled[*] — Nodeon"
    assert drv.text().startswith("new-project/")
    drv.open_test_file("tree_a.txt")
    assert drv.win.windowTitle() == "tree_a.txt[*] — Nodeon"
    assert len(drv.lines()) == 8


@pytest.mark.skipif(not LINUX, reason="starts a real process with throw-away settings (Linux only)")
@pytest.mark.req("REQ-GEN-001", "REQ-GEN-002")
@pytest.mark.parametrize("cwd, script", [(PROJECT_ROOT, "main/main.py"),
                                         (PROJECT_ROOT / "main", "main.py")])
def test_TC_GEN_002_starts_from_project_root_and_from_main(tmp_path, cwd, script):
    code, out = _launch([script, str(TEST_DATA / "tree_a.txt")], cwd, tmp_path)
    assert code is None, f"Nodeon stopped (exit {code}):\n{out}"
    assert "Traceback" not in out


@pytest.mark.skipif(not LINUX, reason="starts a real process with throw-away settings (Linux only)")
@pytest.mark.req("REQ-GEN-003")
def test_TC_GEN_002_wrong_model_file_gives_clear_message(tmp_path):
    app = tmp_path / "app" / "main"
    app.mkdir(parents=True)
    (app / "main.py").write_bytes(MAIN_PY.read_bytes())
    (app / "treemodel.py").write_text("x = 1\n", encoding="utf-8")
    code, out = _launch([str(app / "main.py")], tmp_path, tmp_path)
    # The message is printed and shown in a window that waits for "OK"
    # (after OK Nodeon ends with exit code 1) - no crash, no traceback.
    assert code in (None, 1), out
    assert "not Nodeon's file" in out and "FormatOptions" in out
    assert "Traceback" not in out


@pytest.mark.req("REQ-GEN-004")
def test_TC_GEN_003_old_tree_editor_settings_are_taken_over(tmp_path, monkeypatch):
    m = app_module()

    def per_app(org, app):
        return QSettings(str(tmp_path / f"{org}-{app}.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(m, "QSettings", per_app)
    old = per_app("TreeEditor", "TreeEditor")
    old.setValue("font_size", 15.0)
    old.setValue("dark", True)
    old.sync()
    new = per_app("Nodeon", "Nodeon")
    m._migrate_old_settings(new)
    assert float(new.value("font_size")) == 15.0
    assert new.value("dark", type=bool) is True


@pytest.mark.req("REQ-GEN-005")
def test_TC_GEN_004_first_start_full_height_half_width(drv):
    drv.new_window()
    drv.wait(100)
    avail = QApplication.primaryScreen().availableGeometry()
    frame = drv.win.frameGeometry()
    assert abs(frame.height() - avail.height()) <= 2
    assert abs(frame.width() - avail.width() // 2) <= 2


# ----------------------------------------------------------------------- FMT
@pytest.mark.req("REQ-FMT-001", "REQ-FMT-002", "REQ-FMT-003", "REQ-FMT-007")
@pytest.mark.parametrize("name", ["tree_a.txt", "tree_b_example_project.txt"])
def test_TC_FMT_001_open_and_save_is_byte_identical(drv, name):
    drv.open_test_file(name)
    drv.press("Ctrl+S")
    assert drv.path.read_bytes() == (TEST_DATA / name).read_bytes()


@pytest.mark.req("REQ-FMT-008")
@pytest.mark.parametrize("source, expected", [
    pytest.param("p\n|-- a\n|   `-- b\n`-- c", "p\n├── a\n│   └── b\n└── c", id="ascii"),
    pytest.param("p\n\ta\n\t\tb\n\tc", "p\n├── a\n│   └── b\n└── c", id="tabs"),
    pytest.param("p\n├──\xa0a\n└──\xa0b", "p\n├── a\n└── b", id="nbsp"),
    pytest.param("p\n    a\n        b\n    c", "p\n├── a\n│   └── b\n└── c", id="indented"),
])
def test_TC_FMT_005_other_tree_styles_are_read(drv, source, expected):
    drv.open_text(source)
    drv.press("Ctrl+Alt+L")
    assert drv.text() == expected


@pytest.mark.req("REQ-FMT-009")
@pytest.mark.parametrize("name", ["tree_a.txt", "tree_b_example_project.txt", "tree_c_ascii.txt"])
def test_TC_FMT_006_format_document_is_idempotent(drv, name):
    drv.open_test_file(name)
    drv.press("Alt+Right", 3)
    drv.press("Ctrl+Alt+L")
    once = drv.text()
    drv.press("Ctrl+Alt+L")
    assert drv.text() == once
    for line in once.split("\n"):
        if ARROW in line and line[:line.index(ARROW)].strip("│ "):
            assert line.index(ARROW) >= 34


@pytest.mark.req("REQ-FMT-010")
def test_TC_FMT_007_text_above_the_tree_is_kept(drv):
    source = f"{ARROW} notes about this tree\nroot/\n└── a"
    drv.open_text(source)
    drv.press("Ctrl+S")
    assert drv.saved_text() == source + "\n"


# ---------------------------------------------------------------------- FILE
@pytest.mark.req("REQ-FILE-001", "REQ-FILE-006")
def test_TC_FILE_001_open_by_drop_and_recent_list(drv):
    drv.open_test_file("tree_a.txt")
    other = drv.workdir / "tree_b.txt"
    other.write_bytes((TEST_DATA / "tree_b_example_project.txt").read_bytes())
    drv.editor.openFileRequested.emit(str(other))          # what a drop does
    assert drv.win.windowTitle().startswith("tree_b.txt")
    recent = [a.text() for a in drv.win.recent_menu.actions()]
    assert recent[:2] == [str(other), str(drv.workdir / "tree_a.txt")]
    drv.win.recent_menu.actions()[1].trigger()             # back via Open recent
    assert drv.win.windowTitle().startswith("tree_a.txt")


@pytest.mark.req("REQ-FILE-002", "REQ-FMT-001")
def test_TC_FILE_002_save_writes_file_and_reports_errors(drv):
    drv.open_test_file("tree_a.txt")
    drv.cursor_end_of_line(8)
    drv.press("Ctrl+Enter")
    drv.type("LICENSE")
    drv.press("Ctrl+S")
    assert drv.saved_text().endswith("└── LICENSE\n")
    assert not drv.editor.document().isModified()
    # fault injection: the folder does not exist -> clear error, nothing written
    drv.win.path = str(drv.workdir / "missing-folder" / "tree.txt")
    drv.type("X")
    assert drv.win.save() is False
    assert any("Could not save" in text for kind, text in drv.messages if kind == "critical")
    assert not (drv.workdir / "missing-folder").exists()


@pytest.mark.req("REQ-FILE-003")
def test_TC_FILE_003_crlf_and_bom(drv):
    drv.open_test_file("tree_d_crlf.txt")
    drv.cursor_end_of_line(3)
    drv.type("2")
    drv.press("Ctrl+S")
    data = drv.path.read_bytes()
    assert data == "root/\r\n├── a\r\n└── b2\r\n".encode("utf-8")
    drv.open_test_file("tree_e_bom.txt")
    assert drv.lines()[0] == "root/"


@pytest.mark.req("REQ-FILE-004")
def test_TC_FILE_004_binary_refused_latin1_warned(drv):
    drv.open_test_file("tree_a.txt")
    before = drv.text()
    binary = drv.workdir / "bin.txt"
    binary.write_bytes((TEST_DATA / "tree_f_binary.txt").read_bytes())
    assert drv.win.load_file(str(binary)) is False
    assert any("does not look like a text file" in t for k, t in drv.messages)
    assert drv.text() == before
    latin = drv.workdir / "latin.txt"
    latin.write_bytes((TEST_DATA / "tree_g_latin1.txt").read_bytes())
    assert drv.win.load_file(str(latin)) is True
    assert any("not valid UTF-8" in t for k, t in drv.messages if k == "warning")
    assert "�" in drv.text()


@pytest.mark.req("REQ-FILE-005")
def test_TC_FILE_005_unsaved_changes_cancel_discard_save(drv):
    path = drv.open_test_file("tree_a.txt")
    original = path.read_text(encoding="utf-8")
    drv.cursor_end_of_line(8)
    drv.type("X")
    assert drv.win.isWindowModified()
    drv.answers = ["Cancel"]
    drv.win.new_file()
    assert drv.text().endswith("OverviewX")                # change still there
    drv.answers = ["Discard"]
    drv.win.new_file()
    assert drv.text().startswith("new-project/")
    assert path.read_text(encoding="utf-8") == original
    drv.open_file(path)
    drv.cursor_end_of_line(8)
    drv.type("Y")
    drv.answers = ["Save"]
    drv.win.close()                                       # the real close button path
    assert path.read_text(encoding="utf-8").rstrip("\n").endswith("OverviewY")
    drv.win = None


@pytest.mark.req("REQ-FILE-006")
def test_TC_FILE_006_recent_files_keeps_last_ten(drv):
    drv.new_window()
    paths = []
    for i in range(11):
        p = drv.workdir / f"t{i}.txt"
        p.write_text(f"root{i}/\n└── a\n", encoding="utf-8")
        assert drv.win.load_file(str(p))
        paths.append(str(p))
    recent = [a.text() for a in drv.win.recent_menu.actions()]
    assert recent == list(reversed(paths))[:10]
