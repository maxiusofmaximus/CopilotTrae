param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Command
)

function Test-IsLocalAiAgentCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $leaf = [System.IO.Path]::GetFileName($Name).ToLowerInvariant()
    return $leaf -in @("local-ai-agent", "local-ai-agent.exe", "local-ai-agent.cmd", "local-ai-agent.ps1")
}

function Test-IsMiddlewareCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $scriptPath = [System.IO.Path]::GetFullPath($PSCommandPath)
    $scriptLeaf = [System.IO.Path]::GetFileName($scriptPath).ToLowerInvariant()
    $candidateLeaf = [System.IO.Path]::GetFileName($Name).ToLowerInvariant()
    if ($candidateLeaf -eq "middleware" -or $candidateLeaf -eq $scriptLeaf) {
        return $true
    }

    try {
        $candidatePath = [System.IO.Path]::GetFullPath($Name)
        return $candidatePath.Equals($scriptPath, [System.StringComparison]::OrdinalIgnoreCase)
    } catch {
        return $false
    }
}

function Exit-With-NoFallback {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ExitCode,
        [string]$CommandName,
        [bool]$CommandNotFound = $false
    )

    if ($CommandNotFound) {
        Write-Error ("Command not found: " + $CommandName)
    }
    exit $ExitCode
}

$guardName = "LOCAL_AI_AGENT_MIDDLEWARE_ACTIVE"
$fallbackGuardActive = [Environment]::GetEnvironmentVariable($guardName) -eq "1"

if (-not $Command -or $Command.Count -eq 0) {
    Write-Error "Usage: ./scripts/powershell/middleware.ps1 <command> [args...]"
    exit 1
}

$commandName = $Command[0]
$remainingArgs = @()
if ($Command.Count -gt 1) {
    $remainingArgs = $Command[1..($Command.Count - 1)]
}

if (Test-IsMiddlewareCommand -Name $commandName) {
    Write-Error "Refusing recursive middleware invocation."
    exit 1
}

$resolvedCommand = Get-Command $commandName -ErrorAction SilentlyContinue
$shouldFallback = $false
if ($null -ne $resolvedCommand) {
    & $commandName @remainingArgs
    $exitCode = if ($null -ne $LASTEXITCODE) { [int]$LASTEXITCODE } elseif ($?) { 0 } else { 1 }
    if ($exitCode -eq 0) {
        exit 0
    }
    if ($fallbackGuardActive -or (Test-IsLocalAiAgentCommand -Name $commandName)) {
        Exit-With-NoFallback -ExitCode $exitCode -CommandName $commandName
    }
    $shouldFallback = $true
} else {
    if ($fallbackGuardActive -or (Test-IsLocalAiAgentCommand -Name $commandName)) {
        Exit-With-NoFallback -ExitCode 1 -CommandName $commandName -CommandNotFound $true
    }
    $shouldFallback = $true
}

if (-not $shouldFallback) {
    exit 0
}

$cwd = (Get-Location).Path
$rawCommand = [string]::Join(' ', $Command)
$previousGuard = [Environment]::GetEnvironmentVariable($guardName)
[Environment]::SetEnvironmentVariable($guardName, "1")
try {
    $routeJson = & local-ai-agent route --text $rawCommand --shell powershell --cwd $cwd --snapshot-version generated
} finally {
    [Environment]::SetEnvironmentVariable($guardName, $previousGuard)
}

if (-not $routeJson) {
    Write-Error "Router did not return a response."
    exit 1
}

try {
    $route = $routeJson | ConvertFrom-Json
} catch {
    Write-Error "Failed to parse router JSON."
    exit 1
}

Write-Host ("Router route: " + $route.route)
$previousGuard = [Environment]::GetEnvironmentVariable($guardName)
[Environment]::SetEnvironmentVariable($guardName, "1")
try {
    & local-ai-agent exec --shell powershell --cwd $cwd @Command
} finally {
    [Environment]::SetEnvironmentVariable($guardName, $previousGuard)
}
exit $LASTEXITCODE
