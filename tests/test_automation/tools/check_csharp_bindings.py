"""
Static check of the C# Reqnroll bindings - runs on Linux without .NET.

Every step of every @desktop scenario must match exactly one [StepDefinition]
Cucumber expression in dotnet/**/Steps/*.cs. This is the same check Reqnroll
does at run time ("No matching step definition found"), moved to the
pipeline's first minute (fail fast). Exit code 1 = missing or ambiguous step.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cucumber_to_regex(expr: str) -> re.Pattern:
    out = re.escape(expr)
    out = out.replace(r"\{string\}", r'"[^"]*"').replace(r"\{int\}", r"-?\d+")
    return re.compile(f"^{out}$")


def bindings():
    found = []
    for cs in (ROOT / "dotnet").rglob("Steps/*.cs"):
        for m in re.finditer(r'\[StepDefinition\("((?:[^"\\]|\\.)*)"\)\]', cs.read_text(encoding="utf-8")):
            found.append((m.group(1), cucumber_to_regex(m.group(1))))
    return found


def steps():
    """(feature, scenario, step text) of all scenarios that run on Windows."""
    for feature in sorted((ROOT / "features").glob("*.feature")):
        tags, scenario = [], None
        for raw in feature.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("@"):
                tags = line.split()
            elif line.startswith(("Scenario", "Background")):
                scenario = line
                skip = "@python_only" in tags
                tags = []
                if skip:
                    scenario = None
            elif scenario and re.match(r"^(Given|When|Then|And|But) ", line):
                yield feature.name, scenario, re.sub(r"^\w+ ", "", line)


def main() -> int:
    b = bindings()
    errors = 0
    checked = 0
    for feature, scenario, text in steps():
        if "<" in text:                                   # outline: test with a sample value
            text = re.sub(r"<[^>]+>", "1", text).replace('"1"', '"Alt+1"')
        hits = [e for e, rx in b if rx.match(text)]
        checked += 1
        if len(hits) != 1:
            errors += 1
            print(f"{feature} | {scenario}\n   step: {text}\n   matches: {hits or 'NONE'}")
    print(f"{checked} desktop steps checked against {len(b)} C# bindings: "
          f"{'OK' if not errors else f'{errors} problem(s)'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
