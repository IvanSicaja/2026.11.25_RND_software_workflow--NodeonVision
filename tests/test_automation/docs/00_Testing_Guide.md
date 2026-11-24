# Software Testing Guide: from requirement to release

**Product used as the example:** Nodeon 1.1.0 (desktop tree editor, Python/PySide6)
**Context:** how system testing and test automation are done for regulated products such as IVD instrument software and lab automation (Hamilton, Roche Diagnostics, Switzerland/EU/US).
**Document:** GUIDE-NODEON-000. Written by hand; everything in `docs/01…06` is generated.

> **How to read this.** Chapters 1–3 explain *why*, chapters 4–7 explain *what* is done, chapters 8–12 explain *with which tool, and why that tool and not another one*. Chapter 13 has the commands, and chapter 14 the expert checklist.
> Statements marked **(verify)** are regulatory or pricing facts that change over time. Check them against the official source before you rely on them.

---

## 0 The whole workflow on one page

```
 Intended use / user needs ─────────────────────────────── VALIDATION ── "right product?"
        │                                                       ▲
        ▼                                                       │
 Software requirements (SRS)  specs/requirements.yaml ─── SYSTEM TEST ── "built right?"
        │   + risk analysis (ISO 14971)                         ▲   (= VERIFICATION)
        ▼                                                       │
 Architecture / design  ──────────────────────────── INTEGRATION TEST
        │                                                       ▲
        ▼                                                       │
 Code (units) ────────────────────────────────────────── UNIT TEST (developers)

 Every arrow on the right side leaves EVIDENCE: test spec → executed results →
 traceability matrix → test report → release decision.
```

The cycle in this repository, one step per box:

| # | Step | Output in this repo | Who | Automated? |
|---|------|---------------------|-----|-----------|
| 1 | Plan the testing | `docs/02_Test_Plan.md` | Test lead | – |
| 2 | Write testable requirements | `specs/requirements.yaml` → `docs/01_SRS.md` | Req. engineer + tester (review) | Generated |
| 3 | Analyse risk, set priorities | `priority` per requirement, risk table in the test plan | Team | – |
| 4 | Design test cases | `specs/test_cases.yaml` → `docs/03_Test_Specification.md` | Tester | Generated |
| 5 | Automate | `features/`, `python/`, `dotnet/` | Test automation engineer | – |
| 6 | Execute | `tools/run_all.sh` / `.ps1`, CI pipelines, manual protocol | CI + tester | Mostly |
| 7 | Log anomalies | `specs/anomalies.yaml` | Tester | – |
| 8 | Trace and gate | `docs/04_Traceability_Matrix.md`, `reports/traceability.html` | Generator | Yes |
| 9 | Report | `docs/06_Test_Report.md` | Generator + test lead signs | Yes |
| 10 | Release decision | Sign-off sheet in `05_Manual_Test_Protocol.xlsx` | QA / product owner | – |

---

## 1 Verification vs. validation

| | **Verification** | **Validation** |
|---|---|---|
| Question | *Did we build the product right?* | *Did we build the right product?* |
| Compared against | Requirements and specifications (SRS, design) | User needs and the intended use, in the real use environment |
| Typical evidence | Reviews, unit, integration and **system tests**, static analysis | Usability (summative) evaluation, clinical/performance evaluation, beta use in a lab, acceptance tests with real users |
| Who | Development and the test team | Intended users and application specialists, often independent of development |
| Standard reference | ISO 13485 7.3.6, IEC 62304 5.5–5.7 | ISO 13485 7.3.7, IEC 62366-1 (usability), IVDR performance evaluation |
| In this repo | Everything automated, plus manual TCs against the SRS | Not done here. It would be, for example, a real user structuring a real project tree without instructions while we watch where they fail (TC-UI-008 is a small manual step in that direction) |

**Why both?** A product can pass every verification test and still be useless. For example, the requirement "Alt+5 folds to level 5" is met, but users never find the shortcut. Validation catches wrong requirements. Verification catches wrong implementation.

