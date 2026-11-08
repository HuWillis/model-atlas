[CmdletBinding()]
param([string]$Model = 'qwen3.5-coding:4b')
$ErrorActionPreference = 'Stop'
Get-Command claude -ErrorAction Stop | Out-Null
$settingsPath = Join-Path $env:USERPROFILE '.claude\settings.json'
$settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
$localUrl = 'http://127.0.0.1:11434'
if ($settings.env.ANTHROPIC_BASE_URL -ne $localUrl) {
    throw 'Select the Ollama direct provider in CC Switch first.'
}
if ($env:ANTHROPIC_BASE_URL -and $env:ANTHROPIC_BASE_URL -ne $localUrl) {
    throw 'This terminal has a different ANTHROPIC_BASE_URL. Open a clean terminal.'
}
Invoke-RestMethod -Uri "$localUrl/api/version" -TimeoutSec 5 | Out-Null
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$runDirectory = Join-Path $repositoryRoot ('work\smoke-' + [Guid]::NewGuid().ToString('N').Substring(0, 10))
New-Item -ItemType Directory -Path $runDirectory | Out-Null
Copy-Item -LiteralPath (Join-Path $repositoryRoot 'examples\smoke\strings.py') -Destination $runDirectory
Copy-Item -LiteralPath (Join-Path $repositoryRoot 'examples\smoke\test_strings.py') -Destination $runDirectory
Set-Content -LiteralPath (Join-Path $runDirectory 'mcp.json') -Value '{"mcpServers":{}}' -Encoding utf8
$prompt = 'Read strings.py. Implement normalize_names(names) by editing strings.py: strip leading/trailing whitespace, discard empty strings, deduplicate using Unicode casefold, preserve the order and spelling of the first trimmed occurrence, and do not mutate the input list. Use Read then Edit. Modify only strings.py. Do not just show code in your answer. After editing, reply briefly.'
$arguments = @(
    '-p', $prompt, '--model', $Model,
    '--output-format', 'stream-json', '--verbose',
    '--tools', 'Read,Edit', '--allowedTools', 'Read,Edit',
    '--strict-mcp-config', '--mcp-config', (Join-Path $runDirectory 'mcp.json'),
    '--setting-sources', 'user', '--no-session-persistence',
    '--disable-slash-commands', '--no-chrome'
)
Write-Output "Smoke task directory: $runDirectory"
Push-Location $runDirectory
try {
    & claude @arguments 1> 'response.jsonl' 2> 'stderr.log'
    $claudeExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($claudeExitCode -ne 0) { throw "Claude Code returned $claudeExitCode. See $runDirectory\stderr.log and response.jsonl" }
$originalHash = (Get-FileHash -LiteralPath (Join-Path $repositoryRoot 'examples\smoke\strings.py')).Hash
$resultHash = (Get-FileHash -LiteralPath (Join-Path $runDirectory 'strings.py')).Hash
if ($originalHash -eq $resultHash) { throw "Claude Code did not edit strings.py. See $runDirectory\response.jsonl" }
Write-Output "File changed. Inspect $runDirectory\strings.py, then run python $runDirectory\test_strings.py"
Write-Output 'This script does not execute the generated Python code automatically.'
