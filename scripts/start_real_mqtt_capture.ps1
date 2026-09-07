param(
    [int]$DurationSeconds = 7200
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$env:PYTHONIOENCODING = "utf-8"

$BrokerConfigs = @(
    @{ Name = "recette01"; Broker = "test.mosquitto.org"; Alias = "mqtt-recette-01"; Port = 1883 },
    @{ Name = "recette02"; Broker = "broker.hivemq.com"; Alias = "mqtt-recette-02"; Port = 1883 }
)

$Started = @()

foreach ($Config in $BrokerConfigs) {
    $Args = @(
        "-u",
        "src\mqtt_raw_listener.py",
        "--broker", $Config.Broker,
        "--broker-alias", $Config.Alias,
        "--port", "$($Config.Port)",
        "--duration-seconds", "$DurationSeconds",
        "--topic", "pharma/production/site-042/#",
        "--topic", "pharma/coldchain/site-042/#"
    )

    $Process = Start-Process `
        -FilePath $Python `
        -ArgumentList $Args `
        -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput (Join-Path $LogDir "mqtt_listener_$($Config.Name).log") `
        -RedirectStandardError (Join-Path $LogDir "mqtt_listener_$($Config.Name).err.log") `
        -PassThru `
        -WindowStyle Hidden

    $Started += @{
        name = $Config.Name
        broker = $Config.Alias
        port = $Config.Port
        pid = $Process.Id
    }
}

@{
    started_at = (Get-Date).ToString("o")
    duration_seconds = $DurationSeconds
    mode = "real_brokers_no_local_publisher"
    topics = @("pharma/production/site-042/#", "pharma/coldchain/site-042/#")
    listeners = $Started
} | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $LogDir "mqtt_real_capture_pids.json")

Write-Host "Écoute MQTT réelle lancée pour $DurationSeconds secondes, sans publication locale."
foreach ($Item in $Started) {
    Write-Host "$($Item.name): $($Item.broker):$($Item.port) PID=$($Item.pid)"
}
Write-Host "Topics écoutés: pharma/production/site-042/# ; pharma/coldchain/site-042/#"
Write-Host "Base brute: data\raw\mqtt_raw.db"
Write-Host "Logs: $LogDir"