**A trap in interviews:** "system testing = validation" is **wrong**. System testing against the SRS is verification. It only becomes validation evidence when it tests against user needs in the intended use environment with representative users.

There is a third, separate thing: **tool validation** (ISO 13485 4.1.6, computerised-system validation). Software used *inside the quality system*, such as our report generator and the test frameworks, must be shown to work for its intended use. That is why Playwright tests the HTML traceability report here (chapter 9.6), and why tool versions are pinned (`requirements-test.txt`).

---

## 2 Why regulated testing is different

In an unregulated company a test that passed is enough. In medical devices and IVD, **if it is not documented, it was not done**. An auditor (notified body, Swissmedic, FDA) asks for evidence that is:

1. **Planned:** a test plan exists *before* execution, with entry and exit criteria.
2. **Traceable:** each requirement → test case(s) → result → software version (commit). Each risk control → test.
3. **Reproducible:** same version, same environment, same result. Hence Docker, pinned tools, and a commit id in the report.
4. **Attributable:** who executed it, when, and on what version (the signature fields in the protocol; 21 CFR Part 11 if electronic signatures are used).
5. **Complete:** failures are not deleted but logged as anomalies, evaluated (risk) and closed (fixed, or accepted with a justification).
6. **Controlled:** documents have ids and versions, and changes trigger a regression analysis.

### Regulatory map (short; **verify** current versions)

| Topic | EU | Switzerland | USA |
|---|---|---|---|
| Device law (IVD) | IVDR (EU) 2017/746 – Annex I §16 covers software | IvDO (SR 812.219), aligned with IVDR. Swissmedic applies the extended IVDR transition (Reg. (EU) 2024/1860) **(verify)** | 21 CFR 809 (IVD) |
| Quality system | ISO 13485:2016 (harmonised) | ISO 13485:2016 | QMSR (21 CFR 820, now incorporating ISO 13485, in force since 2 Feb 2026 **(verify)**) |
| Software life cycle | IEC 62304 (+A1) | IEC 62304 | IEC 62304 recognised standard; FDA guidance "Content of Premarket Submissions for Device Software Functions" |
| Risk | ISO 14971 | ISO 14971 | ISO 14971 recognised |
| Usability (validation) | IEC 62366-1 | IEC 62366-1 | FDA human-factors guidance |
| Cybersecurity | IEC 81001-5-1, MDCG guidance | same | FDA premarket cybersecurity guidance |
| Electronic records | (Annex 11 is pharma GMP) | – | 21 CFR Part 11 |
| Tools in the QMS | ISO 13485 4.1.6 | same | Computer Software Assurance (CSA) guidance, risk-based **(verify status)** |

**IEC 62304 in one table.** This is the core standard for a software tester.

| Clause | Content | Where in this repo |
|---|---|---|
| 4.3 | Software safety class A / B / C (by possible harm) | Test plan §2 (Nodeon is not a medical device; we test it *as if* it were class B) |
| 5.1 | Development plan, incl. verification planning and tool/configuration items | Test plan, `requirements-test.txt` |
| 5.2 | Software requirements: testable, uniquely identified | `requirements.yaml` (each one has `acceptance`) |
| 5.5 | Unit implementation and verification (B, C) | `../test_*.py` developer suites (173 tests) |
| 5.6 | Integration and integration testing | Driver-level system tests; GUI tests in `../test_gui.py` |
| 5.7 | **Software system testing**: tests for every requirement, anomalies evaluated, results recorded with version, environment and tester | **This test_automation project** |
| 5.8 | Release: known residual anomalies documented | Test report chapter 4, `anomalies.yaml` |
| 6 | Maintenance: changes → impact analysis → regression | Chapter 7.4 |
| 8 | Configuration management | Git, tags, commit id in reports |
| 9 | Problem resolution | Anomaly workflow, chapter 7 |

---

## 3 Test levels and types

