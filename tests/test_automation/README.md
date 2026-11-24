# Nodeon: system test and verification package

Complete, traceable verification of Nodeon 1.1.0 with the full tool stack: **Python · pytest · Behave · pytest-bdd · Playwright · C# · .NET · Gherkin · Reqnroll · FlaUI · Docker · Git · SSH · Linux · TeamCity · Azure DevOps**, plus manual testing. It is structured the way regulated IVD/medical software is verified (IEC 62304, ISO 13485).

**Start reading here:** `docs/00_Testing_Guide.md` (the whole testing cycle, the reasons for each step, and which tool does what and why).

## Layout

```
specs/                 SINGLE SOURCE OF TRUTH (edit these)
  requirements.yaml      120 requirements
  test_cases.yaml        103 test cases (steps + expected results)
  anomalies.yaml         anomalies found during testing
  test_data/             versioned test files (CRLF, BOM, Latin-1, binary …)
features/              Gherkin: run by Behave, pytest-bdd AND Reqnroll
features_web/          Gherkin for the HTML report (Playwright)
python/
  nodeon_driver.py       driver / page object (in-process)
  step_impl.py           what each Gherkin step does (shared)
  system_tests/          plain pytest system tests (90)
  bdd_pytest/            pytest-bdd bindings
  web_tests/             Playwright tests of the HTML report
dotnet/                Reqnroll + FlaUI (Windows, black-box)  → dotnet/README.md
tools/
  generate_docs.py       YAML + results → documents, HTML report, quality gate
  check_csharp_bindings.py  every Gherkin step has a C# binding
  run_all.sh / run_all.ps1  run everything (Linux/Docker | Windows)
  run_remote.sh          run on a lab machine via SSH
docs/                  00 guide, 02 test plan (hand-written); 01, 03-06 generated
reports/               results (JUnit/TRX) + traceability.html (generated)
Dockerfile, requirements-test.txt
ci/azure-pipelines.yml, ci/teamcity/settings.kts   CI pipelines
```

## Quick start

```bash
pip install -r tests/test_automation/requirements-test.txt
python -m playwright install chromium
bash tests/test_automation/tools/run_all.sh        # → RESULT: ALL GREEN
```

Open `reports/traceability.html` in a browser, and `docs/06_Test_Report.md` for the verdict.

## Changing things

* New requirement → `specs/requirements.yaml` → a test case in `specs/test_cases.yaml` → an automated test or scenario whose **name starts with the TC id** → run. The generator links everything automatically, and the quality gate fails if anything is untraced.
* Never edit the generated documents by hand.
