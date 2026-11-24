"""
Behave step definitions for the shared Nodeon features.

Behave finds this file because it lies in features/steps/ (Behave's fixed
convention). Each step only forwards to python/step_impl.py; the driver
lives in context.drv (created per scenario in features/environment.py).
"""
from behave import given, then, when  # type: ignore

import step_impl as s


@given('Nodeon is open with the tree:')
def given_tree(context):
    s.open_tree(context.drv, context.text)


@given('Nodeon is open with the test file "{name}"')
def given_test_file(context, name):
    s.open_test_file(context.drv, name)


@when('I put the cursor at the end of line {n:d}')
def when_cursor_end(context, n):
    s.cursor_end_of_line(context.drv, n)


@when('I put the cursor at the start of line {n:d}')
def when_cursor_start(context, n):
    s.cursor_start_of_line(context.drv, n)


@when('I put the cursor on "{text}"')
def when_cursor_on(context, text):
    s.cursor_on(context.drv, text)


@when('I select "{text}"')
def when_select(context, text):
    s.select(context.drv, text)


@when('I press "{keys}" {times:d} times')
def when_press_times(context, keys, times):
    s.press(context.drv, keys, times)


@when('I press "{keys}"')
def when_press(context, keys):
    s.press(context.drv, keys)


@when('I type "{text}"')
def when_type(context, text):
    s.type_text(context.drv, text)


@when('I click the toolbar button "{label}"')
def when_click(context, label):
    s.click_toolbar(context.drv, label)


@when('I paste:')
def when_paste(context):
    s.paste(context.drv, context.text)


@when('I add the colour "{meaning}" in the legend')
def when_add_colour(context, meaning):
    s.add_colour(context.drv, meaning)


@when('I save the tree')
def when_save(context):
    s.save(context.drv)


@when('I reopen the tree')
def when_reopen(context):
    s.reopen(context.drv)


@then('the tree is:')
def then_tree(context):
    s.assert_tree(context.drv, context.text)


@then('line {n:d} is "{text}"')
def then_line(context, n, text):
    s.assert_line(context.drv, n, text)


@then('the tree has {n:d} lines')
def then_line_count(context, n):
    s.assert_line_count(context.drv, n)


@then('the level indicator shows {current:d} of {maximum:d}')
def then_level(context, current, maximum):
    s.assert_level(context.drv, current, maximum)


@then('{n:d} lines are visible')
def then_visible(context, n):
    s.assert_visible_lines(context.drv, n)


@then('the name "{name}" is marked "{meaning}"')
def then_name_marked(context, name, meaning):
    s.assert_name_marked(context.drv, name, meaning)


@then('the word "{word}" is marked "{meaning}"')
def then_word_marked(context, word, meaning):
    s.assert_word_marked(context.drv, word, meaning)


@then('the explanation "{text}" has the explanation colour')
def then_expl_colour(context, text):
    s.assert_explanation_colour(context.drv, text)


@then('the legend shows "{meaning}"')
def then_legend(context, meaning):
    s.assert_legend_shows(context.drv, meaning)


@then('every explanation is in the same column')
def then_same_column(context):
    s.assert_same_column(context.drv)


@then('every explanation is exactly 3 spaces after its name')
def then_three_spaces(context):
    s.assert_three_spaces_after_name(context.drv)


@then('the saved file is:')
def then_saved_file(context):
    s.assert_saved_file(context.drv, context.text)


@then('the saved file contains the line "{line}"')
def then_saved_line(context, line):
    s.assert_saved_contains_line(context.drv, line)


@then('the window is still open')
def then_window_open(context):
    s.assert_window_open(context.drv)


# ------------------------------------------------------------- item details
@when('I drop {n:d} pictures onto the item panel')
def when_drop_pictures(context, n):
    s.drop_pictures(context.drv, n)


@when('I show the next picture')
def when_next_picture(context):
    s.next_picture(context.drv)


@when('I write the must-have features "{text}"')
def when_write_must(context, text):
    s.write_features(context.drv, "must", text)


@when('I write the features to avoid "{text}"')
def when_write_avoid(context, text):
    s.write_features(context.drv, "avoid", text)


@then('the item panel shows "{name}"')
def then_panel_shows(context, name):
    s.assert_item_panel_shows(context.drv, name)


@then('the item "{name}" has {n:d} pictures')
def then_picture_count(context, name, n):
    s.assert_picture_count(context.drv, name, n)


@then('the picture counter shows "{text}"')
def then_counter(context, text):
    s.assert_counter(context.drv, text)


@then('the item "{name}" must have "{text}"')
def then_must(context, name, text):
    s.assert_features(context.drv, name, "must", text)


@then('the item "{name}" avoids "{text}"')
def then_avoid(context, name, text):
    s.assert_features(context.drv, name, "avoid", text)