| Level | Tests what | Black/white box | Here | Tool |
|---|---|---|---|---|
| Unit | One function or class, isolated | White | `tests/test_treemodel.py` | pytest/unittest |
| Integration | Units together, e.g. model + editor widget | Grey | `tests/test_gui.py` | pytest + Qt |
| **System** | The complete product through its user interface against the SRS | Black (Python driver: grey) | `tests/test_automation/` | pytest, pytest-bdd, Behave, Reqnroll+FlaUI |
| Acceptance / validation | Intended use with real users | Black | not in scope | Manual |

**Types across levels:** functional, regression, smoke (`-m` markers / tag filters), negative and robustness (binary file, missing folder, wrong model file), fault injection (save into a missing folder, simulated exception), configuration (Windows/Linux, dark/light theme), data integrity (byte-identical round trip, CRLF/BOM), usability (manual), performance (not required by the SRS, so not tested; an expert says this explicitly rather than silently skipping it).

**Why system tests if the unit tests already pass?** Units can be correct and the product still wrong: wrong shortcut wiring, focus problems, file encoding at the boundary. ANOMALY-001 (keyboard focus after a dialog) is invisible to every unit test and was found only by a system test that used the real dialog.

**Why not *only* system tests?** They are slow (seconds instead of milliseconds) and a failure says *that* something broke, not *where*. This is the test pyramid: many fast unit tests, fewer system tests, very few manual tests.

---

## 4 Requirements: the base of everything

A requirement is only useful for testing if it is:

* **Atomic** – one statement, one verdict.
* **Unambiguous** – no "fast", "user-friendly" or "etc."
* **Verifiable** – it has an acceptance criterion. In `requirements.yaml` every requirement has `acceptance:`, which is the oracle for the tester.
* **Identified** – a permanent id (`REQ-FOLD-003`). Ids are never reused.
* **Traceable to its source** – `source:` says where it came from (here: which user request in the project history).

**The tester's job starts here, not after coding.** Review requirements for testability. Two examples from this project:

* *"Ctrl+D duplicates the line"* – does that include the empty spacer line above it? The test found it does (ANOMALY-002). That is a requirement clarification, not a code bug.
* *"Explanations are aligned"* – aligned to what? We made it measurable: "the same column, at least column 34, exactly 3 spaces after the longest name".

---

## 5 Test design techniques (what an expert applies)

| Technique | Idea | Example in this repo |
|---|---|---|
| Equivalence partitioning | One test per class of inputs that behaves the same | Tree styles: ASCII / tabs / NBSP / indented (`TC_FMT_005`, parametrised) |
| Boundary value analysis | Test at the edges | Zoom lower limit 6 pt; recent files: 10 kept, the 11th drops out; minimum column 34/40 |
| Decision table | Combinations of conditions | Unsaved changes × Cancel / Discard / Save (`TC_FILE_005`) |
| State transition | States and events | Folding levels 0..3 with Alt+1..5, collapse/expand level |
| Use-case / scenario | End-to-end user flows | Gherkin scenarios in `features/` |
| Error guessing / fault injection | Where it usually breaks | Binary file, Latin-1 file, missing folder, simulated crash, wrong module next to `main.py` |
| Invariants / property checks | Something must always hold | `SAFE-002`: after every edit operation the tree is still valid and nothing is lost (parametrised over all operations) |
| Round trip | Write → read → identical | Open + save is byte-identical (`TC_FMT_001`) |
| Exploratory (session-based) | Timeboxed, charter-driven, documented | It found both anomalies; record sessions in the protocol |
| Risk-based prioritisation | Test most where failure hurts most | `priority` field; high = data loss and file integrity |

---

## 6 Test case anatomy

Each test case in `specs/test_cases.yaml` has the parts an auditor expects:

