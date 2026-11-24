#!/usr/bin/env bash
# =============================================================================
# Runs the complete Nodeon test stack (Linux / macOS / Docker / CI agents)
# and generates the documentation + traceability report.
#
#   ./test_automation/tools/run_all.sh            # everything
#   ./test_automation/tools/run_all.sh --quick    # skip the developer suite
#
# Order matters: the report is generated first, then Playwright tests the
# report, then the report is generated again including the Playwright results.
# Exit code 0 only if every suite passed and the quality gate is green.
# =============================================================================
set -u
cd "$(dirname "$0")/.."                      # -> tests/test_automation/
TA="$(pwd)"
PROJECT="$(cd ../.. && pwd)"                 # project root (main/, tests/)
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
export PYTHONDONTWRITEBYTECODE=1
mkdir -p reports && find reports -mindepth 1 -delete   # works for a mounted folder too
mkdir -p reports/behave
STATUS=0
step() { echo; echo "==== $1"; }
run()  { "$@" || STATUS=1; }

step "0/6 Static checks: every Gherkin step of the Windows suite has a C# binding"
run python tools/check_csharp_bindings.py

if [ "${1:-}" != "--quick" ]; then
  step "1/6 Developer unit + GUI tests (pytest runs the unittest suites tests/test_*.py)"
  (cd "$PROJECT" && run python -m pytest tests/test_*.py -q -p no:cacheprovider \
      --junitxml="$TA/reports/junit-dev.xml") || STATUS=1
fi

step "2/6 System tests (pytest)"
run python -m pytest python/system_tests -q --junitxml=reports/junit-system.xml

step "3/6 BDD scenarios with pytest-bdd"
run python -m pytest python/bdd_pytest -q --junitxml=reports/junit-pytest-bdd.xml

step "4/6 The same BDD scenarios with Behave"
run python -m behave features --junit --junit-directory reports/behave -f progress

step "5/6 Generate documents + report, then test the report with Playwright"
python tools/generate_docs.py > reports/generate_1.json || true
run python -m pytest python/web_tests -q --junitxml=reports/junit-playwright.xml

step "6/6 Final documents, traceability report and quality gate"
run python tools/generate_docs.py --require-pass

echo
if [ $STATUS -eq 0 ]; then echo "RESULT: ALL GREEN"; else echo "RESULT: FAILURES - see output above and docs/06_Test_Report.md"; fi
exit $STATUS
