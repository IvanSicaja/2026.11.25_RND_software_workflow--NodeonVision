using Microsoft.Win32;

namespace Nodeon.SystemTests.Support;

/// <summary>
/// Nodeon keeps its settings in HKCU\Software\Nodeon (Qt QSettings on Windows).
/// The tests must never change the tester's own settings (recent files, theme,
/// window size), so the key is copied away before the run and restored after it.
/// </summary>
public static class SettingsBackup
{
    private const string Key = @"Software\Nodeon";
    private const string BackupKey = @"Software\Nodeon_TestBackup";

    public static void Save()
    {
        Registry.CurrentUser.DeleteSubKeyTree(BackupKey, throwOnMissingSubKey: false);
        using var src = Registry.CurrentUser.OpenSubKey(Key);
        if (src is null) return;
        using var dst = Registry.CurrentUser.CreateSubKey(BackupKey);
        Copy(src, dst);
    }

    public static void Restore()
    {
        Registry.CurrentUser.DeleteSubKeyTree(Key, throwOnMissingSubKey: false);
        using var src = Registry.CurrentUser.OpenSubKey(BackupKey);
        if (src is null) return;                  // there were no settings before the run
        using (var dst = Registry.CurrentUser.CreateSubKey(Key)) Copy(src, dst);
        Registry.CurrentUser.DeleteSubKeyTree(BackupKey, throwOnMissingSubKey: false);
    }

    /// <summary>Start every scenario like a first start (no remembered settings).</summary>
    public static void Clear() => Registry.CurrentUser.DeleteSubKeyTree(Key, throwOnMissingSubKey: false);

    private static void Copy(RegistryKey src, RegistryKey dst)
    {
        foreach (var name in src.GetValueNames())
            dst.SetValue(name, src.GetValue(name, null, RegistryValueOptions.DoNotExpandEnvironmentNames)!,
                         src.GetValueKind(name));
        foreach (var sub in src.GetSubKeyNames())
        {
            using var s = src.OpenSubKey(sub)!;
            using var d = dst.CreateSubKey(sub);
            Copy(s, d);
        }
    }
}
