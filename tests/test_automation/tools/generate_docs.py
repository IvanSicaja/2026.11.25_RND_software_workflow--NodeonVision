#!/usr/bin/env python3
"""
generate_docs.py - builds the test documentation and the traceability report.

Inputs  (single source of truth, version-controlled with the code)
    specs/requirements.yaml   the requirements (REQ-...)
    specs/test_cases.yaml     the test cases (TC-...) with manual steps
    specs/anomalies.yaml      defects / observations found by testing
    reports/                  JUnit / TRX results of every test tool (optional)

Outputs
    docs/01_Software_Requirements_Specification.md
    docs/03_Test_Specification.md
    docs/04_Traceability_Matrix.md
    docs/05_Manual_Test_Protocol.xlsx      (fill in during manual execution)
    docs/06_Test_Report.md
    reports/traceability.html               (interactive; verified with Playwright)

Quality gate (exit code 1, so CI fails):
    * duplicate ids, test cases that point to unknown requirements,
    * requirements without any test case,
    * automated references that do not exist in the developer test results,
    * (with --require-pass) any failed test.

Usage:  python tools/generate_docs.py [--require-pass]
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import html
import json
import os
import platform
import re
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]          # tests/test_automation/
SPECS = ROOT / "specs"
REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"

# Result files of every tool (glob relative to reports/), in report order.
TOOLS = OrderedDict([
    ("dev", ("pytest - unit & GUI (developers)", ["junit-dev.xml"])),
    ("system", ("pytest - system tests", ["junit-system.xml"])),
    ("pytest-bdd", ("pytest-bdd (Gherkin, Python)", ["junit-pytest-bdd.xml"])),
    ("behave", ("Behave (Gherkin, Python)", ["behave/*.xml"])),
    ("reqnroll", ("Reqnroll + FlaUI (Gherkin, C#, Windows)", ["reqnroll/*.xml", "reqnroll/*.trx"])),
    ("playwright", ("Playwright + pytest-bdd (web report)", ["junit-playwright.xml"])),
])
STATUS_ORDER = ["failed", "passed", "skipped"]


# ----------------------------------------------------------------- loading
def load_yaml(name: str):
    with open(SPECS / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def parse_junit(path: Path):
    """[(classname, name, status, message)] from a JUnit XML file."""
    out = []
    root = ET.parse(path).getroot()
    for case in root.iter("testcase"):
        status, msg = "passed", ""
        for child in case:
            tag = child.tag.lower()
            if tag in ("failure", "error"):
                status, msg = "failed", (child.get("message") or "")[:300]
            elif tag == "skipped":
                status, msg = "skipped", (child.get("message") or "")[:300]
        out.append((case.get("classname", ""), case.get("name", ""), status, msg))
    return out


def parse_trx(path: Path):
    """[(classname, name, status, message)] from a Visual Studio TRX file (dotnet test)."""
    ns = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
    root = ET.parse(path).getroot()
    out = []
    for r in root.iterfind(".//t:UnitTestResult", ns):
        outcome = (r.get("outcome") or "").lower()
        status = {"passed": "passed", "failed": "failed"}.get(outcome, "skipped")
        out.append(("reqnroll", r.get("testName", ""), status, ""))
    return out


def load_results():
    """{tool key: [(classname, name, status, message)]} - missing tools are absent."""
    results = {}
    for key, (_label, patterns) in TOOLS.items():
        cases = []
        found = False
        for pattern in patterns:
            for p in sorted(glob.glob(str(REPORTS / pattern))):
                found = True
                cases += parse_trx(Path(p)) if p.endswith(".trx") else parse_junit(Path(p))
        if found:
            results[key] = cases
    return results


# ------------------------------------------------------------------ linking
def link(reqs, tcs, results):
    """Attach the automated results to every test case."""
    errors = []
    dev = results.get("dev", [])
    for tc in tcs:
        tc["results"] = []                     # (tool key, test name, status)
        for ref in tc.get("automated") or []:
            _kind, _, ident = ref.partition(":")
            cls, _, name = ident.strip().partition("::")
            hits = [c for c in dev if c[1] == name and c[0].endswith(cls)]
            if dev and not hits:
                errors.append(f"{tc['id']}: automated test not found in the results: {ref}")
            tc["results"] += [("dev", f"{cls}::{name}", h[2]) for h in hits]
            if not dev:
                tc["results"].append(("dev", f"{cls}::{name}", "not run"))
        key = norm(tc["id"])
        for tool, cases in results.items():
            if tool == "dev":
                continue
            for cls, name, status, _msg in cases:
                if key in norm(name):
                    tc["results"].append((tool, name, status))
        statuses = {r[2] for r in tc["results"]}
        if "failed" in statuses:
            tc["status"] = "failed"
        elif "passed" in statuses:
            tc["status"] = "passed"
        elif not tc["results"] or tc.get("manual_only"):
            tc["status"] = "manual"
        else:
            tc["status"] = "not run"
        tc["tools"] = sorted({r[0] for r in tc["results"]}, key=list(TOOLS).index)
    by_req = {r["id"]: [] for r in reqs}
    for tc in tcs:
        for rid in tc["reqs"]:
            if rid not in by_req:
                errors.append(f"{tc['id']}: unknown requirement {rid}")
            else:
                by_req[rid].append(tc)
    for r in reqs:
        r["tcs"] = by_req[r["id"]]
        st = {tc["status"] for tc in r["tcs"]}
        if not r["tcs"]:
            r["status"] = "not covered"
            errors.append(f"{r['id']}: no test case covers this requirement")
        elif "failed" in st:
            r["status"] = "failed"
        elif "passed" in st:
            r["status"] = "passed"
        elif st == {"manual"}:
            r["status"] = "manual"
        else:
            r["status"] = "not run"
    for kind, items in (("requirement", reqs), ("test case", tcs)):
        ids = [i["id"] for i in items]
        for dup in sorted({i for i in ids if ids.count(i) > 1}):
            errors.append(f"duplicate {kind} id {dup}")
    return errors


# ---------------------------------------------------------------- markdown
def md_escape(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def header(title, meta, doc_id):
    today = dt.date.today().isoformat()
    return (f"# {title}\n\n"
            f"| Product | Version | Document | Generated |\n|---|---|---|---|\n"
            f"| {meta['product']} | {meta['version']} | {doc_id} | {today} |\n\n"
            "> Generated by `tools/generate_docs.py` from `specs/*.yaml` and the test results. "
            "Do not edit by hand - change the YAML files and regenerate.\n\n")


def write_srs(meta, areas, reqs):
    out = [header("Software Requirements Specification", meta, meta["document"])]
    out.append(f"## 1 Intended use\n\n{meta['intended_use'].strip()}\n\n")
    out.append("## 2 Conventions\n\n* Every requirement has a permanent id `REQ-<AREA>-<NNN>`; ids "
               "are never re-used.\n* *shall* = mandatory. Each requirement is one testable "
               "statement with an acceptance criterion.\n* Priority: High = core function / data "
               "integrity, Medium = important convenience, Low = cosmetic.\n\n")
    out.append("## 3 Requirements\n\n")
    for code, name in areas.items():
        rs = [r for r in reqs if r["id"].split("-")[1] == code]
        if not rs:
            continue
        out.append(f"### {code} - {name}\n\n| ID | Requirement | Acceptance criterion | Prio | Source |\n"
                   "|---|---|---|---|---|\n")
        for r in rs:
            out.append(f"| **{r['id']}** {md_escape(r['title'])} | {md_escape(r['text'])} | "
                       f"{md_escape(r['acceptance'])} | {r['priority']} | {md_escape(r['source'])} |\n")
        out.append("\n")
    out.append(f"Total: **{len(reqs)} requirements**.\n")
    (DOCS / "01_Software_Requirements_Specification.md").write_text("".join(out), encoding="utf-8")


def write_test_spec(meta, tcs):
    out = [header("Test Specification", meta, "TSP-NODEON-001")]
    out.append("Each test case can be executed **manually** (steps below; record results in "
               "`05_Manual_Test_Protocol.xlsx`) and is **automated** by the tests listed. BDD "
               "scenarios and pytest system tests are linked automatically through the test case "
               "id in their name.\n\n")
    for tc in tcs:
        out.append(f"## {tc['id']} - {tc['title']}\n\n"
                   f"| Requirements | Level | Technique | Priority |\n|---|---|---|---|\n"
                   f"| {', '.join(tc['reqs'])} | {tc['level']} | {md_escape(tc['technique'])} | "
                   f"{tc['priority']} |\n\n**Preconditions:** {tc['preconditions']}\n\n"
                   "| # | Action | Expected result |\n|---|---|---|\n")
        for i, (action, expected) in enumerate(tc["steps"], 1):
            out.append(f"| {i} | {md_escape(action)} | {md_escape(expected)} |\n")
        autos = sorted({f"{TOOLS[t][0]}: `{n}`" for t, n, _s in tc["results"]})
        out.append("\n**Automated by:** " + ("; ".join(autos) if autos else
                                            "manual execution only") + "\n\n")
    (DOCS / "03_Test_Specification.md").write_text("".join(out), encoding="utf-8")


ICON = {"passed": "✅ passed", "failed": "❌ failed", "manual": "📝 manual",
        "not run": "⏸ not run", "not covered": "⚠ not covered", "skipped": "⏭ skipped"}


def tool_cell(tc_list, tool):
    st = [r[2] for tc in tc_list for r in tc["results"] if r[0] == tool]
    if not st:
        return "–"
    if "failed" in st:
        return f"❌ {st.count('failed')}/{len(st)}"
    if "passed" in st:
        return f"✅ {st.count('passed')}"
    return "⏸"


def write_trace(meta, reqs, tcs, results):
    out = [header("Traceability Matrix", meta, "TRM-NODEON-001")]
    covered = sum(1 for r in reqs if r["tcs"])
    out.append(f"Requirements covered by test cases: **{covered} / {len(reqs)}**. "
               f"Status: {count_line(reqs)}.\n\n## 1 Requirement → test cases → results per tool\n\n")
    cols = [k for k in TOOLS]
    out.append("| Requirement | Test cases | Status | " + " | ".join(TOOLS[k][0] for k in cols)
               + " |\n|---|---|---|" + "---|" * len(cols) + "\n")
    for r in reqs:
        out.append(f"| {r['id']} {md_escape(r['title'])} | {', '.join(tc['id'] for tc in r['tcs'])} "
                   f"| {ICON[r['status']]} | " + " | ".join(tool_cell(r['tcs'], k) for k in cols) + " |\n")
    out.append("\n## 2 Test case → requirements (backward)\n\n| Test case | Requirements | "
               "Status | Tools |\n|---|---|---|---|\n")
    for tc in tcs:
        out.append(f"| {tc['id']} {md_escape(tc['title'])} | {', '.join(tc['reqs'])} | "
                   f"{ICON[tc['status']]} | {', '.join(tc['tools']) or 'manual'} |\n")
    (DOCS / "04_Traceability_Matrix.md").write_text("".join(out), encoding="utf-8")


def count_line(items):
    counts = {}
    for i in items:
        counts[i["status"]] = counts.get(i["status"], 0) + 1
    return ", ".join(f"{ICON[k]}: {v}" for k, v in sorted(counts.items()))


def versions():
    out = {"Python": platform.python_version(), "OS": platform.platform()}
    for pkg in ("PySide6", "pytest", "pytest-bdd", "behave", "playwright"):
        try:
            from importlib.metadata import version
            out[pkg] = version(pkg)
        except Exception:
            out[pkg] = "not installed"
    return out


def write_report(meta, reqs, tcs, results, anomalies, errors):
    out = [header("Test Report", meta, "TRP-NODEON-001")]
    out.append("## 1 Summary\n\n")
    out.append(f"* Requirements: **{len(reqs)}** - {count_line(reqs)}\n"
               f"* Test cases: **{len(tcs)}** - {count_line(tcs)}\n"
               f"* Open anomalies: **{sum(1 for a in anomalies if not str(a['status']).startswith('Closed'))}**"
               " (see chapter 4)\n* Quality gate: " +
               ("**passed**" if not errors else f"**{len(errors)} problem(s)** (chapter 5)") + "\n\n")
    out.append("## 2 Results per tool\n\n| Tool | Tests | Passed | Failed | Skipped |\n|---|---|---|---|---|\n")
    for key, (label, _p) in TOOLS.items():
        cases = results.get(key)
        if cases is None:
            reason = ("needs Windows + .NET SDK - run tests/test_automation/dotnet on Windows"
                      if key == "reqnroll" else "not run")
            out.append(f"| {label} | – | – | – | {reason} |\n")
            continue
        n = len(cases)
        p = sum(1 for c in cases if c[2] == "passed")
        f = sum(1 for c in cases if c[2] == "failed")
        out.append(f"| {label} | {n} | {p} | {f} | {n - p - f} |\n")
    out.append("\n## 3 Test environment\n\n| Item | Value |\n|---|---|\n")
    for k, v in versions().items():
        out.append(f"| {k} | {v} |\n")
    out.append("| Qt platform | offscreen (no visible window) |\n\n")
    out.append("## 4 Anomalies (defects / observations)\n\n")
    if not anomalies:
        out.append("None.\n\n")
    for a in anomalies:
        out.append(f"### {a['id']} - {a['title']}\n\n| Found by | Severity | Risk | Status |\n"
                   f"|---|---|---|---|\n| {a['found_by']} | {a['severity']} | {a['risk']} | "
                   f"{a['status']} |\n\n**Steps:** {a['steps'].strip()}  \n**Expected:** "
                   f"{a['expected']}  \n**Actual:** {a['actual'].strip()}  \n**Proposal:** "
                   f"{a['proposal']}\n\n")
    out.append("## 5 Quality gate findings\n\n" + ("None.\n" if not errors else
                                                   "".join(f"* {e}\n" for e in errors)))
    failed = [tc for tc in tcs if tc["status"] == "failed"]
    out.append("\n## 6 Failed test cases\n\n" + ("" if failed else "None.\n"))
    if failed:
        for tc in failed:
            for t, n, s in tc["results"]:
                if s == "failed":
                    out.append(f"* {tc['id']} - {TOOLS[t][0]}: `{n}`\n")
    out.append("\n## 7 Conclusion\n\n")
    if errors or failed:
        out.append("Verification is **not complete**: resolve the findings above, rerun, regenerate.\n")
    else:
        manual = sum(1 for tc in tcs if tc["status"] == "manual")
        windows_ran = any(t == "reqnroll" for tc in tcs for t, _n, _s in tc["results"])
        out.append("All automated tests that were run **passed** and every requirement is traced to at "
                   f"least one test case. {manual} test case(s) need manual execution (protocol "
                   "05_Manual_Test_Protocol.xlsx)"
                   + ("." if windows_ran else " and the Windows suite (Reqnroll + FlaUI) must be run "
                      "on Windows before release.") + "\n")
    (DOCS / "06_Test_Report.md").write_text("".join(out), encoding="utf-8")


# --------------------------------------------------------------------- html
def write_html(meta, reqs, results):
    rows = []
    for r in reqs:
        tools = " ".join(f'<span class="tool {s}">{html.escape(TOOLS[t][0].split(" (")[0])}</span>'
                         for t, s in tool_summary(r))
        rows.append(
            f'<tr data-status="{r["status"].replace(" ", "-")}">'
            f'<td class="id">{r["id"]}</td><td>{html.escape(r["title"])}</td>'
            f'<td>{", ".join(tc["id"] for tc in r["tcs"]) or "–"}</td>'
            f'<td><span class="badge {r["status"].replace(" ", "-")}">{r["status"]}</span></td>'
            f'<td>{tools}</td></tr>')
    counts = {s: sum(1 for r in reqs if r["status"] == s)
              for s in ("passed", "failed", "manual", "not covered", "not run")}
    covered = sum(1 for r in reqs if r["tcs"])
    page = HTML_TEMPLATE.format(
        product=meta["product"], version=meta["version"], date=dt.date.today().isoformat(),
        total=len(reqs), covered=covered, passed=counts["passed"], failed=counts["failed"],
        manual=counts["manual"], rows="\n".join(rows),
        tools=", ".join(TOOLS[k][0] for k in results) or "none")
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "traceability.html").write_text(page, encoding="utf-8")


def tool_summary(req):
    out = []
    for key in TOOLS:
        st = [r[2] for tc in req["tcs"] for r in tc["results"] if r[0] == key]
        if st:
            out.append((key, "failed" if "failed" in st else "passed" if "passed" in st else "skipped"))
    return out


HTML_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nodeon Traceability</title>
<style>
:root {{ --bg:#ffffff; --fg:#1f2328; --muted:#5b6370; --line:#d8dde3; --ok:#1a7f37; --bad:#cf222e;
        --man:#8250df; --warn:#9a6700; --tile:#f6f8fa; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#16181d; --fg:#e6e8eb; --muted:#9aa3ad;
        --line:#30353d; --ok:#3fb950; --bad:#f85149; --man:#bc8cff; --warn:#d29922; --tile:#1e2128; }} }}
body {{ background:var(--bg); color:var(--fg); font:14px/1.45 system-ui, sans-serif; margin:0; padding:24px 16px; }}
main {{ max-width:1200px; margin:0 auto; }}
h1 {{ font-size:22px; margin:0 0 4px; }} p.sub {{ color:var(--muted); margin:0 0 20px; }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin-bottom:18px; }}
.tile {{ background:var(--tile); border:1px solid var(--line); border-radius:8px; padding:10px 12px; }}
.tile b {{ display:block; font-size:24px; }} .tile span {{ color:var(--muted); }}
.controls {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:10px; }}
input, select {{ font:inherit; padding:6px 8px; border:1px solid var(--line); border-radius:6px;
                background:var(--bg); color:var(--fg); }} input {{ flex:1; min-width:200px; }}
.wrap {{ overflow-x:auto; }} table {{ width:100%; border-collapse:collapse; }}
th, td {{ text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ color:var(--muted); font-weight:600; }} td.id {{ white-space:nowrap; font-family:ui-monospace,monospace; }}
.badge {{ border-radius:10px; padding:1px 8px; font-size:12px; white-space:nowrap; border:1px solid; }}
.badge.passed {{ color:var(--ok); }} .badge.failed {{ color:var(--bad); }} .badge.manual {{ color:var(--man); }}
.badge.not-covered, .badge.not-run {{ color:var(--warn); }}
.tool {{ display:inline-block; font-size:12px; margin:1px 4px 1px 0; color:var(--muted); }}
.tool.passed::before {{ content:"✓ "; color:var(--ok); }} .tool.failed::before {{ content:"✗ "; color:var(--bad); }}
#empty {{ color:var(--muted); padding:12px 0; display:none; }}
</style></head><body><main>
<h1>Traceability - {product} {version}</h1>
<p class="sub">Generated {date} from requirements.yaml, test_cases.yaml and the results of: {tools}.</p>
<section class="tiles" aria-label="Summary">
  <div class="tile"><b id="sum-total">{total}</b><span>requirements</span></div>
  <div class="tile"><b id="sum-covered">{covered}</b><span>covered by test cases</span></div>
  <div class="tile"><b id="sum-passed">{passed}</b><span>passed (automated)</span></div>
  <div class="tile"><b id="sum-failed">{failed}</b><span>failed</span></div>
  <div class="tile"><b id="sum-manual">{manual}</b><span>manual only</span></div>
</section>
<div class="controls">
  <input id="filter" type="search" placeholder="Filter: requirement, title or test case" aria-label="Filter">
  <select id="status" aria-label="Status">
    <option value="all">All statuses</option><option value="passed">Passed</option>
    <option value="failed">Failed</option><option value="manual">Manual</option>
    <option value="not-covered">Not covered</option><option value="not-run">Not run</option>
  </select>
  <span id="count" aria-live="polite"></span>
</div>
<div class="wrap"><table id="matrix"><thead><tr><th>Requirement</th><th>Title</th>
<th>Test cases</th><th>Status</th><th>Automated by</th></tr></thead><tbody>
{rows}
</tbody></table></div>
<p id="empty">No requirement matches the filter.</p>
</main>
<script>
const rows = Array.from(document.querySelectorAll("#matrix tbody tr"));
const filter = document.getElementById("filter"), status = document.getElementById("status");
function apply() {{
  const q = filter.value.trim().toLowerCase(), s = status.value;
  let shown = 0;
  rows.forEach(r => {{
    const ok = (s === "all" || r.dataset.status === s) && r.textContent.toLowerCase().includes(q);
    r.hidden = !ok; if (ok) shown++;
  }});
  document.getElementById("count").textContent = shown + " of " + rows.length + " shown";
  document.getElementById("empty").style.display = shown ? "none" : "block";
}}
filter.addEventListener("input", apply); status.addEventListener("change", apply); apply();
</script></body></html>
"""


