using Nodeon.SystemTests.Drivers;
using Nodeon.SystemTests.Support;

namespace Nodeon.SystemTests.Steps;

/// <summary>
/// The same Gherkin sentences as features/steps/nodeon_steps.py (Behave) and
/// python/bdd_pytest/test_features.py (pytest-bdd) - here executed black-box
/// on Windows through UI Automation. Text, lines, level indicator and legend
/// are read from the window; colours from the marks file (UIA cannot read
/// text colours). Scenarios tagged @python_only need in-process access and
/// are excluded: dotnet test --filter "Category!=python_only".
/// </summary>
[Binding]
public sealed class NodeonSteps(NodeonSession session)
{
    private const string Arrow = "➡️";
    private NodeonApp App => session.App;

    private static string Doc(string text) => text.Replace("\r\n", "\n").TrimEnd('\n');

    // ------------------------------------------------------------------ Given
    [StepDefinition("Nodeon is open with the tree:")]
    public void OpenTree(string docString) => App.OpenText(Doc(docString));

    [StepDefinition("Nodeon is open with the test file {string}")]
    public void OpenTestFile(string name) => App.OpenTestFile(name);

    // ------------------------------------------------------------------- When
    [StepDefinition("I put the cursor at the end of line {int}")]
    public void CursorEnd(int line) => App.CursorEndOfLine(line);

    [StepDefinition("I put the cursor at the start of line {int}")]
    public void CursorStart(int line) => App.CursorStartOfLine(line);

    [StepDefinition("I put the cursor on {string}")]
    public void CursorOn(string text) => App.CursorOn(text);

    [StepDefinition("I select {string}")]
    public void Select(string text) => App.Select(text);

    [StepDefinition("I press {string} {int} times")]
    public void PressTimes(string keys, int times) { App.FocusEditor(); Keys.Press(keys, times); Settle(); }

    [StepDefinition("I press {string}")]
    public void Press(string keys) => PressTimes(keys, 1);

    [StepDefinition("I type {string}")]
    public void Type(string text) => App.Type(text);

    [StepDefinition("I click the toolbar button {string}")]
    public void ClickToolbar(string label) { App.ClickButton(label); Settle(); }

    [StepDefinition("I paste:")]
    public void Paste(string docString) { App.Paste(Doc(docString)); Settle(); }

    [StepDefinition("I add the colour {string} in the legend")]
    public void AddColour(string meaning) => App.AddColour(meaning);

    [StepDefinition("I save the tree")]
    public void Save() => App.Save();

    [StepDefinition("I reopen the tree")]
    public void Reopen() => App.Reopen();

    private static void Settle() => Thread.Sleep(150);   // Nodeon finishes its re-layout

    // ------------------------------------------------------------------- Then
    [StepDefinition("the tree is:")]
    public void TreeIs(string docString) => Assert.That(App.Text(), Is.EqualTo(Doc(docString)));

    [StepDefinition("line {int} is {string}")]
    public void LineIs(int n, string text)
    {
        var lines = App.Lines();
        Assert.That(lines.Length, Is.GreaterThanOrEqualTo(n), $"The tree has only {lines.Length} lines:\n{App.Text()}");
        Assert.That(lines[n - 1], Is.EqualTo(text), $"Line {n}");
    }

    [StepDefinition("the tree has {int} lines")]
    public void LineCount(int n) => Assert.That(App.Lines().Length, Is.EqualTo(n), App.Text());

    [StepDefinition("the level indicator shows {int} of {int}")]
    public void Level(int current, int maximum) => Assert.That(App.Level(), Is.EqualTo((current, maximum)));

    [StepDefinition("the name {string} is marked {string}")]
    public void NameMarked(string name, string meaning) =>
        Assert.That(MarksFile.NameMeaning(App.TreePath!, name), Is.EqualTo(meaning), $"Colour mark of '{name}'");

    [StepDefinition("the word {string} is marked {string}")]
    public void WordMarked(string word, string meaning) =>
        Assert.That(MarksFile.WordMeaning(App.TreePath!, word), Is.EqualTo(meaning), $"Colour mark of the word '{word}'");

    [StepDefinition("the legend shows {string}")]
    public void LegendShows(string meaning) => Assert.That(App.LegendShows(meaning), Is.True, $"Legend entry '{meaning}'");

    [StepDefinition("every explanation is in the same column")]
    public void SameColumn()
    {
        var columns = App.Lines().Where(l => l.Contains(Arrow)).Select(l => l.IndexOf(Arrow, StringComparison.Ordinal)).Distinct();
        Assert.That(columns.Count(), Is.EqualTo(1), App.Text());
    }

    [StepDefinition("every explanation is exactly 3 spaces after its name")]
    public void ThreeSpaces()
    {
        foreach (var line in App.Lines().Where(l => l.Contains(Arrow)))
        {
            var before = line[..line.IndexOf(Arrow, StringComparison.Ordinal)];
            if (before.Trim('│', ' ').Length == 0) continue;           // continuation line, no name
            Assert.That(before.EndsWith("   ") && !before.EndsWith("    "), Is.True, $"Not exactly 3 spaces: '{line}'");
        }
    }

    [StepDefinition("the saved file is:")]
    public void SavedFileIs(string docString) =>
        Assert.That(File.ReadAllText(App.TreePath!).Replace("\r\n", "\n"), Is.EqualTo(Doc(docString) + "\n"));

    [StepDefinition("the saved file contains the line {string}")]
    public void SavedFileContains(string line) =>
        Assert.That(File.ReadAllText(App.TreePath!).Replace("\r\n", "\n").Split('\n'), Does.Contain(line));

    [StepDefinition("the window is still open")]
    public void WindowOpen() => Assert.That(App.IsRunning, Is.True, "The Nodeon window was closed");

    // ------------------------------------------- need in-process access (Python only)
    [StepDefinition("{int} lines are visible")]
    public void VisibleLines(int n) =>
        Assert.Ignore("Folded lines are not exposed by UI Automation - checked by the Python suites (@python_only)");

    [StepDefinition("the explanation {string} has the explanation colour")]
    public void ExplanationColour(string text) =>
        Assert.Ignore("UI Automation cannot read text colours - checked by the Python suites (@python_only)");
}
