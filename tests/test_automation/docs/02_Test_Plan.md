# Software Verification Test Plan

| Product | Version | Document | Status |
|---|---|---|---|
| Nodeon | 1.1.0 | STP-NODEON-001 | Approved for execution (example) |

Related documents: SRS-NODEON-001 (`01_…`), Test Specification (`03_…`), Traceability Matrix (`04_…`), Manual Test Protocol (`05_…`), Test Report (`06_…`), Testing Guide (`00_…`).

## 1 Purpose and scope

This plan defines how Nodeon 1.1.0 is verified against its 120 software requirements.

**In scope:** software system testing (IEC 62304 §5.7) of the desktop application on Linux and Windows: file handling, tree format, folding, structural editing, shortcuts, explanations, pasting, column selection, colours and marks, legend, find, UI and settings, error handling. It also covers the validation of the test tooling itself (report generator and HTML report).

**Out of scope:** validation with real users (IEC 62366-1 summative evaluation), performance and load (no requirement), macOS (not a target platform), localisation, installer and packaging. Unit and integration tests are owned by development (`../tests`, 173 tests), but their results are included in the traceability.

## 2 Safety classification and rigour

Nodeon is not a medical device. For training purposes it is tested **as if it were IEC 62304 class B**: system tests for every requirement, documented anomalies with risk evaluation, and traceability. The highest risk is **data loss or silent corruption of the user's file**. Requirements in FMT, FILE, SAFE and EDIT (invariants) are therefore priority *high*. They are tested with multiple techniques and by at least two independent tools.

## 3 Test items and configuration

| Item | Identification |
|---|---|
| Application | `main/main.py`, `main/treemodel.py`, Git commit recorded in the report |
| Third-party software (SOUP) | PySide6 6.x (Qt), Python ≥ 3.10 |
| Test tools | Pinned in `tests/test_automation/requirements-test.txt` and `dotnet/…csproj` |
| Test data | `specs/test_data/*` (versioned) |

## 4 Strategy

| Layer | Purpose | Tool | Runs on |
|---|---|---|---|
| Static checks | Fail fast: ids, YAML, C# step bindings | `generate_docs.py`, `check_csharp_bindings.py` | Linux |
| Developer unit + GUI tests | Code correctness | pytest (unittest) | Linux, Windows |
| System tests (driver) | Breadth, boundaries, fault injection, invariants | pytest | Linux, Windows |
| BDD system tests | Reviewable specification, user flows | pytest-bdd **and** Behave (same features) | Linux, Windows |
| Black-box UI tests | Real process, real OS input, accessibility | Reqnroll + FlaUI (same features, `@desktop`) | Windows (interactive agent) |
| Tool validation | HTML traceability report works | Playwright (pytest-bdd + plain) | Linux |
| Manual tests | Usability aspects, dry run of automation, fallback | Protocol xlsx | Any |
| Exploratory sessions | Find what the specification missed | Charter + notes in the protocol | Any |

Test design techniques per requirement area are listed in the Test Specification (`technique` per TC).

## 5 Environments

| Id | Environment | Use |
|---|---|---|
| ENV-L1 | Docker image `tests/test_automation/Dockerfile` (Ubuntu 24.04, Python, Chromium, Qt offscreen) | CI, reproducible reference |
| ENV-L2 | Developer Linux PC | Development, debugging |
| ENV-W1 | Windows 10/11, interactive session, Python 3.10+, .NET 8 SDK | Reqnroll + FlaUI, manual tests |
| ENV-R | Remote lab machine via SSH (`tools/run_remote.sh`) | Shared test rig |

## 6 Entry and exit criteria

**Entry (start of a formal verification run):**
* The build is identified by a Git tag or commit, and the SRS and Test Specification are reviewed and baselined.
* The environment matches §5, and the tool versions match the pinned versions.
* The smoke test passes (application starts, opens `tree_a.txt`).

**Exit (verification complete):**
* 100 % of requirements are traced to at least one executed test case (quality gate green).
* 100 % of automated tests pass on ENV-L1, and the `@desktop` scenarios pass on ENV-W1.
* All manual TCs are executed and signed.
* No open anomaly of severity *high*. Open *medium* or *low* anomalies are evaluated, justified and listed in the test report.
* The test report is reviewed and signed (Sign-off sheet).

**Suspension / resumption:** suspend if the smoke test fails, the environment is not reproducible, or more than 20 % of tests are blocked. Resume after a new build and a repeated smoke test.

## 7 Risks to the test project

| Risk | Effect | Mitigation |
|---|---|---|
| UI tests flaky (focus, timing) | False alarms, lost trust | Condition-based waits, clean state per scenario, flaky = defect |
| Windows agent unavailable | No black-box evidence | Manual protocol covers the same TCs |
| Tool update changes behaviour | Unnoticed wrong results | Pinned versions, Playwright validation of the report |
| Requirements ambiguous | Wrong oracle | Tester review of the SRS (see ANOMALY-002) |
| Tester's own settings changed by tests | Wrong results, annoyed users | Settings backup and restore, temporary folders |

## 8 Anomaly management

Anomalies are recorded in `specs/anomalies.yaml` (id, title, found by, version, steps, expected/actual, severity, risk, status, decision) and appear in the test report. Workflow and severities: see Testing Guide §7.

## 9 Roles

| Role | Responsibility |
|---|---|
| Test lead | This plan, entry/exit decision, test report approval |
| Test automation engineer | Frameworks, drivers, CI pipelines, tool validation |
| Tester | Test design, manual execution, exploratory sessions, anomaly reports |
| Developer | Unit/integration tests, fixes, root-cause analysis |
| QA / regulatory | Review of traceability and report, release sign-off |

## 10 Deliverables

SRS, this test plan, Test Specification, Traceability Matrix, executed Manual Test Protocol, automated results (JUnit, TRX, HTML), Test Report, anomaly list.

## 11 Schedule (per release)

1. Requirement review → 2. Test design and automation updates → 3. Dry run (manual and automated) → 4. Formal run on the tagged build → 5. Anomaly evaluation and retests → 6. Test report and sign-off.
