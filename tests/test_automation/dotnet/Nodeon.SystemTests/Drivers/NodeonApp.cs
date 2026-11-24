using System.Diagnostics;
using FlaUI.Core;
using FlaUI.Core.AutomationElements;
using FlaUI.Core.Capturing;
using FlaUI.Core.Definitions;
using FlaUI.Core.Input;
using FlaUI.Core.Tools;
using FlaUI.UIA3;
using Nodeon.SystemTests.Support;

namespace Nodeon.SystemTests.Drivers;

/// <summary>
/// Drives the real Nodeon process from the outside through Windows UI
/// Automation (UIA3) - exactly like a person: keyboard, mouse clicks, reading
/// what the window exposes. Counterpart of python/nodeon_driver.py.
///
/// Configuration (environment variables):
///   NODEON_PYTHON   python.exe to use (default "python"; do NOT use the "py" launcher,
///                   it starts a second process and the window would not be found)
///   NODEON_ROOT     project folder containing main\main.py (default: found automatically)
/// </summary>
public sealed class NodeonApp : IDisposable
{
    private static readonly TimeSpan Timeout = TimeSpan.FromSeconds(20);
    private readonly UIA3Automation _automation = new();
    private Application? _app;
    private Window? _window;

    public string WorkDir { get; }
    public string? TreePath { get; private set; }
    public static string ProjectRoot { get; } = FindProjectRoot();
    public static string TestData => Path.Combine(ProjectRoot, "test_automation", "specs", "test_data");

    public NodeonApp(string workDir) => WorkDir = workDir;

