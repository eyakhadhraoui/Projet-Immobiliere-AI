[CmdletBinding()]
param(
    [switch]$Supprimer
)

$ErrorActionPreference = "Stop"
$TaskName = "ImmoAnnonces-Entrainement-Absence-Visites"
$BackendDir = $PSScriptRoot
$Python = Join-Path $BackendDir "venv\Scripts\python.exe"

if ($Supprimer) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Tâche quotidienne supprimée : $TaskName"
    exit 0
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Interpréteur du projet introuvable : $Python"
}

$Action = New-ScheduledTaskAction -Execute $Python `
    -Argument "-m flask --app run entrainer-absence-visites" `
    -WorkingDirectory $BackendDir
$Trigger = New-ScheduledTaskTrigger -Daily -At "2:00 AM"
$Principal = New-ScheduledTaskPrincipal `
    -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName `
    -Description "Réentraîne chaque nuit le modèle local de prédiction des absences aux visites." `
    -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force -ErrorAction Stop | Out-Null
Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop
Write-Host "Tâche quotidienne enregistrée et entraînement initial lancé : $TaskName (02:00)."