# --------------------------------------------------------------------- xlsx
def write_protocol(meta, tcs):
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation

    font = Font(name="Arial", size=10)
    bold = Font(name="Arial", size=10, bold=True)
    head_fill = PatternFill("solid", start_color="1F2328")
    head_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    fill_in = PatternFill("solid", start_color="FFFF00")
    wrap = Alignment(wrap_text=True, vertical="top")
    thin = Side(style="thin", color="D0D0D0")
    border = Border(top=thin, bottom=thin, left=thin, right=thin)

    wb = Workbook()
    ws = wb.active
    ws.title = "Instructions"
    rows = [
        (f"Manual Test Protocol - {meta['product']} {meta['version']}", True),
        ("Document MTP-NODEON-001, generated from specs/test_cases.yaml. One row per test step.", False),
        ("", False),
        ("How to fill in", True),
        ("1. Fill in the header on sheet 'Protocol' (tester, date, version, PC).", False),
        ("2. Execute the steps in order. Fill in ONLY the yellow columns: Actual result, "
         "Result (Pass / Fail / Blocked / N/A from the list), Tester, Date, Comment / defect id.", False),
        ("3. Fail: describe what happened in 'Actual result' and create an anomaly (ANOMALY-xxx).", False),
        ("4. Never delete or overwrite a recorded result - add a new row / comment (audit trail).", False),
        ("5. Sheet 'Summary' counts the results per test case automatically.", False),
        ("", False),
        ("Example of a filled-in row (format only - not part of the protocol):", True),
    ]
    for i, (text, is_bold) in enumerate(rows, 1):
        c = ws.cell(row=i, column=1, value=text)
        c.font = bold if is_bold else font
    ex_head = ["TC", "Step", "Action", "Expected result", "Actual result", "Result", "Tester",
               "Date", "Comment / defect"]
    ex_vals = ["TC-FOLD-001", 1, "Press Alt+1", "Only 'project-name/' is visible; Levels 0 / 3.",
               "As expected", "Pass", "A. Tester", "2026-10-15", ""]
    for j, (h, v) in enumerate(zip(ex_head, ex_vals), 1):
        hc = ws.cell(row=12, column=j, value=h)
        hc.font, hc.fill = head_font, head_fill
        vc = ws.cell(row=13, column=j, value=v)
        vc.font, vc.alignment = font, wrap
        if j >= 5:
            vc.fill = fill_in
    ws.column_dimensions["A"].width = 16
    for col in "CDE":
        ws.column_dimensions[col].width = 34

    p = wb.create_sheet("Protocol")
    p["A1"], p["A2"], p["A3"], p["A4"] = "Tester:", "Date:", "Nodeon version:", "PC / OS:"
    for r in range(1, 5):
        p.cell(row=r, column=1).font = bold
        c = p.cell(row=r, column=2)
        c.fill, c.font = fill_in, font
    p["B3"] = meta["version"]
    cols = ["TC", "Title", "Requirements", "Step", "Action", "Expected result",
            "Actual result", "Result", "Tester", "Date", "Comment / defect"]
    widths = [12, 30, 18, 6, 44, 44, 30, 10, 12, 12, 24]
    hrow = 6
    for j, (h, w) in enumerate(zip(cols, widths), 1):
        c = p.cell(row=hrow, column=j, value=h)
        c.font, c.fill, c.alignment, c.border = head_font, head_fill, wrap, border
        p.column_dimensions[c.column_letter].width = w
    dv = DataValidation(type="list", formula1='"Pass,Fail,Blocked,N/A"', allow_blank=True)
    dv.error, dv.errorTitle = "Choose Pass, Fail, Blocked or N/A", "Result"
    p.add_data_validation(dv)
    r = hrow + 1
    for tc in tcs:
        for i, (action, expected) in enumerate(tc["steps"], 1):
            vals = [tc["id"], tc["title"], ", ".join(tc["reqs"]), i, action, expected,
                    None, None, None, None, None]
            for j, v in enumerate(vals, 1):
                c = p.cell(row=r, column=j, value=v)
                c.font, c.alignment, c.border = font, wrap, border
                if j >= 7:
                    c.fill = fill_in
            dv.add(p.cell(row=r, column=8))
            r += 1
    last = r - 1
    p.freeze_panes = p.cell(row=hrow + 1, column=1)
    p.auto_filter.ref = f"A{hrow}:K{last}"
    p.cell(row=hrow, column=8).comment = Comment("Choose from the list: Pass, Fail, Blocked, N/A", "Nodeon QA")

    s = wb.create_sheet("Summary")
    sh = ["TC", "Title", "Steps", "Pass", "Fail", "Blocked", "N/A", "Not executed", "Verdict"]
    for j, h in enumerate(sh, 1):
        c = s.cell(row=1, column=j, value=h)
        c.font, c.fill = head_font, head_fill
    rng_tc = f"Protocol!$A${hrow + 1}:$A${last}"
    rng_res = f"Protocol!$H${hrow + 1}:$H${last}"
    for i, tc in enumerate(tcs, 2):
        s.cell(row=i, column=1, value=tc["id"])
        s.cell(row=i, column=2, value=tc["title"])
        s.cell(row=i, column=3, value=f'=COUNTIF({rng_tc},A{i})')
        for col, word in zip("DEFG", ("Pass", "Fail", "Blocked", "N/A")):
            s[f"{col}{i}"] = f'=COUNTIFS({rng_tc},$A{i},{rng_res},"{word}")'
        s[f"H{i}"] = f"=C{i}-SUM(D{i}:G{i})"
        s[f"I{i}"] = (f'=IF(E{i}>0,"FAIL",IF(F{i}>0,"BLOCKED",'
                      f'IF(H{i}>0,"OPEN",IF(D{i}+G{i}=C{i},"PASS","OPEN"))))')
        for j in range(1, 10):
            s.cell(row=i, column=j).font = font
    n = len(tcs) + 1
    t = n + 2
    s.cell(row=t, column=1, value="Totals").font = bold
    for col in "CDEFGH":
        s[f"{col}{t}"] = f"=SUM({col}2:{col}{n})"
        s[f"{col}{t}"].font = bold
    s.cell(row=t + 1, column=1, value="Test cases PASS").font = font
    s[f"C{t + 1}"] = f'=COUNTIF(I2:I{n},"PASS")'
    s.cell(row=t + 2, column=1, value="Test cases FAIL").font = font
    s[f"C{t + 2}"] = f'=COUNTIF(I2:I{n},"FAIL")'
    s.cell(row=t + 4, column=1, value="Verdict rule: FAIL if any step failed, BLOCKED if any "
                                      "step blocked, PASS when every step is Pass or N/A, "
                                      "otherwise OPEN.").font = font
    s.column_dimensions["A"].width = 14
    s.column_dimensions["B"].width = 50
    s.freeze_panes = "A2"

    so = wb.create_sheet("Sign-off")
    lines = ["Test execution sign-off", "", "Executed by (name, signature, date):", "",
             "Reviewed by (name, signature, date):", "", "Overall verdict (PASS / FAIL):", "",
             "Open anomalies (ids):"]
    for i, text in enumerate(lines, 1):
        c = so.cell(row=i, column=1, value=text)
        c.font = bold if i == 1 else font
        if text.endswith(":"):
            so.cell(row=i, column=2).fill = fill_in
    so.column_dimensions["A"].width = 40
    so.column_dimensions["B"].width = 50
    wb.save(DOCS / "05_Manual_Test_Protocol.xlsx")


# --------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--require-pass", action="store_true", help="fail when any test failed")
    args = ap.parse_args()
    req_data = load_yaml("requirements.yaml")
    meta, areas, reqs = req_data["meta"], req_data["areas"], req_data["requirements"]
    tcs = load_yaml("test_cases.yaml")["test_cases"]
    anomalies = (load_yaml("anomalies.yaml") or {}).get("anomalies", []) \
        if (SPECS / "anomalies.yaml").exists() else []
    results = load_results()
    errors = link(reqs, tcs, results)
    DOCS.mkdir(exist_ok=True)
    write_srs(meta, areas, reqs)
    write_test_spec(meta, tcs)
    write_trace(meta, reqs, tcs, results)
    write_report(meta, reqs, tcs, results, anomalies, errors)
    write_html(meta, reqs, results)
    write_protocol(meta, tcs)
    summary = {"requirements": len(reqs), "test_cases": len(tcs),
               "tools_with_results": list(results), "gate_errors": errors,
               "tc_status": {s: sum(1 for t in tcs if t["status"] == s)
                             for s in ("passed", "failed", "manual", "not run")}}
    print(json.dumps(summary, indent=2))
    failed = [t for t in tcs if t["status"] == "failed"]
    if errors or (args.require_pass and failed):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
