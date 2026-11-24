using FlaUI.Core.Input;
using FlaUI.Core.WindowsAPI;

namespace Nodeon.SystemTests.Support;

/// <summary>
/// Turns "Alt+Shift+G", "Ctrl+Enter", "Tab" ... into real key presses.
/// Uses the numeric Windows virtual-key codes, so it does not depend on enum
/// names or on the keyboard layout (VK codes for letters are layout-independent).
/// </summary>
public static class Keys
{
    private static readonly Dictionary<string, ushort> Named = new(StringComparer.OrdinalIgnoreCase)
    {
        ["Ctrl"] = 0x11, ["Control"] = 0x11, ["Alt"] = 0x12, ["Shift"] = 0x10,
        ["Enter"] = 0x0D, ["Return"] = 0x0D, ["Tab"] = 0x09, ["Esc"] = 0x1B, ["Escape"] = 0x1B,
        ["Backspace"] = 0x08, ["Space"] = 0x20, ["PgUp"] = 0x21, ["PgDown"] = 0x22,
        ["End"] = 0x23, ["Home"] = 0x24, ["Left"] = 0x25, ["Up"] = 0x26, ["Right"] = 0x27,
        ["Down"] = 0x28, ["Insert"] = 0x2D, ["Ins"] = 0x2D, ["Delete"] = 0x2E, ["Del"] = 0x2E,
        ["."] = 0xBE, [","] = 0xBC, ["-"] = 0xBD, ["="] = 0xBB,
    };

    public static VirtualKeyShort[] Parse(string combination)
    {
        var parts = combination.Split('+', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        var keys = new List<VirtualKeyShort>();
        foreach (var part in parts)
        {
            if (Named.TryGetValue(part, out var vk)) keys.Add((VirtualKeyShort)vk);
            else if (part.Length == 1 && char.IsLetterOrDigit(part[0]))
                keys.Add((VirtualKeyShort)char.ToUpperInvariant(part[0]));      // 'A'..'Z', '0'..'9'
            else if (part.Length >= 2 && (part[0] is 'F' or 'f') && int.TryParse(part[1..], out var f) && f is >= 1 and <= 24)
                keys.Add((VirtualKeyShort)(0x70 + f - 1));                     // F1..F24
            else throw new ArgumentException($"Unknown key '{part}' in '{combination}'");
        }
        return keys.ToArray();
    }

    public static void Press(string combination, int times = 1)
    {
        var keys = Parse(combination);
        for (var i = 0; i < times; i++)
        {
            Keyboard.TypeSimultaneously(keys);
            Wait.UntilInputIsProcessed();
        }
    }
}