    private static string FindProjectRoot()
    {
        var env = Environment.GetEnvironmentVariable("NODEON_ROOT");
        if (!string.IsNullOrEmpty(env)) return env;
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "main", "main.py")))
            dir = dir.Parent;
        return dir?.FullName ?? throw new InvalidOperationException(
            "main\\main.py not found above the test folder - set NODEON_ROOT");
    }

    // ------------------------------------------------------------------ start / stop
    public void OpenText(string text, string name = "tree.txt")
    {
        var path = Path.Combine(WorkDir, name);
        File.WriteAllText(path, text.TrimEnd('\n', '\r') + "\n");     // UTF-8 without BOM
        DeleteMarks(path);
        Launch(path);
    }

    public void OpenTestFile(string name)
    {
        var path = Path.Combine(WorkDir, name);
        File.Copy(Path.Combine(TestData, name), path, overwrite: true);
        DeleteMarks(path);
        Launch(path);
    }

    private static void DeleteMarks(string path)
    {
        if (File.Exists(path + ".marks.json")) File.Delete(path + ".marks.json");
    }

    public void Launch(string treePath)
    {
        Close();
        TreePath = treePath;
        var python = Environment.GetEnvironmentVariable("NODEON_PYTHON") ?? "python";
        var psi = new ProcessStartInfo(python, $"\"{Path.Combine(ProjectRoot, "main", "main.py")}\" \"{treePath}\"")
        {
            WorkingDirectory = ProjectRoot,
            UseShellExecute = false,
        };
        psi.Environment["NODEON_COLORS_FILE"] = Path.Combine(WorkDir, "default_colours.json");
        _app = Application.Launch(psi);
        _window = FindWindow();
        _window.SetForeground();
        Editor.Focus();
    }

    private Window FindWindow()
    {
        try
        {
            var w = _app!.GetMainWindow(_automation, Timeout);
            if (w is not null) return w;
        }
        catch (Exception) { /* fall back to a search by title */ }
        var found = Retry.WhileNull(() => _automation.GetDesktop()
                .FindAllChildren(cf => cf.ByControlType(ControlType.Window))
                .FirstOrDefault(e => e.Name.EndsWith("Nodeon", StringComparison.Ordinal)),
            Timeout, TimeSpan.FromMilliseconds(250)).Result;
        return found?.AsWindow() ?? throw new InvalidOperationException("The Nodeon window did not appear");
    }

    public void Reopen()
    {
        var path = TreePath ?? throw new InvalidOperationException("No tree was opened");
        Launch(path);
    }

    public void Close()
    {
        if (_app is null) return;
        try
        {
            if (!_app.HasExited) _app.Close();             // normal close (saves settings)
            Retry.WhileFalse(() => _app.HasExited, TimeSpan.FromSeconds(5));
            if (!_app.HasExited) _app.Kill();
        }
        catch (Exception) { /* already gone */ }
        _app.Dispose();
        _app = null;
        _window = null;
    }

    public bool IsRunning => _app is { HasExited: false } && _window is not null && _window.IsAvailable;

    public void Screenshot(string file) => Capture.Element(Window).ToFile(file);

    public void Dispose()
    {
        Close();
        _automation.Dispose();
    }

    // ------------------------------------------------------------------ elements
    public Window Window => _window ?? throw new InvalidOperationException("Nodeon is not running");

    /// <summary>The text editor: the biggest Document / Edit element of the window.</summary>
    public AutomationElement Editor
    {
        get
        {
            var candidates = Window.FindAllDescendants(cf =>
                cf.ByControlType(ControlType.Document).Or(cf.ByControlType(ControlType.Edit)));
            return candidates.OrderByDescending(e => e.BoundingRectangle.Width * e.BoundingRectangle.Height)
                             .FirstOrDefault() ?? throw new InvalidOperationException("Editor not found");
        }
    }

    public AutomationElement Button(string name) =>
        Retry.WhileNull(() => Window.FindFirstDescendant(cf =>
                cf.ByControlType(ControlType.Button).And(cf.ByName(name))),
            TimeSpan.FromSeconds(5)).Result
        ?? throw new InvalidOperationException($"No button '{name}'");

    // ------------------------------------------------------------------ reading
    public string Text()
    {
        var editor = Editor;
        string text = editor.Patterns.Text.IsSupported
            ? editor.Patterns.Text.Pattern.DocumentRange.GetText(-1)
            : editor.Patterns.Value.Pattern.Value.Value;
        return text.Replace("\r\n", "\n").Replace('\r', '\n').Replace('\u2029', '\n').TrimEnd('\n');
    }

    public string[] Lines() => Text().Split('\n');

    /// <summary>(current, maximum) of the "Levels" spin box.</summary>
    public (int Current, int Maximum) Level()
    {
        var spin = Window.FindFirstDescendant(cf => cf.ByControlType(ControlType.Spinner))
                   ?? throw new InvalidOperationException("Levels box not found");
        var range = spin.Patterns.RangeValue.Pattern;
        return ((int)range.Value.Value, (int)range.Maximum.Value);
    }

    // ------------------------------------------------------------------ actions
    /// <summary>Like a click into the text: the editor gets the keyboard focus.</summary>
    public void FocusEditor()
    {
        Window.SetForeground();
        Editor.Focus();
        Wait.UntilInputIsProcessed();
    }

    /// <summary>Moves the cursor like a person with the keyboard (line 1-based, column 0-based).</summary>
    public void MoveCursor(int line, int column)
    {
        FocusEditor();
        Keys.Press("Ctrl+Home");
        if (line > 1) Keys.Press("Down", line - 1);
        Keys.Press("Home");
        if (column > 0) Keys.Press("Right", column);
    }

    public (int Line, int Column) Find(string text)
    {
        var lines = Lines();
        for (var i = 0; i < lines.Length; i++)
        {
            var col = lines[i].IndexOf(text, StringComparison.Ordinal);
            if (col >= 0) return (i + 1, col);
        }
        throw new AssertionException($"'{text}' not found in the tree:\n{Text()}");
    }

    public void CursorEndOfLine(int line) { MoveCursor(line, 0); Keys.Press("End"); }
    public void CursorStartOfLine(int line) => MoveCursor(line, 0);
    public void CursorOn(string text) { var (l, c) = Find(text); MoveCursor(l, c + 1); }

    public void Select(string text)
    {
        var (l, c) = Find(text);
        MoveCursor(l, c);
        Keys.Press("Shift+Right", text.Length);
    }

    public void Type(string text)
    {
        Keyboard.Type(text);
        Wait.UntilInputIsProcessed();
        Thread.Sleep(300);                            // Nodeon re-reads the text after typing
    }

    /// <summary>Mouse click (not UIA Invoke: a button that opens a modal dialog
    /// would block an Invoke call until the dialog is closed).</summary>
    public void ClickButton(string name)
    {
        Window.SetForeground();
        Button(name).Click();
        Wait.UntilInputIsProcessed();
    }

    public void Paste(string text)
    {
        var t = new Thread(() => System.Windows.Forms.Clipboard.SetText(text));
        t.SetApartmentState(ApartmentState.STA);      // the clipboard needs an STA thread
        t.Start();
        t.Join();
        FocusEditor();
        Keys.Press("Ctrl+V");
    }

    public void Save()
    {
        var before = File.GetLastWriteTimeUtc(TreePath!);
        Keys.Press("Ctrl+S");
        Retry.WhileFalse(() => File.GetLastWriteTimeUtc(TreePath!) > before, TimeSpan.FromSeconds(5));
    }

    /// <summary>Legend "+ Add colour", type the meaning, OK (suggested colour + shortcuts).</summary>
    public void AddColour(string meaning)
    {
        ClickButton("+ Add colour");
        var dialog = Retry.WhileNull(() => Window.ModalWindows.FirstOrDefault(w => w.Title == "Add colour"),
                                     Timeout).Result
                     ?? throw new InvalidOperationException("The 'Add colour' dialog did not open");
        dialog.SetForeground();
        Keys.Press("Ctrl+A");
        Keyboard.Type(meaning);
        Keys.Press("Enter");                          // OK is the default button
        Retry.WhileTrue(() => Window.ModalWindows.Any(), TimeSpan.FromSeconds(5));
    }

    public bool LegendShows(string meaning) =>
        Window.FindFirstDescendant(cf => cf.ByControlType(ControlType.Button).And(cf.ByName(meaning))) is not null;
}
