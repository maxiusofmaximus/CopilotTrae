param()

$ErrorActionPreference = "Stop"

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$middlewarePath = Join-Path $repoRoot "scripts\powershell\middleware.ps1"

function Assert-StepSucceeded {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ExitCode,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if ($ExitCode -ne 0) {
        throw $Message
    }
}

Push-Location $repoRoot
try {
    Write-Host "==> Running pytest -q"
    & pytest -q
    Assert-StepSucceeded -ExitCode $LASTEXITCODE -Message "Smoke check failed: pytest -q returned a non-zero exit code."

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw "Smoke check failed: python is not available in PATH."
    }

    $smokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("local-ai-agent-smoke-" + [System.Guid]::NewGuid().ToString("N"))
    $binDir = Join-Path $smokeRoot "bin"
    $logsDir = Join-Path $smokeRoot "logs"
    $driverPath = Join-Path $smokeRoot "local_ai_agent_driver.py"
    $localAiShim = Join-Path $binDir "local-ai-agent.cmd"
    $ghShim = Join-Path $binDir "gh.cmd"

    New-Item -ItemType Directory -Force -Path $binDir | Out-Null
    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

    @"
from __future__ import annotations

import sys

sys.path.insert(0, r"$($repoRoot.Replace('\', '\\'))\src")

from local_ai_agent.cli import main
from local_ai_agent.config import Settings
from local_ai_agent.runtime import build_runtime
import local_ai_agent.runtime as runtime_module

runtime_module.build_multimodal_input_processor = lambda settings: object()
settings = Settings.from_env()
runtime = build_runtime(settings, stdin=sys.stdin, stdout=sys.stdout)
raise SystemExit(main(sys.argv[1:], runtime=runtime, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr))
"@ | Set-Content -Path $driverPath -Encoding UTF8

    @"
@echo off
"$($pythonCommand.Source)" "$driverPath" %*
exit /b %ERRORLEVEL%
"@ | Set-Content -Path $localAiShim -Encoding UTF8

    @"
@echo off
echo gh version 9.9.9
exit /b 0
"@ | Set-Content -Path $ghShim -Encoding UTF8

    $previousPath = $env:PATH
    $previousProvider = $env:LOCAL_AI_AGENT_PROVIDER
    $previousSession = $env:LOCAL_AI_AGENT_SESSION_ID
    $previousLogsDir = $env:LOCAL_AI_AGENT_LOGS_DIR
    $previousConfirm = $env:LOCAL_AI_AGENT_CONFIRM_BEFORE_COPY

    try {
        $env:PATH = "$binDir$([System.IO.Path]::PathSeparator)$previousPath"
        $env:LOCAL_AI_AGENT_PROVIDER = "stub"
        $env:LOCAL_AI_AGENT_SESSION_ID = "smoke-e2e"
        $env:LOCAL_AI_AGENT_LOGS_DIR = $logsDir
        $env:LOCAL_AI_AGENT_CONFIRM_BEFORE_COPY = "false"

        Write-Host "==> Running middleware E2E with stub provider"
        $e2eOutput = "y`n" | & pwsh -NoProfile -File $middlewarePath github.cli --version 2>&1
        $e2eExitCode = $LASTEXITCODE
        $e2eText = ($e2eOutput | Out-String)
        Write-Host $e2eText.TrimEnd()

        Assert-StepSucceeded -ExitCode $e2eExitCode -Message "Smoke check failed: middleware E2E returned a non-zero exit code."
        if ($e2eText -notmatch "Router route: command_fix") {
            throw "Smoke check failed: middleware E2E did not emit the expected router route."
        }
        if ($e2eText -notmatch "Executed suggested command: gh --version") {
            throw "Smoke check failed: middleware E2E did not execute the expected suggested command."
        }
        if ($e2eText -notmatch "gh version 9\.9\.9") {
            throw "Smoke check failed: middleware E2E did not print the expected gh stub output."
        }

        $routerLog = Join-Path $logsDir "router\smoke-e2e.jsonl"
        if (-not (Test-Path $routerLog)) {
            throw "Smoke check failed: router log was not created."
        }
    } finally {
        $env:PATH = $previousPath
        $env:LOCAL_AI_AGENT_PROVIDER = $previousProvider
        $env:LOCAL_AI_AGENT_SESSION_ID = $previousSession
        $env:LOCAL_AI_AGENT_LOGS_DIR = $previousLogsDir
        $env:LOCAL_AI_AGENT_CONFIRM_BEFORE_COPY = $previousConfirm
        if (Test-Path $smokeRoot) {
            Remove-Item -Recurse -Force $smokeRoot
        }
    }

    Write-Host "Smoke check passed."
} finally {
    Pop-Location
}
