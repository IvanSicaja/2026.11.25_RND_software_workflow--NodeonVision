namespace Nodeon.SystemTests.Drivers;

/// <summary>
/// One per scenario (Reqnroll context injection creates it and disposes it at the
/// end of the scenario): a fresh temporary folder and one Nodeon process.
/// </summary>
public sealed class NodeonSession : IDisposable
{
    public string WorkDir { get; } =
        Directory.CreateDirectory(Path.Combine(Path.GetTempPath(), "nodeon-tests", Guid.NewGuid().ToString("N"))).FullName;

    private NodeonApp? _app;
    public NodeonApp App => _app ??= new NodeonApp(WorkDir);

    public void Dispose()
    {
        _app?.Dispose();
        try { Directory.Delete(WorkDir, recursive: true); } catch (IOException) { /* file still locked: leave it */ }
    }
}
