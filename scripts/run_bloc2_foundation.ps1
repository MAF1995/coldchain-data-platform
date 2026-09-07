param(
    [switch]$SkipNotebook
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Dbt = Join-Path $ProjectRoot ".venv\Scripts\dbt.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Environnement Python introuvable : $Python"
}
if (-not (Test-Path -LiteralPath $Dbt)) {
    throw "Exécutable dbt introuvable : $Dbt"
}

Push-Location $ProjectRoot
try {
    docker compose up -d postgres

    $PostgresReady = $false
    for ($Attempt = 1; $Attempt -le 24; $Attempt++) {
        docker compose exec -T postgres pg_isready `
            -U pharma_data `
            -d pharma_analytics *> $null
        if ($LASTEXITCODE -eq 0) {
            $PostgresReady = $true
            break
        }
        Start-Sleep -Seconds 2
    }

    if (-not $PostgresReady) {
        throw "PostgreSQL n'est pas prêt après 48 secondes."
    }

    $env:PGHOST = "localhost"
    $env:PGPORT = "55432"
    $env:PGDATABASE = "pharma_analytics"
    $env:PGUSER = "pharma_data"
    $env:PGPASSWORD = "pharma_local_only"
    $env:DBT_SCHEMA = "analytics"

    & $Python .\src\load_raw_to_postgres.py
    if ($LASTEXITCODE -ne 0) {
        throw "Le chargement PostgreSQL a échoué."
    }

    & $Dbt seed `
        --project-dir .\dbt `
        --profiles-dir .\dbt
    if ($LASTEXITCODE -ne 0) {
        throw "dbt seed a échoué."
    }

    & $Dbt run `
        --project-dir .\dbt `
        --profiles-dir .\dbt
    if ($LASTEXITCODE -ne 0) {
        throw "dbt run a échoué."
    }

    & $Dbt test `
        --project-dir .\dbt `
        --profiles-dir .\dbt
    if ($LASTEXITCODE -ne 0) {
        throw "dbt test a échoué."
    }

    if (-not $SkipNotebook) {
        & $Python .\scripts\create_bloc2_quality_notebook.py
        if ($LASTEXITCODE -ne 0) {
            throw "La création du notebook a échoué."
        }

        & $Python -m jupyter nbconvert `
            --to notebook `
            --execute `
            --inplace `
            --ExecutePreprocessor.timeout=180 `
            .\notebooks\bloc2_qualite_donnees.ipynb
        if ($LASTEXITCODE -ne 0) {
            throw "L'exécution du notebook a échoué."
        }
    }

    Write-Output "Socle du bloc II exécuté avec succès."
}
finally {
    Pop-Location
}
