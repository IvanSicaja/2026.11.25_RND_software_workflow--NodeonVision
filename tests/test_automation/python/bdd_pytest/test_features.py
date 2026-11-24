"""
pytest-bdd step definitions for the shared Nodeon features (../../features).

Same .feature files as Behave and Reqnroll. Differences to Behave you can see
here: steps are plain pytest functions, the driver arrives as a pytest fixture
(`drv`), doc strings arrive as the `docstring` argument, and every scenario
becomes a normal pytest test (so pytest markers, -k filters, parallel runs and
JUnit XML work out of the box).
"""
from pytest_bdd import given, parsers, scenarios, then, when

import step_impl as s

scenarios("")                      # every .feature file in bdd_features_base_dir


@given("Nodeon is open with the tree:")
def _(drv, docstring):
    s.open_tree(drv, docstring)


@given(parsers.parse('Nodeon is open with the test file "{name}"'))
def _(drv, name):
    s.open_test_file(drv, name)


@when(parsers.parse("I put the cursor at the end of line {n:d}"))
def _(drv, n):
    s.cursor_end_of_line(drv, n)


@when(parsers.parse("I put the cursor at the start of line {n:d}"))
def _(drv, n):
    s.cursor_start_of_line(drv, n)


@when(parsers.parse('I put the cursor on "{text}"'))
def _(drv, text):
    s.cursor_on(drv, text)


@when(parsers.parse('I select "{text}"'))
def _(drv, text):
    s.select(drv, text)


@when(parsers.parse('I press "{keys}" {times:d} times'))
def _(drv, keys, times):
    s.press(drv, keys, times)


@when(parsers.parse('I press "{keys}"'))
def _(drv, keys):
    s.press(drv, keys)


@when(parsers.parse('I type "{text}"'))
def _(drv, text):
    s.type_text(drv, text)


@when(parsers.parse('I click the toolbar button "{label}"'))
def _(drv, label):
    s.click_toolbar(drv, label)


@when("I paste:")
def _(drv, docstring):
    s.paste(drv, docstring)


@when(parsers.parse('I add the colour "{meaning}" in the legend'))
def _(drv, meaning):
    s.add_colour(drv, meaning)


@when("I save the tree")
def _(drv):
    s.save(drv)


@when("I reopen the tree")
def _(drv):
    s.reopen(drv)


@then("the tree is:")
def _(drv, docstring):
    s.assert_tree(drv, docstring)


@then(parsers.parse('line {n:d} is "{text}"'))
def _(drv, n, text):
    s.assert_line(drv, n, text)


@then(parsers.parse("the tree has {n:d} lines"))
def _(drv, n):
    s.assert_line_count(drv, n)


@then(parsers.parse("the level indicator shows {current:d} of {maximum:d}"))
def _(drv, current, maximum):
    s.assert_level(drv, current, maximum)


@then(parsers.parse("{n:d} lines are visible"))
def _(drv, n):
    s.assert_visible_lines(drv, n)


@then(parsers.parse('the name "{name}" is marked "{meaning}"'))
def _(drv, name, meaning):
    s.assert_name_marked(drv, name, meaning)


@then(parsers.parse('the word "{word}" is marked "{meaning}"'))
def _(drv, word, meaning):
    s.assert_word_marked(drv, word, meaning)


@then(parsers.parse('the explanation "{text}" has the explanation colour'))
def _(drv, text):
    s.assert_explanation_colour(drv, text)


@then(parsers.parse('the legend shows "{meaning}"'))
def _(drv, meaning):
    s.assert_legend_shows(drv, meaning)


@then("every explanation is in the same column")
def _(drv):
    s.assert_same_column(drv)


@then("every explanation is exactly 3 spaces after its name")
def _(drv):
    s.assert_three_spaces_after_name(drv)


@then("the saved file is:")
def _(drv, docstring):
    s.assert_saved_file(drv, docstring)


@then(parsers.parse('the saved file contains the line "{line}"'))
def _(drv, line):
    s.assert_saved_contains_line(drv, line)


@then("the window is still open")
def _(drv):
    s.assert_window_open(drv)


# ------------------------------------------------------------- item details
@when(parsers.parse("I drop {n:d} pictures onto the item panel"))
def _(drv, n):
    s.drop_pictures(drv, n)


@when("I show the next picture")
def _(drv):
    s.next_picture(drv)


@when(parsers.parse('I write the must-have features "{text}"'))
def _(drv, text):
    s.write_features(drv, "must", text)


@when(parsers.parse('I write the features to avoid "{text}"'))
def _(drv, text):
    s.write_features(drv, "avoid", text)


@then(parsers.parse('the item panel shows "{name}"'))
def _(drv, name):
    s.assert_item_panel_shows(drv, name)


@then(parsers.parse('the item "{name}" has {n:d} pictures'))
def _(drv, name, n):
    s.assert_picture_count(drv, name, n)


@then(parsers.parse('the picture counter shows "{text}"'))
def _(drv, text):
    s.assert_counter(drv, text)


@then(parsers.parse('the item "{name}" must have "{text}"'))
def _(drv, name, text):
    s.assert_features(drv, name, "must", text)


@then(parsers.parse('the item "{name}" avoids "{text}"'))
def _(drv, name, text):
    s.assert_features(drv, name, "avoid", text)
