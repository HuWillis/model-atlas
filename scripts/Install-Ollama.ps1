[CmdletBinding()]
param(
    [string]$InstallerPath,
    [string]$InstallDirectory = 'D:\Software\Ollama',
    [string]$ModelsDirectory = 'D:\AI\Models'
)

$ErrorActionPreference = 'Stop'
$version = '0.40.15'
$expectedHash = '106ef3d2a02437810fba6f574914b1413c512ea84ddd4f184c8e7f434b6f5564'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$workDirectory = Join-Path $repositoryRoot 'work'
New-Item -ItemType Directory -Path $workDirectory -Force | Out-Null

if (-not $InstallerPath) {
    $InstallerPath = Join-Path $workDirectory "OllamaSetup-$version.exe"
    if (-not (Test-Path -LiteralPath $InstallerPath)) {
        Invoke-WebRequest -Uri "https://github.com/ollama/ollama/releases/download/v$version/OllamaSetup.exe" -OutFile $InstallerPath
    }
}

$InstallerPath = (Resolve-Path -LiteralPath $InstallerPath).Path
if ((Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256).Hash -ne $expectedHash) {
    throw 'Installer SHA256 does not match the pinned official release.'
}
$signature = Get-AuthenticodeSignature -LiteralPath $InstallerPath
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Ollama') {
    throw 'Installer does not have a valid Ollama publisher signature.'
}
if ($InstallDirectory.Contains('"') -or -not [IO.Path]::IsPathRooted($InstallDirectory)) {
    throw 'InstallDirectory must be an absolute path without quote characters.'
}
if (-not [IO.Path]::IsPathRooted($ModelsDirectory)) {
    throw 'ModelsDirectory must be an absolute path.'
}

New-Item -ItemType Directory -Path $ModelsDirectory -Force | Out-Null
[Environment]::SetEnvironmentVariable('OLLAMA_MODELS', $ModelsDirectory, 'User')
$env:OLLAMA_MODELS = $ModelsDirectory
$logPath = Join-Path $workDirectory 'ollama-install.log'
$installerArguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=`"$InstallDirectory`"", "/LOG=`"$logPath`"")
$installer = Start-Process -FilePath $InstallerPath -ArgumentList $installerArguments -WindowStyle Hidden -PassThru
$installer.WaitForExit()
if ($installer.ExitCode -notin 0, 3010) {
    throw "Ollama installer returned $($installer.ExitCode). See $logPath"
}
$ollama = Join-Path $InstallDirectory 'ollama.exe'
if (-not (Test-Path -LiteralPath $ollama)) {
    throw "Ollama executable not found in $InstallDirectory. See $logPath"
}
Write-Output "Installed Ollama $version in $InstallDirectory"
Write-Output "Model directory: $ModelsDirectory"
Write-Output 'Reopen your terminal before using the ollama command from PATH.'