```
id: TC-FOLD-003                      permanent id
title: Fold to a chosen level        what it is about
reqs: [REQ-FOLD-003]                 trace upward
level: system   technique: state transition   priority: high
preconditions: test file tree_b ...  defined start state + test data
steps:                               action + EXPECTED result per step
  - [Press Alt+2, Level indicator shows "2 of 3"; only levels 1-2 visible]
automated: [gui: GuiTests::test_...] optional explicit links to developer tests
```

**Every automated test case is also a manual test case.** The steps are written for a human, and `05_Manual_Test_Protocol.xlsx` is generated from the same YAML. This is required because:

1. An automated test can itself be wrong. A manual dry run validates the automation once.
2. The CI or the lab automation may be down before a release.
3. Some checks cannot be automated sensibly, for example "is it readable and pleasant?" (TC-UI-008).

---

## 7 Anomalies, defects and regression

### 7.1 Life cycle (IEC 62304 §9)

```
 New ─► Analysed (reproducible? risk? which requirement?) ─► Decision:
          ├─ Fix ─► Fixed in build X ─► Verified (re-test + regression) ─► Closed
          ├─ Requirement unclear ─► clarify SRS ─► re-test
          └─ Accept (justified residual anomaly, risk acceptable) ─► listed in release notes
```

### 7.2 A good anomaly report

It has a title, steps to reproduce, expected vs. actual, software version (commit), environment, severity, **risk assessment** (can it cause harm? for IVD: a wrong result, a delayed result, data loss), evidence (log, screenshot; the Windows suite takes a screenshot on every failure), linked requirement or TC, and status. See `specs/anomalies.yaml`.

### 7.3 Severity ≠ priority

Severity is how bad the effect is. Priority is how soon it is fixed. A typo on the start screen has low severity but can be high priority before a trade show.

### 7.4 Regression after a change

1. Impact analysis: which requirements and areas are touched?
2. Run the impacted TCs plus the automated full regression. Automation makes the full run cheap, which is the main business case for it.
3. Re-run manual TCs only where they are affected, and document why the others were not re-run.

---

## 8 Traceability and the quality gate

```
REQ-FOLD-003 ──► TC-FOLD-003 ──► pytest-bdd: "TC-FOLD-003 ..."   passed
                               ├► Behave:    "TC-FOLD-003 ..."   passed
                               └► Reqnroll:  TC_FOLD_003...      (Windows)
```

* **Forward** (requirement → tests) proves *completeness*: nothing was left untested.
* **Backward** (test → requirement) proves *no gold-plating*: every test has a reason.
* Links are made **automatically by naming**: a test or scenario name that contains the TC id is linked. There is no manual matrix in Excel that goes stale.
* `tools/generate_docs.py --require-pass` is the **quality gate**. It fails (exit 1) on duplicate ids, unknown requirements, untested requirements, broken references or any failed test. CI uses it as the release blocker.

**Why docs-as-code (YAML + generator) instead of Word plus a test management tool?** The requirements, the tests and the evidence live in Git next to the code. That gives one version, one review (pull request) and a history. Tools like Polarion, Jama, Codebeamer or Azure Test Plans do the same with a UI and e-signatures. Large companies use them, and the concepts are identical.

---

## 9 The tools: what, why, and why not another one

### 9.1 Architecture of the automation (applies to every tool)

```
  Specification   features/*.feature  (Gherkin, readable by QA / regulatory)
        │                       Same text for 3 runners
  Step bindings   Behave · pytest-bdd · Reqnroll   ← thin: only text → call
        │
  Shared step logic  python/step_impl.py           ← what a step DOES (Python)
        │
  Driver / page object  nodeon_driver.py (in-process) · NodeonApp.cs (UI Automation)
        │
  Application under test  main/main.py  (NOT changed for testing)
```

**Why layers?** If the UI changes (a renamed button), only the driver changes, not 100 tests. If the wording of a specification changes, only the binding changes. This is the most important design idea in test automation. The same pattern is called page object (web), screen object or driver.

### 9.2 Python + pytest

