using Nodeon.SystemTests.Drivers;
using Nodeon.SystemTests.Support;

namespace Nodeon.SystemTests.Hooks;

[Binding]
public sealed class Hooks
{
    /// <summary>Nodeon keeps its settings in HKCU\Software\Nodeon. The tests must
    /// not change the tester's own settings: back them up once, restore at the end.</summary>
    [BeforeTestRun]
    public static void BackupSettings() => SettingsBackup.Save();

    [AfterTestRun]
    public static void RestoreSettings() => SettingsBackup.Restore();

    /// <summary>Every scenario starts like a first start: no settings, no extra colours.</summary>
    [BeforeScenario]
    public void CleanStart() => SettingsBackup.Clear();

    /// <summary>Evidence for the test report: a screenshot of every failed scenario.</summary>
    [AfterScenario(Order = 0)]
    public void ScreenshotOnFailure(ScenarioContext scenario, NodeonSession session)
    {
        if (scenario.TestError is null || !session.App.IsRunning) return;
        var folder = Directory.CreateDirectory(Path.Combine(TestContext.CurrentContext.WorkDirectory, "screenshots")).FullName;
        var name = string.Concat(scenario.ScenarioInfo.Title.Split(Path.GetInvalidFileNameChars()));
        var file = Path.Combine(folder, name + ".png");
        try
        {
            session.App.Screenshot(file);
            TestContext.AddTestAttachment(file, "Nodeon window at the failure");
        }
        catch (Exception e) { TestContext.WriteLine($"No screenshot: {e.Message}"); }
    }
}
