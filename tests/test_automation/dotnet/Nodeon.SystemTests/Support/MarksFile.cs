using System.Text.Json;

namespace Nodeon.SystemTests.Support;

/// <summary>
/// Reads "&lt;tree&gt;.txt.marks.json" - the file Nodeon writes as soon as a colour
/// is set. UI Automation cannot tell the colour of text reliably, so the
/// Windows tests check the stored colour mark instead (black-box: the file
/// is a product output). The Python tests check the drawn colour.
/// </summary>
public static class MarksFile
{
    public const string TextLabel = "Not checked yet (only mentioned)";

    private static JsonDocument? Load(string treePath)
    {
        var path = treePath + ".marks.json";
        return File.Exists(path) ? JsonDocument.Parse(File.ReadAllText(path)) : null;
    }

    private static string LabelOf(JsonDocument doc, string key)
    {
        if (key == "default") return TextLabel;               // "back to text colour"
        foreach (var c in doc.RootElement.GetProperty("legend").GetProperty("colours").EnumerateArray())
            if (c.GetProperty("key").GetString() == key) return c.GetProperty("label").GetString()!;
        return key;
    }

    /// <summary>Meaning of the whole-name colour of a branch (default: the text label).</summary>
    public static string NameMeaning(string treePath, string name)
    {
        using var doc = Load(treePath);
        if (doc is null) return TextLabel;
        foreach (var m in doc.RootElement.GetProperty("marks").EnumerateArray())
        {
            var path = m.GetProperty("path");
            var last = path[path.GetArrayLength() - 1];
            if (last[0].GetString() == name) return LabelOf(doc, m.GetProperty("mark").GetString()!);
        }
        return TextLabel;
    }

    /// <summary>Meaning of a coloured word (default: the text label).</summary>
    public static string WordMeaning(string treePath, string word)
    {
        using var doc = Load(treePath);
        if (doc is null) return TextLabel;
        foreach (var w in doc.RootElement.GetProperty("words").EnumerateArray())
            if (w.GetProperty("text").GetString() == word && w.GetProperty("part").GetString() == "name")
                return LabelOf(doc, w.GetProperty("mark").GetString()!);
        return TextLabel;
    }
}
