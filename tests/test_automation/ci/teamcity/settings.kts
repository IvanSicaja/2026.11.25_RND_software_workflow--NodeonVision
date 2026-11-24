// =============================================================================
// TeamCity Kotlin DSL - Nodeon verification (same 3 stages as azure-pipelines.yml)
// Versioned settings: Project > Versioned Settings > "Use settings from VCS".
// TeamCity Professional (free): up to 100 build configurations and 3 agents.
// =============================================================================
import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildFeatures.XmlReport
import jetbrains.buildServer.configs.kotlin.buildFeatures.xmlReport
import jetbrains.buildServer.configs.kotlin.buildSteps.script
import jetbrains.buildServer.configs.kotlin.triggers.vcs

version = "2024.03"

project {
    buildType(LinuxSuites)
    buildType(WindowsReqnroll)
    buildType(Report)
}

object LinuxSuites : BuildType({
    name = "1 Linux: pytest, pytest-bdd, Behave, Playwright"
    vcs { root(DslContext.settingsRoot) }
    steps {
        script {
            name = "Run all Linux suites in Docker"
            scriptContent = """
                docker build -t nodeon-tests -f tests/test_automation/Dockerfile .
                docker run --rm --user "${'$'}(id -u):${'$'}(id -g)" -e HOME=/tmp \
                  -v "${'$'}PWD/test_automation/reports:/work/test_automation/reports" \
                  -v "${'$'}PWD/test_automation/docs:/work/test_automation/docs" nodeon-tests
            """.trimIndent()
        }
    }
    features {
        xmlReport { reportType = XmlReport.XmlReportType.JUNIT; rules = "tests/test_automation/reports/**/*.xml" }
    }
    requirements { equals("teamcity.agent.jvm.os.family", "Linux") }
    artifactRules = "tests/test_automation/reports => reports-linux.zip"
    triggers { vcs { } }
})

object WindowsReqnroll : BuildType({
    name = "2 Windows: Reqnroll + FlaUI (black-box)"
    vcs { root(DslContext.settingsRoot) }
    steps {
        script {
            name = "dotnet test"
            workingDir = "tests/test_automation"
            scriptContent = """
                python -m pip install -r ..\..\draft_requirements_python-3.11.9.txt
                dotnet test dotnet\Nodeon.SystemTests --filter "Category!=python_only" --logger "trx;LogFileName=reqnroll.trx" --results-directory reports\reqnroll
            """.trimIndent()
        }
    }
    features {
        xmlReport { reportType = XmlReport.XmlReportType.TRX; rules = "tests/test_automation/reports/reqnroll/*.trx" }
    }
    // The agent must run in an interactive desktop session (not as a Windows service).
    requirements { equals("teamcity.agent.jvm.os.family", "Windows") }
    artifactRules = "tests/test_automation/reports/reqnroll => reports-windows.zip"
    triggers { vcs { } }
})

object Report : BuildType({
    name = "3 Report: traceability + quality gate"
    vcs { root(DslContext.settingsRoot) }
    dependencies {
        artifacts(LinuxSuites) { artifactRules = "reports-linux.zip!** => tests/test_automation/reports" }
        artifacts(WindowsReqnroll) { artifactRules = "reports-windows.zip!** => tests/test_automation/reports/reqnroll" }
        snapshot(LinuxSuites) { onDependencyFailure = FailureAction.ADD_PROBLEM }
        snapshot(WindowsReqnroll) { onDependencyFailure = FailureAction.ADD_PROBLEM }
    }
    steps {
        script {
            name = "Documents, Playwright check of the report, quality gate"
            workingDir = "tests/test_automation"
            scriptContent = """
                python -m pip install -r requirements-test.txt
                python tools/generate_docs.py > reports/generate_1.json
                python -m pytest python/web_tests -q --junitxml=reports/junit-playwright.xml
                python tools/generate_docs.py --require-pass
            """.trimIndent()
        }
    }
    requirements { equals("teamcity.agent.jvm.os.family", "Linux") }
    artifactRules = """
        tests/test_automation/docs => verification-documents.zip
        tests/test_automation/reports => reports-all.zip
    """.trimIndent()
})
