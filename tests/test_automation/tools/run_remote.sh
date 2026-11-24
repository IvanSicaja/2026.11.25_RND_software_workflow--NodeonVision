#!/usr/bin/env bash
# =============================================================================
# Run the test stack on a remote Linux test machine over SSH and fetch the
# results - typical for a lab PC next to an instrument or a shared test rig.
#
#   tools/run_remote.sh tester@lab-pc-07 [git-ref]
#
# What happens:  1. ssh: clone/update the repository at the given commit
#                2. ssh: run the suite inside Docker (or directly if no Docker)
#                3. scp: copy reports/ and docs/ back here
# Why a commit (git ref) and not "copy my folder": the test report must name
# exactly WHICH software version was tested (IEC 62304 configuration mgmt).
# Needs: SSH key login (ssh-copy-id), git + docker (or python) on the target.
# =============================================================================
set -euo pipefail
TARGET="${1:?usage: run_remote.sh user@host [git-ref]}"
REF="${2:-$(git rev-parse HEAD)}"
REPO="${NODEON_REPO:-$(git config --get remote.origin.url)}"
REMOTE_DIR="${NODEON_REMOTE_DIR:-nodeon-test}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

echo "==== testing commit $REF on $TARGET"
STATUS=0
ssh -o BatchMode=yes "$TARGET" bash -s -- "$REPO" "$REF" "$REMOTE_DIR" <<'REMOTE' || STATUS=$?
set -euo pipefail
REPO="$1"; REF="$2"; DIR="$3"
[ -d "$DIR/.git" ] || git clone --quiet "$REPO" "$DIR"
cd "$DIR"
git fetch --quiet --all --tags
git checkout --quiet --force "$REF"
git clean -fdxq -e tests/test_automation/reports
if command -v docker >/dev/null; then
  docker build -q -t nodeon-tests -f tests/test_automation/Dockerfile . >/dev/null
  docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD/test_automation/reports:/work/test_automation/reports" \
                  -v "$PWD/test_automation/docs:/work/test_automation/docs" nodeon-tests
else
  bash tests/test_automation/tools/run_all.sh
fi
REMOTE
mkdir -p "$HERE/reports/remote" "$HERE/docs/remote"
scp -rq "$TARGET:$REMOTE_DIR/test_automation/reports/." "$HERE/reports/remote/"
scp -rq "$TARGET:$REMOTE_DIR/test_automation/docs/." "$HERE/docs/remote/"
echo "==== results copied to reports/remote and docs/remote (exit $STATUS)"
exit $STATUS
