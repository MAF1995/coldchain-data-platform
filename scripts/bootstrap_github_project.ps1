[CmdletBinding()]
param(
    [string]$Owner = "@me",
    [string]$Title = "Pilotage - plateforme data chaîne du froid",
    [string]$Responsible = "Marc-Alfred FALIGANT",
    [switch]$OpenInBrowser
)

$ErrorActionPreference = "Stop"

function Invoke-Gh {
    param([Parameter(Mandatory)][string[]]$Arguments)

    & $script:GitHubCli @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "La commande gh a échoué : gh $($Arguments -join ' ')"
    }
}

function Get-ProjectField {
    param(
        [Parameter(Mandatory)][object[]]$Fields,
        [Parameter(Mandatory)][string]$Name
    )

    $field = $Fields | Where-Object { $_.name -eq $Name } | Select-Object -First 1
    if (-not $field) {
        throw "Champ GitHub Projects introuvable : $Name"
    }
    return $field
}

$githubCliCommand = Get-Command gh -ErrorAction SilentlyContinue
if ($githubCliCommand) {
    $script:GitHubCli = $githubCliCommand.Source
}
elseif (Test-Path -LiteralPath "C:\Program Files\GitHub CLI\gh.exe") {
    $script:GitHubCli = "C:\Program Files\GitHub CLI\gh.exe"
}
else {
    throw "GitHub CLI est introuvable. Installez-le puis relancez ce script."
}

Invoke-Gh -Arguments @("auth", "status")

$existingProjects = (Invoke-Gh -Arguments @("project", "list", "--owner", $Owner, "--limit", "100", "--format", "json") | ConvertFrom-Json).projects
$project = $existingProjects | Where-Object { $_.title -eq $Title } | Select-Object -First 1

if (-not $project) {
    $projectNumber = (Invoke-Gh -Arguments @("project", "create", "--owner", $Owner, "--title", $Title, "--format", "json", "--jq", ".number")).Trim()
    $projectReadme = @"
# Pilotage

Tableau de suivi des jalons, responsables, échéances et preuves de recette.
"@
    Invoke-Gh -Arguments @(
        "project", "edit", $projectNumber, "--owner", $Owner, "--visibility", "PRIVATE",
        "--description", "Pilotage des livrables et des preuves de validation de la plateforme data.",
        "--readme", $projectReadme
    ) | Out-Null
}
else {
    $projectNumber = [string]$project.number
}

$projectDetails = Invoke-Gh -Arguments @("project", "view", $projectNumber, "--owner", $Owner, "--format", "json") | ConvertFrom-Json
$projectId = $projectDetails.id

$fieldDefinitions = @(
    @{ Name = "Jalon"; DataType = "SINGLE_SELECT"; Options = "Bloc I,Bloc II,Bloc III,Bloc IV,Soutenance" },
    @{ Name = "Statut de preuve"; DataType = "SINGLE_SELECT"; Options = "Terminé,En cours,À faire" },
    @{ Name = "Responsable"; DataType = "TEXT"; Options = $null },
    @{ Name = "Échéance"; DataType = "DATE"; Options = $null }
)

$fields = (Invoke-Gh -Arguments @("project", "field-list", $projectNumber, "--owner", $Owner, "--limit", "100", "--format", "json") | ConvertFrom-Json).fields
foreach ($definition in $fieldDefinitions) {
    if (-not ($fields | Where-Object { $_.name -eq $definition.Name })) {
        $arguments = @("project", "field-create", $projectNumber, "--owner", $Owner, "--name", $definition.Name, "--data-type", $definition.DataType)
        if ($definition.Options) {
            $arguments += @("--single-select-options", $definition.Options)
        }
        Invoke-Gh -Arguments $arguments | Out-Null
    }
}

$fields = (Invoke-Gh -Arguments @("project", "field-list", $projectNumber, "--owner", $Owner, "--limit", "100", "--format", "json") | ConvertFrom-Json).fields
$milestoneField = Get-ProjectField -Fields $fields -Name "Jalon"
$nativeStatusField = Get-ProjectField -Fields $fields -Name "Status"
$statusField = Get-ProjectField -Fields $fields -Name "Statut de preuve"
$responsibleField = Get-ProjectField -Fields $fields -Name "Responsable"
$dueDateField = Get-ProjectField -Fields $fields -Name "Échéance"

