param(
    [string]$MetabaseUrl = "http://localhost:3001",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

Set-Location $projectRoot
docker compose up -d postgres metabase-app-db metabase

$deadline = (Get-Date).AddMinutes(4)
do {
    try {
        $health = Invoke-RestMethod -Uri "$MetabaseUrl/api/health" -TimeoutSec 5
        if ($health.status -eq "ok") {
            Write-Host "Metabase est prêt : $MetabaseUrl" -ForegroundColor Green
            if (-not $NoBrowser) {
                Start-Process $MetabaseUrl
            }
            exit 0
        }
    }
    catch {
        Start-Sleep -Seconds 5
    }
} while ((Get-Date) -lt $deadline)

docker compose logs --tail 60 metabase
throw "Metabase n'a pas répondu dans le délai prévu."
