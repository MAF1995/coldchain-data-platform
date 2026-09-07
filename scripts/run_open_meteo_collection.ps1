param(
    [string]$SiteId = "042",
    [double]$Latitude = 45.70482,
    [double]$Longitude = 4.88772,
    [switch]$SkipPostgresLoad
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Push-Location $ProjectRoot
try {
    & $Python .\src\collect_open_meteo.py `
        --site-id $SiteId `
        --latitude $Latitude `
        --longitude $Longitude

    if (-not $SkipPostgresLoad) {
        & $Python .\src\load_open_meteo_to_postgres.py
    }
}
finally {
    Pop-Location
}