* **What:** the de-facto standard Python test runner: fixtures, parametrisation, markers, plugins, JUnit XML.
* **Why here:** Nodeon is Python. pytest runs *inside* the process and can read things no outside tool can see: drawn colours, folded (hidden) lines, internal state, injected faults.
* **Why not only pytest?** The tests are code. A regulatory reviewer or product owner cannot review them. That is what Gherkin is for.
* **Typical use at instrument makers:** service scripts, simulators, data and log analysis, system tests of Python-based tools, test infrastructure.

### 9.3 Gherkin (the language) – Behave and pytest-bdd (two Python runners)

* **Gherkin** = `Given / When / Then` text. It *is* the test specification and the executable test at the same time, so they cannot drift apart.
* **Behave:** a standalone BDD runner (own CLI, `environment.py` hooks, `context` object). It is simple and close to Cucumber, but it is not pytest, so pytest fixtures and plugins are not available.
* **pytest-bdd:** Gherkin *inside* pytest. You get fixtures, parametrisation, the pytest plugins (including Playwright) and one runner for everything. Its binding style is a bit more formal.
* **Why both here?** The user asked to see the difference, and it is real:

| | Behave | pytest-bdd |
|---|---|---|
| Runner | own (`behave`) | pytest |
| State between steps | `context` object | pytest fixtures |
| Hooks | `environment.py` (before/after scenario …) | fixtures, conftest, pytest hooks |
| Plugins | Behave-specific (few) | Whole pytest ecosystem (xdist, playwright, html, rerun …) |
| Reports | `--junit` | `--junitxml` like any pytest test |
| Choose it when | the team is BDD-first and wants the Cucumber feel | the team already uses pytest, or needs Playwright and fixtures |

* **Same feature files:** 29 scenarios, identical results with both runners. That proves the specification is runner-independent.

### 9.4 C#, .NET, Reqnroll, FlaUI (the Windows black-box suite)

* **.NET / C#:** typical language for Windows instrument control software at Hamilton and Roche. The test code often lives in the same language and solution as the product.
* **Reqnroll:** Gherkin runner for .NET. It is the open-source continuation of **SpecFlow** (forked Jan 2024; SpecFlow is end-of-life). It generates NUnit/xUnit/MSTest tests from `.feature` files and has context injection and hooks. Its role is the same as Behave or pytest-bdd, but in C#.
* **FlaUI:** wraps Microsoft **UI Automation (UIA)**. It finds windows and controls by type and name, clicks, types and reads text, values and ranges. It works on WPF, WinForms, Win32 and Qt (Qt exposes UIA through its accessibility bridge).
* **Why it is needed in addition to the Python suites:** it is **black-box**. It starts the real `python main.py` process and uses only what a user or screen reader sees. It finds things in-process tests can miss: accessibility names, real keyboard focus, real OS input, the start-up from a clean state, Windows-specific file and registry behaviour.
* **Why not use it for everything:**
  * UIA **cannot read text colours**, so colour marks are checked via the persisted `*.marks.json`, a product output.
  * Folded (hidden) lines are not exposed, so these are `@python_only` and the scenario is excluded by tag.
  * It is Windows-only, slower and more fragile (focus, timing), and needs an *interactive desktop session* on the CI agent.
* **Why not Playwright for the desktop app?** Playwright automates browsers through the DOM and the Chrome DevTools Protocol. A Qt or WPF window has no DOM, so Playwright cannot see it. (It can automate Electron apps, because they are browsers inside.)
* **Alternatives on the same principle (UIA):** WinAppDriver (Microsoft, no longer actively developed), pywinauto (Python, UIA backend), Appium Windows driver, commercial Ranorex and TestComplete.
* **Status in this delivery:** the C# project is written and statically checked (C# syntax parser, plus `tools/check_csharp_bindings.py`, which proves that all 107 desktop step lines have exactly one C# binding). It was **not compiled or run** in this environment: no .NET SDK, NuGet is blocked, and FlaUI needs Windows. The first run on Windows is therefore a **dry run**; expect small fixes such as control names and timing.

