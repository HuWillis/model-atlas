[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)][int]$Port = 18765,
    [string]$OllamaPath,
    [string]$ModelsDirectory,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$url = "http://127.0.0.1:$Port"
try { $existing = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 2 } catch { $existing = $null }
if ($existing -and $existing.app -eq 'model-atlas') {
    Write-Output "Model Atlas is already running: $url"
    if (-not $NoBrowser) { Start-Process $url }
    return
}
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw 'Python 3.10+ is required. Install Python, then reopen this launcher.' }
& $python.Source -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ is required.' }
$runtime = Join-Path $root 'work\console'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$script = Join-Path $root 'console\server.py'
$arguments = @('-u', ('"' + $script + '"'), '--port', $Port)
if ($OllamaPath) {
    if (-not (Test-Path -LiteralPath $OllamaPath -PathType Leaf)) { throw 'OllamaPath does not exist.' }
    $arguments += @('--ollama-path', ('"' + $OllamaPath + '"'))
}
if ($ModelsDirectory) {
    if (-not (Test-Path -LiteralPath $ModelsDirectory -PathType Container)) { throw 'ModelsDirectory does not exist.' }
    $arguments += @('--models-dir', ('"' + $ModelsDirectory + '"'))
}
$process = Start-Process -FilePath $python.Source -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'server.stdout.log') -RedirectStandardError (Join-Path $runtime 'server.stderr.log')
for ($i = 0; $i -lt 30; $i++) {
    if ($process.HasExited) { throw 'Console startup failed. Check work\console\server.stderr.log (the port may be occupied).' }
    try {
        $ready = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 1
        if ($ready.app -eq 'model-atlas') {
            Write-Output "Model Atlas is running: $url"
            if (-not $NoBrowser) { Start-Process $url }
            return
        }
    } catch { }
    Start-Sleep -Milliseconds 300
}
throw 'Console did not become ready. Check work\console\server.stderr.log.'