$workItems = @(
    @{ Id = "PIL-01"; Title = "Cadrage, risques et gouvernance"; Milestone = "Bloc III"; Status = "Terminé"; Due = "2026-06-05" },
    @{ Id = "PIL-02"; Title = "Contrat d'événements et acquisition MQTT"; Milestone = "Bloc I"; Status = "Terminé"; Due = "2026-06-20" },
    @{ Id = "PIL-03"; Title = "Stockage raw et chargement idempotent"; Milestone = "Bloc I"; Status = "Terminé"; Due = "2026-06-27" },
    @{ Id = "PIL-04"; Title = "Transformations dbt et contrôles qualité"; Milestone = "Bloc II"; Status = "Terminé"; Due = "2026-07-07" },
    @{ Id = "PIL-05"; Title = "Kafka, Airflow, Spark et observabilité"; Milestone = "Bloc IV"; Status = "Terminé"; Due = "2026-07-24" },
    @{ Id = "PIL-06"; Title = "Collecte API Open-Meteo et traçabilité brute"; Milestone = "Bloc I"; Status = "Terminé"; Due = "2026-09-07" },
    @{ Id = "PIL-07"; Title = "Exécution distante CI/CD et artefacts"; Milestone = "Bloc IV"; Status = "Terminé"; Due = "2026-09-07" },
    @{ Id = "PIL-08"; Title = "Recette finale et constitution des preuves"; Milestone = "Soutenance"; Status = "À faire"; Due = "2026-09-11" }
)

$existingItems = (Invoke-Gh -Arguments @("project", "item-list", $projectNumber, "--owner", $Owner, "--limit", "100", "--format", "json") | ConvertFrom-Json).items

foreach ($workItem in $workItems) {
    $marker = "[$($workItem.Id)]"
    $itemTitle = "$marker $($workItem.Title)"
    $itemBody = "Responsable : $Responsible`nJalon : $($workItem.Milestone)`nÉchéance : $($workItem.Due)`nStatut : $($workItem.Status)"
    $alreadyPresent = $existingItems | Where-Object { $_.content.title.Contains($marker) } | Select-Object -First 1
    if ($alreadyPresent) {
        Write-Host "Déjà présent : $marker"
        $itemId = $alreadyPresent.id
        Invoke-Gh -Arguments @(
            "api", "graphql",
            "-f", 'query=mutation($draftIssueId:ID!,$title:String,$body:String){updateProjectV2DraftIssue(input:{draftIssueId:$draftIssueId,title:$title,body:$body}){draftIssue{id}}}',
            "-F", "draftIssueId=$($alreadyPresent.content.id)",
            "-F", "title=$itemTitle",
            "-F", "body=$itemBody"
        ) | Out-Null
    }
    else {
        $itemId = (Invoke-Gh -Arguments @("project", "item-create", $projectNumber, "--owner", $Owner, "--title", $itemTitle, "--body", $itemBody, "--format", "json", "--jq", ".id")).Trim()
    }

    $milestoneOption = $milestoneField.options | Where-Object { $_.name -eq $workItem.Milestone } | Select-Object -First 1
    $statusOption = $statusField.options | Where-Object { $_.name -eq $workItem.Status } | Select-Object -First 1
    $nativeStatusName = switch ($workItem.Status) {
        "Terminé" { "Done" }
        "En cours" { "In Progress" }
        default { "Todo" }
    }
    $nativeStatusOption = $nativeStatusField.options | Where-Object { $_.name -eq $nativeStatusName } | Select-Object -First 1
    if (-not $milestoneOption -or -not $statusOption -or -not $nativeStatusOption) {
        throw "Option de champ introuvable pour $marker"
    }

    Invoke-Gh -Arguments @("project", "item-edit", "--id", $itemId, "--project-id", $projectId, "--field-id", $milestoneField.id, "--single-select-option-id", $milestoneOption.id) | Out-Null
    Invoke-Gh -Arguments @("project", "item-edit", "--id", $itemId, "--project-id", $projectId, "--field-id", $nativeStatusField.id, "--single-select-option-id", $nativeStatusOption.id) | Out-Null
    Invoke-Gh -Arguments @("project", "item-edit", "--id", $itemId, "--project-id", $projectId, "--field-id", $statusField.id, "--single-select-option-id", $statusOption.id) | Out-Null
    Invoke-Gh -Arguments @("project", "item-edit", "--id", $itemId, "--project-id", $projectId, "--field-id", $responsibleField.id, "--text", $Responsible) | Out-Null
    Invoke-Gh -Arguments @("project", "item-edit", "--id", $itemId, "--project-id", $projectId, "--field-id", $dueDateField.id, "--date", $workItem.Due) | Out-Null
}

Write-Host "Projet GitHub prêt : $($projectDetails.url)"
Write-Host "Capture à prendre : vue Table avec les colonnes Jalon, Statut de preuve, Responsable et Échéance."

if ($OpenInBrowser) {
    Invoke-Gh -Arguments @("project", "view", $projectNumber, "--owner", $Owner, "--web")
}
