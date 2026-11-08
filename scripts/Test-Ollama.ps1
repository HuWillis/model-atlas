[CmdletBinding()]
param([string]$Model = 'qwen3.5-coding:4b')
$ErrorActionPreference = 'Stop'
$baseUrl = 'http://127.0.0.1:11434'
$version = Invoke-RestMethod -Uri "$baseUrl/api/version" -TimeoutSec 5
$show = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/show" -ContentType 'application/json' -Body (@{ model = $Model } | ConvertTo-Json) -TimeoutSec 15
if ('tools' -notin $show.capabilities) { throw 'This model does not report tool-calling support.' }
$body = @{
    model = $Model
    messages = @(@{role='user';content='Reply with the single word READY.'})
    think = $false
    stream = $false
    options = @{num_predict=32}
} | ConvertTo-Json -Depth 6
$response = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/chat" -ContentType 'application/json' -Body $body -TimeoutSec 300
if (-not $response.done -or [string]::IsNullOrWhiteSpace($response.message.content)) { throw 'No completed text response.' }
$tokensPerSecond = if ($response.eval_duration -gt 0) { [Math]::Round($response.eval_count * 1e9 / $response.eval_duration, 2) } else { $null }
[pscustomobject]@{
    OllamaVersion = $version.version
    Model = $Model
    Capabilities = $show.capabilities -join ', '
    Parameters = $show.parameters
    Response = $response.message.content
    TotalSeconds = [Math]::Round($response.total_duration / 1e9, 2)
    GeneratedTokens = $response.eval_count
    TokensPerSecond = $tokensPerSecond
}
Invoke-RestMethod -Uri "$baseUrl/api/ps" -TimeoutSec 5 | ConvertTo-Json -Depth 8
