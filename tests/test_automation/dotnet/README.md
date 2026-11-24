# Nodeon Windows system tests: Reqnroll + FlaUI (C#)

The **same Gherkin files** (`../features/*.feature`) that Behave and pytest-bdd run, executed **black-box on Windows**. FlaUI starts the real `python main/main.py`, finds the window through Microsoft UI Automation and uses the real keyboard and mouse.

## Requirements

* Windows 10/11, **interactive desktop session** (not a service, not a locked screen)
* .NET 8 SDK
* Python 3.10+ with `pip install -r ../../../draft_requirements_python-3.11.9.txt` (PySide6). `python.exe` must be on PATH, or set `NODEON_PYTHON` to the full path of `python.exe`. Do not use the `py` launcher: it starts a second process and the window would not be found.

## Run

```powershell
cd test_automation
dotnet test dotnet\Nodeon.SystemTests --filter "Category!=python_only" `
  --logger "trx;LogFileName=reqnroll.trx" --results-directory reports\reqnroll
python tools\generate_docs.py           # picks up reports\reqnroll\*.trx
```

Do not touch the mouse or keyboard while the tests run. Screenshots of failed scenarios are attached to the TRX.

## Structure

| File | Role |
|---|---|
| `Steps/NodeonSteps.cs` | Gherkin sentence → action/assertion (counterpart of `features/steps/nodeon_steps.py`) |
| `Drivers/NodeonApp.cs` | Driver: start/stop, find editor, cursor, typing, toolbar, legend, save, read text (counterpart of `python/nodeon_driver.py`) |
| `Drivers/NodeonSession.cs` | One temporary folder and one Nodeon process per scenario (context injection) |
| `Hooks/Hooks.cs` | Settings backup/restore (HKCU\Software\Nodeon), clean start, screenshot on failure |
| `Support/Keys.cs` | "Alt+Shift+G" → virtual-key codes (keyboard-layout independent) |
| `Support/MarksFile.cs` | Colour checks via `<tree>.txt.marks.json` (UIA cannot read text colours) |

## Known limits (by design)

* `@python_only` scenarios (hidden/folded line counts, drawn colours) need in-process access and are excluded by the filter.
* **Not yet executed:** this project was written and statically checked (C# syntax, and every step has exactly one binding: `python tools/check_csharp_bindings.py`) in an environment without .NET or Windows. Treat the first Windows run as a dry run. Typical adjustments are UIA control names or types (check with *Accessibility Insights for Windows* or FlaUInspect) and settle times.
