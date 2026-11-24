"""
step_impl.py - what every Gherkin step DOES, written once.

Behave (features/steps/nodeon_steps.py) and pytest-bdd
(python/bdd_pytest/test_features.py) only bind the step sentences to these
functions. The C# side (Reqnroll + FlaUI) implements the same sentences with
Windows UI Automation. Comparing the three shows the difference between the
tools while the test specification (the .feature files) stays identical.
"""
from __future__ import annotations

from nodeon_driver import ARROW, NodeonDriver

TEXT_LABEL = "Not checked yet (only mentioned)"


def _doc(text: str) -> str:
    """Gherkin doc strings arrive without the final line break."""
    return text.rstrip("\n")


# ------------------------------------------------------------------- Given
def open_tree(drv: NodeonDriver, text: str) -> None:
    drv.open_text(_doc(text))


def open_test_file(drv: NodeonDriver, name: str) -> None:
    drv.open_test_file(name)


# -------------------------------------------------------------------- When
def cursor_end_of_line(drv, n: int) -> None:
    drv.cursor_end_of_line(n)


def cursor_start_of_line(drv, n: int) -> None:
    drv.cursor_start_of_line(n)


def cursor_on(drv, text: str) -> None:
    drv.cursor_on(text)


def select(drv, text: str) -> None:
    drv.select(text)


def press(drv, keys: str, times: int = 1) -> None:
    drv.press(keys, times)


def type_text(drv, text: str) -> None:
    drv.type(text)


def click_toolbar(drv, label: str) -> None:
    drv.click_toolbar(label)


def paste(drv, text: str) -> None:
    drv.paste(_doc(text))


def add_colour(drv, meaning: str) -> None:
    drv.add_colour(meaning)


def save(drv) -> None:
    drv.press("Ctrl+S")
    drv.wait(20)


def reopen(drv) -> None:
    drv.reopen()


# -------------------------------------------------------------------- Then
def _lines_with_arrow(drv):
    return [line for line in drv.lines() if ARROW in line]


def assert_tree(drv, text: str) -> None:
    drv.settle()
    expected = _doc(text)
    assert drv.text() == expected, f"\nExpected:\n{expected}\n\nActual:\n{drv.text()}"


def assert_line(drv, n: int, text: str) -> None:
    drv.settle()
    lines = drv.lines()
    assert n <= len(lines), f"The tree has only {len(lines)} lines:\n{drv.text()}"
    assert lines[n - 1] == text, f"Line {n}: expected {text!r}, got {lines[n - 1]!r}"


def assert_line_count(drv, n: int) -> None:
    assert len(drv.lines()) == n, f"Expected {n} lines, got {len(drv.lines())}:\n{drv.text()}"


def assert_level(drv, current: int, maximum: int) -> None:
    assert drv.level() == (current, maximum), f"Level indicator shows {drv.level()}"


def assert_visible_lines(drv, n: int) -> None:
    assert drv.visible_lines() == n, f"{drv.visible_lines()} lines are visible, expected {n}"


def assert_name_marked(drv, name: str, meaning: str) -> None:
    expected = drv.meaning_colour(meaning, name)
    actual = drv.colour_of_text(name)
    assert actual == {expected}, f"{name!r} is drawn in {actual}, expected {meaning} = {expected}"


def assert_word_marked(drv, word: str, meaning: str) -> None:
    assert_name_marked(drv, word, meaning)


def assert_explanation_colour(drv, text: str) -> None:
    actual = drv.colour_of_text(text)
    assert actual == {drv.explanation_colour()}, f"{text!r} is drawn in {actual}"


def assert_legend_shows(drv, meaning: str) -> None:
    labels = [label for label, _c in drv.legend()]
    assert meaning in labels, f"Legend shows {labels}"


def assert_same_column(drv) -> None:
    cols = {line.index(ARROW) for line in _lines_with_arrow(drv)}
    assert len(cols) == 1, f"Explanations start in columns {sorted(cols)}:\n{drv.text()}"


def assert_three_spaces_after_name(drv) -> None:
    for line in _lines_with_arrow(drv):
        before = line[:line.index(ARROW)]
        if before.strip("│ "):                    # a line with a name
            assert before.endswith("   ") and not before.endswith("    "), \
                f"Not exactly 3 spaces before the explanation: {line!r}"


def assert_saved_file(drv, text: str) -> None:
    assert drv.saved_text() == _doc(text) + "\n", f"Saved file:\n{drv.saved_text()}"


def assert_saved_contains_line(drv, line: str) -> None:
    lines = drv.saved_text().split("\n")
    assert line in lines, f"{line!r} not in the saved file:\n{drv.saved_text()}"


def assert_window_open(drv) -> None:
    assert drv.win is not None and drv.win.isVisible(), "The Nodeon window was closed"


# ------------------------------------------------------------- item details
def drop_pictures(drv, n: int) -> None:
    colours = ["#d33", "#3a3", "#33d", "#aa3", "#3aa", "#a3a"]
    pics = [drv.make_picture(f"bdd {i}.png", 50 + 10 * i, 40, colours[i % 6]) for i in range(n)]
    drv.sync_panel()
    drv.drop_pictures(*pics)


def next_picture(drv) -> None:
    drv.panel.b_next.click()


def write_features(drv, which: str, text: str) -> None:
    drv.sync_panel()
    drv.type_features(which, text)


def assert_item_panel_shows(drv, name: str) -> None:
    drv.sync_panel()
    assert drv.item_title() == name, f"The item panel shows {drv.item_title()!r}"


def assert_picture_count(drv, name: str, n: int) -> None:
    drv.settle()
    got = len(drv.picture_names(name))
    assert got == n, f"{name!r} has {got} pictures, expected {n}"


def assert_counter(drv, text: str) -> None:
    assert drv.picture_counter() == text, f"Counter shows {drv.picture_counter()!r}"


def assert_features(drv, name: str, which: str, text: str) -> None:
    drv.settle()
    d = drv.item_details(name)
    got = getattr(d, which) if d else ""
    assert got == text, f"{name!r}: {which} is {got!r}, expected {text!r}"
