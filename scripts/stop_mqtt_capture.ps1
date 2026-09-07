$ErrorActionPreference = "SilentlyContinue"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$PidFile = Join-Path $ProjectRoot "logs\mqtt_capture_pids.json"

if (!(Test-Path $PidFile)) {
    Write-Host "Aucun fichier PID trouvé."
    exit 0
}

$Data = Get-Content -Raw -Encoding UTF8 $PidFile | ConvertFrom-Json
foreach ($ProcId in @($Data.listener_pid, $Data.publisher_pid)) {
    if ($ProcId) {
        $Process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcId"
        $CommandLine = $Process.CommandLine
        $IsProjectProcess = $CommandLine -and
            $CommandLine.Contains($ProjectRoot.Path) -and
            ($CommandLine.Contains("mqtt_raw_listener.py") -or $CommandLine.Contains("publish_machine_signals.py"))

        if ($IsProjectProcess) {
            Stop-Process -Id $ProcId -Force
            Write-Host "Process stoppé: $ProcId"
        }
        else {
            Write-Host "PID ignoré, il ne correspond pas à une capture MQTT du projet: $ProcId"
        }
    }
}