### 9.5 Manual testing

It is still required (chapter 6). Use it for usability, look and feel, exploratory sessions, first-time validation of new automation, and when automation is unavailable. The protocol `docs/05_Manual_Test_Protocol.xlsx` has instructions, an example row, Pass/Fail/Blocked/N/A dropdowns, automatic summary formulas and a sign-off sheet.

### 9.6 Playwright (web)

* **What:** browser automation (Chromium, Firefox, WebKit) with auto-waiting, web-first assertions (`expect`), emulation (dark mode, mobile) and tracing.
* **Why here:** our only web UI is the **HTML traceability report**, a QMS tool output that auditors and reviewers use. Testing it (filters, counts, statuses, dark mode) is **tool validation** (ISO 13485 4.1.6).
* **Two styles shown:** `test_report_bdd.py` (pytest-bdd + Playwright, Gherkin `features_web/`) and `test_report_plain.py` (plain pytest-playwright). Same assertions, different readability and audience.
* **Where it fits at instrument makers:** web-based instrument UIs, LIS/middleware web portals, cloud dashboards, and REST APIs (`request` fixture).
* **Alternatives (free):** Selenium WebDriver (older, bigger ecosystem, no built-in auto-wait) and Cypress (JS only, runs inside the browser).

### 9.7 Git

Everything (requirements, tests, tools, pipelines) is versioned together. A release is a **tag**, and the test report records the **commit**. Typical rules: `main` is protected, work happens on feature branches, merges go through a pull request with review plus a green pipeline, and release branches are used for fixes to a released version. Why: IEC 62304 §8 configuration management means "which exact version did we test?" must always have an answer.

### 9.8 Linux, SSH

* **Linux:** CI agents, Docker hosts and many lab or embedded controllers run Linux. Our full Python stack runs headless (`QT_QPA_PLATFORM=offscreen`).
* **SSH:** run tests on a remote lab machine (for example a PC next to an instrument or a simulator) and fetch the results. See `tools/run_remote.sh`: it checks out an exact commit, runs everything in Docker and copies the reports back with `scp`. Use key-based login only, never passwords in scripts.

### 9.9 Docker

* **Why:** the same OS, libraries, Python and browser everywhere. Without Docker, "it fails on the CI agent but not on my PC" costs days. The `Dockerfile` *documents* the test environment as code, which is useful as installation qualification (IQ) evidence.
* **Why not for the Windows UI tests:** Windows containers have no interactive desktop, so UI Automation cannot drive windows. Those run on a dedicated Windows agent or VM.
* **Status:** the Dockerfile was **not built** here (no Docker daemon in this environment).

### 9.10 CI/CD: TeamCity and Azure DevOps

* **Why CI at all:** every commit is tested automatically, the same way, with stored evidence. Regressions are found within hours, not at the release test.
* **Pipeline (both files implement the same three stages):**
  1. Linux: static checks, developer tests, system tests, pytest-bdd, Behave, Playwright
  2. Windows: Reqnroll + FlaUI
  3. Report: merge the results, generate the documents, quality gate
* **TeamCity** (JetBrains, `tests/test_automation/ci/teamcity/settings.kts`, Kotlin DSL): strong build chains (snapshot and artifact dependencies), agents on your own hardware. It is common in companies with on-premises labs.
* **Azure DevOps** (`tests/test_automation/ci/azure-pipelines.yml`, YAML): pipelines plus Boards (work items), Repos and Test Plans in one place. It is common in Microsoft-centred companies.
* **Why both are delivered:** the CV lists both, and the concepts are identical (agent, pipeline, stage, artifact, test-result publishing, gate). If you know one well, you can switch in days.
* **Status:** both files were **not executed** here (no CI server). The YAML syntax was checked.

---

## 10 Same test, different tools: the comparison

Test case **TC-LEG-002** ("add a colour in the legend"):

