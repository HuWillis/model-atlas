[CmdletBinding()]
param([string]$OllamaPath = 'D:\Software\Ollama\ollama.exe')
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $OllamaPath)) { throw "Ollama not found: $OllamaPath" }
Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 5 | Out-Null
& $OllamaPath pull qwen3.5:4b
if ($LASTEXITCODE -ne 0) { throw 'Model download failed. Rerun this script to resume.' }
$modelFile = Join-Path (Split-Path -Parent $PSScriptRoot) 'models\qwen3.5-4b\Modelfile'
& $OllamaPath create qwen3.5-coding:4b -f $modelFile
if ($LASTEXITCODE -ne 0) { throw 'Coding model profile creation failed.' }
& $OllamaPath show qwen3.5-coding:4b
