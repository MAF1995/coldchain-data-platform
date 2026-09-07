param(
    [int]$DurationSeconds = 7200,
    [string]$Broker = "test.mosquitto.org",
    [string]$BrokerAlias = "mqtt-recette-01",
    [int]$Port = 1883
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"
$PidDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$env:PYTHONIOENCODING = "utf-8"

$ListenerArgs = @(
    "-u",
    "src\mqtt_raw_listener.py",
    "--broker", $Broker,
    "--broker-alias", $BrokerAlias,
    "--port", "$Port",
    "--duration-seconds", "$DurationSeconds"
)

$PublisherArgs = @(
    "-u",
    "src\publish_machine_signals.py",
    "--broker", $Broker,
    "--port", "$Port",
    "--duration-seconds", "$DurationSeconds",
    "--interval-seconds", "5"
)

$Listener = Start-Process -FilePath $Python -ArgumentList $ListenerArgs -WorkingDirectory $ProjectRoot -RedirectStandardOutput (Join-Path $LogDir "mqtt_listener.log") -RedirectStandardError (Join-Path $LogDir "mqtt_listener.err.log") -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 3
$Publisher = Start-Process -FilePath $Python -ArgumentList $PublisherArgs -WorkingDirectory $ProjectRoot -RedirectStandardOutput (Join-Path $LogDir "mqtt_publisher.log") -RedirectStandardError (Join-Path $LogDir "mqtt_publisher.err.log") -PassThru -WindowStyle Hidden

@{
    started_at = (Get-Date).ToString("o")
    broker = $BrokerAlias
    port = $Port
    duration_seconds = $DurationSeconds
    listener_pid = $Listener.Id
    publisher_pid = $Publisher.Id
} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $PidDir "mqtt_capture_pids.json")

Write-Host "Capture MQTT lancée pour $DurationSeconds secondes"
Write-Host "Listener PID : $($Listener.Id)"
Write-Host "Publisher PID: $($Publisher.Id)"
Write-Host "Logs: $LogDir"
Write-Host "Base: data\raw\mqtt_raw.db"
