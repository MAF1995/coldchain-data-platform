$ErrorActionPreference = "SilentlyContinue"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$PidFile = Join-Path $ProjectRoot "logs\mqtt_real_capture_pids.json"

if (!(Test-Path $PidFile)) {
    Write-Host "Aucun fichier PID réel trouvé."
    exit 0
}

$Data = Get-Content -Raw -Encoding UTF8 $PidFile | ConvertFrom-Json
foreach ($Listener in $Data.listeners) {
    if ($Listener.pid) {
        $Process = Get-CimInstance Win32_Process -Filter "ProcessId = $($Listener.pid)"
        $CommandLine = $Process.CommandLine
        $IsProjectProcess = $CommandLine -and
            $CommandLine.Contains($ProjectRoot.Path) -and
            $CommandLine.Contains("mqtt_raw_listener.py")

        if ($IsProjectProcess) {
            Stop-Process -Id $Listener.pid -Force
            Write-Host "Process stoppé: $($Listener.name) PID=$($Listener.pid)"
        }
        else {
            Write-Host "PID ignoré, il ne correspond pas à une écoute MQTT du projet: $($Listener.name) PID=$($Listener.pid)"
        }
    }
}
