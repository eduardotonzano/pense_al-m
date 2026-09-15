param(
    [ValidateSet("DryRun", "Commit")]
    [string]$Mode = "DryRun"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

$PythonPath = Join-Path $env:USERPROFILE "debenture-venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Python nao encontrado: $PythonPath"
}

$ConfigPath = Join-Path $ProjectRoot "config\collection.production.json"

if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Configuracao nao encontrada: $ConfigPath"
}

$PythonScript = Join-Path $ProjectRoot "scripts\run_scheduled_collection.py"

if (-not (Test-Path -LiteralPath $PythonScript)) {
    throw "Script nao encontrado: $PythonScript"
}

$LogDirectory = Join-Path $ProjectRoot "logs"

if (-not (Test-Path -LiteralPath $LogDirectory)) {
    New-Item `
        -ItemType Directory `
        -Path $LogDirectory `
        -Force | Out-Null
}

$LogFile = Join-Path $LogDirectory "scheduled_collection.log"

"" | Out-File `
    -FilePath $LogFile `
    -Append `
    -Encoding utf8

("==== INICIO " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " ====") |
    Out-File `
        -FilePath $LogFile `
        -Append `
        -Encoding utf8

$Arguments = @(
    $PythonScript
    "--config"
    $ConfigPath
)

if ($Mode -eq "Commit") {
    $Arguments += "--commit"
}
else {
    $Arguments += "--dry-run"
}

Push-Location $ProjectRoot

try {

    $Output = & $PythonPath @Arguments 2>&1

    $ExitCode = $LASTEXITCODE

    $Output | Out-File `
        -FilePath $LogFile `
        -Append `
        -Encoding utf8

    ("ExitCode=" + $ExitCode) |
        Out-File `
            -FilePath $LogFile `
            -Append `
            -Encoding utf8

    exit $ExitCode
}
catch {

    ("ERRO: " + $_.Exception.Message) |
        Out-File `
            -FilePath $LogFile `
            -Append `
            -Encoding utf8

    Write-Error $_.Exception.Message

    exit 1
}
finally {

    Pop-Location

    ("==== FIM " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " ====") |
        Out-File `
            -FilePath $LogFile `
            -Append `
            -Encoding utf8
}