| | pytest-bdd / Behave (Python) | Reqnroll + FlaUI (C#) | Plain pytest |
|---|---|---|---|
| How it acts | Real Qt dialog, in-process keyboard events | Real OS mouse and keyboard on the real window | Calls the driver directly |
| How it checks the colour | Reads the drawn text colour | Reads `tree.txt.marks.json` (UIA cannot see colours) | Reads the drawn colour |
| Speed | ~1 s | ~5–10 s (process start, real input) | ~1 s |
| Finds focus bugs? | Only if focus is simulated realistically (that is how ANOMALY-001 was found) | **Yes, naturally** | Rarely |
| Readable by non-programmers | Yes (Gherkin) | Yes (same Gherkin) | No |
| Runs on Linux CI | Yes | No | Yes |

**Conclusion an expert gives:** use in-process tests for breadth and speed, black-box UIA tests for the real user path on the target OS, Gherkin where non-programmers must review, and plain pytest for data-heavy and parametrised checks.

---

## 11 Making automation reliable (where most projects fail)

1. **No fixed sleeps as synchronisation.** Wait for a condition: `Retry.WhileFalse` (FlaUI), `expect(...)` auto-wait (Playwright), event processing (Qt). The few sleeps in this code are documented settle times after input, not waits for a result.
2. **Independence:** each scenario has a fresh temporary folder, a fresh process and clean settings (`SettingsBackup` on Windows, a temporary ini in Python). Order must not matter.
3. **Do not touch the tester's machine:** settings are backed up and restored, and the colour file is redirected via `NODEON_COLORS_FILE`.
4. **Test data under version control:** `specs/test_data/`, with edge cases (CRLF, BOM, Latin-1, binary).
5. **Evidence on failure:** a screenshot (C#), the expected/actual tree in the message (Python), and JUnit or TRX into CI.
6. **Flaky test = defect.** Find the cause and do not just rerun. Quarantine is allowed only when it is visible and has a ticket.
7. **The application is not changed for tests.** Testability comes from outside (env variables, settings, accessibility names). If a hook is unavoidable, it is a reviewed requirement.
8. **Fail fast:** cheap static checks first (binding check, YAML validity), expensive UI tests last.

---

## 12 Licences and free alternatives (**verify** before purchase decisions)

| Tool | Free? | Licence / conditions | Free alternative (same principle) |
|---|---|---|---|
| Python | Yes | PSF licence | – |
| pytest | Yes | MIT | unittest (standard library) |
| Behave | Yes | BSD | – |
| pytest-bdd | Yes | MIT | – |
| Playwright | Yes | Apache 2.0 | Selenium (Apache 2.0) |
| C# / .NET SDK | Yes | MIT (.NET) | – |
| Visual Studio (IDE) | Community is free with limits for larger companies; Pro/Enterprise are paid | Microsoft licence **(verify)** | VS Code; JetBrains Rider (free for non-commercial use **(verify)**). Building and testing need only the free .NET SDK |
| Gherkin | Yes | MIT (Cucumber) | – |
| Reqnroll | Yes | BSD-3-Clause | – (SpecFlow is end-of-life) |
| FlaUI | Yes | MIT | pywinauto, Appium Windows driver |
| NUnit | Yes | MIT | xUnit, MSTest |
| TeamCity | **Professional edition free** (100 build configurations, 3 agents); Enterprise and Cloud paid | JetBrains | Jenkins, GitLab CI, GitHub Actions |
| Azure DevOps | Free tier: 5 Basic users and limited pipeline minutes **(verify)**; Test Plans paid | Microsoft | GitHub Actions, GitLab CI, Jenkins |
| Linux | Yes | GPL etc. | – |
| Git | Yes | GPLv2 | – |
| SSH (OpenSSH) | Yes | BSD | – |
| Docker Engine (Linux) | Yes | Apache 2.0 | Podman |
| Docker Desktop | **Paid** for companies with >250 employees or >$10M revenue | Docker subscription | Docker Engine on Linux, Podman Desktop, Rancher Desktop |
| PySide6 (app) | Yes | LGPLv3 | – |
| Test management (Polarion, Jama, Codebeamer, Azure Test Plans) | Paid | Commercial | Docs-as-code as in this repo, Kiwi TCMS |

---

## 13 How to run (automated and manual)

**Linux / macOS / Docker (everything except the Windows suite):**
```bash
pip install -r tests/test_automation/requirements-test.txt
python -m playwright install chromium
bash tests/test_automation/tools/run_all.sh                # → RESULT: ALL GREEN
```
**Docker:**
```bash
docker build -t nodeon-tests -f tests/test_automation/Dockerfile .
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$PWD/test_automation/reports:/work/test_automation/reports" \
  -v "$PWD/test_automation/docs:/work/test_automation/docs" nodeon-tests
```
**Windows (all suites including Reqnroll + FlaUI):**
```powershell
powershell -ExecutionPolicy Bypass -File test_automation\tools\run_all.ps1
```
**Remote lab machine over SSH:** `tests/test_automation/tools/run_remote.sh tester@lab-pc [commit]`

**Single suites:**
```bash
cd test_automation
python -m pytest python/system_tests -k FOLD          # pytest, one area
python -m pytest python/bdd_pytest                    # pytest-bdd
python -m behave features --tags="not @python_only"  # Behave, Windows-equivalent scope
python -m pytest python/web_tests --headed            # Playwright, browser visible
python tools/generate_docs.py --require-pass          # documents + quality gate
dotnet test dotnet/Nodeon.SystemTests --filter "Category!=python_only"   # Windows
```
**Manual:** open `docs/05_Manual_Test_Protocol.xlsx`, read the *Instructions* sheet, execute each row (every automated TC is also listed), choose Pass/Fail/Blocked/N/A, enter the version, date and initials, link anomalies, then sign on the *Sign-off* sheet. Every scenario in `features/*.feature` can also be followed by hand: it is written as user actions.

---

## 14 Expert checklist (what distinguishes a senior system tester)

* I can explain **verification vs. validation** and IEC 62304 §5.7 without notes.
* I review requirements for testability **before** any test is written.
* Every test has a reason (a requirement or risk), and every requirement has a test (bidirectional trace).
* I choose the technique (boundary values, decision tables, state transitions …) deliberately and can name it.
* I separate **specification** (Gherkin), **binding**, **logic** and **driver**.
* I know what each tool **cannot** do (Playwright ≠ desktop; UIA ≠ colours; in-process ≠ real focus), and I close the gap with another tool or a manual test, documented.
* I treat flaky tests as defects and use condition-based waits.
* I report anomalies with a risk assessment, not just "it is broken".
* I make results reproducible: pinned versions, Docker, commit id, clean environment.
* I validate the tools I rely on (tool validation, CSA).
* I can run the full test manually when automation is not available.
* For instruments: I know the hardware-in-the-loop ladder: **simulator → instrument in the lab → system with real samples/consumables**. Automation runs mostly against simulators, and a defined subset runs against physical instruments.

---

## 15 Glossary

| Term | Meaning |
|---|---|
| SRS | Software Requirements Specification |
| TC | Test case |
| Oracle | How the tester knows the expected result (the `acceptance` text) |
| Anomaly | Any deviation from expectation (IEC 62304 term; includes defects) |
| Regression | Something that worked before is broken by a change |
| Quality gate | Automated pass/fail criterion that blocks a release |
| IQ/OQ/PQ | Installation, operational and performance qualification (of equipment or tools) |
| UIA | Microsoft UI Automation, the accessibility API used by FlaUI |
| BDD | Behaviour-driven development: Gherkin specifications as tests |
| SOUP | Software of unknown provenance, i.e. third-party components (PySide6 here). IEC 62304 requires listing them and their known anomalies |
| Notified body | EU organisation that certifies higher-class IVDs under the IVDR |
