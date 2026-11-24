# =============================================================================
# Reproducible Linux test environment for Nodeon (everything except the
# Windows-only Reqnroll/FlaUI suite).
#
#   docker build -t nodeon-tests -f tests/test_automation/Dockerfile .
#   docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
#              -v "$PWD/test_automation/reports:/work/test_automation/reports" \
#              -v "$PWD/test_automation/docs:/work/test_automation/docs" nodeon-tests
#
# Why Docker: every run (laptop, CI agent, auditor) uses the SAME OS, Python,
# Qt libraries and browser -> "works on my machine" cannot happen and the
# environment is documented as code (needed for the test report / IQ).
# =============================================================================
FROM mcr.microsoft.com/playwright/python:v1.56.0-noble

# Qt (PySide6) needs these X/GL libraries even when it draws off-screen.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libdbus-1-3 libfontconfig1 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
COPY draft_requirements_python-3.11.9.txt ./draft_requirements_python-3.11.9.txt
COPY tests/test_automation/requirements-test.txt ./test_automation/requirements-test.txt
RUN pip install --no-cache-dir -r tests/test_automation/requirements-test.txt

COPY . .
ENV QT_QPA_PLATFORM=offscreen \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
# Non-root user: tests must not need administrator rights.
# (With mounted result folders, run as YOUR user id: --user "$(id -u):$(id -g)".)
RUN useradd -m tester && chown -R tester /work
USER tester
CMD ["bash", "tests/test_automation/tools/run_all.sh"]
