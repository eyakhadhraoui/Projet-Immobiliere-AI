[CmdletBinding()]
param(
    [switch]$Arreter
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $ScriptDir "tmp\demarrer-pids.json"

if ($Arreter) {
    if (-not (Test-Path $PidFile)) {
        Write-Host "Aucun fichier de PID trouvé ($PidFile). Rien à arrêter." -ForegroundColor Yellow
        exit 0
    }
    try {
        $pids = Get-Content $PidFile -Raw | ConvertFrom-Json
        foreach ($procId in $pids) {
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "Arrêt du processus $procId ($($proc.ProcessName))..." -ForegroundColor Cyan
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        Write-Host "Processus arrêtés avec succès." -ForegroundColor Green
    } catch {
        Write-Warning "Erreur lors de l'arrêt des processus : $_"
    }
    exit 0
}

# Vérification de disponibilité des ports
function Test-PortOccupied([int]$port) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return ($null -ne $connections)
}

if (Test-PortOccupied 5000) {
    Write-Error "Le port 5000 (backend) est déjà utilisé. Arrêtez le serveur existant ou utilisez un autre port."
    exit 1
}

if (Test-PortOccupied 5173) {
    Write-Error "Le port 5173 (frontend) est déjà utilisé. Arrêtez le serveur existant ou utilisez un autre port."
    exit 1
}

New-Item -ItemType Directory -Path (Join-Path $ScriptDir "tmp") -Force | Out-Null

Write-Host "Démarrage du backend Flask sur le port 5000..." -ForegroundColor Cyan
$BackendCmd = "cd '$ScriptDir\backend'; .\venv\Scripts\Activate.ps1; python run.py"
$backendProc = Start-Process powershell -ArgumentList "-NoExit", "-Command", $BackendCmd -PassThru

Write-Host "Démarrage du frontend Vite sur le port 5173..." -ForegroundColor Cyan
$FrontendCmd = "cd '$ScriptDir\frontend'; npm run dev"
$frontendProc = Start-Process powershell -ArgumentList "-NoExit", "-Command", $FrontendCmd -PassThru

$savedPids = @($backendProc.Id, $frontendProc.Id)
$savedPids | ConvertTo-Json | Set-Content $PidFile -Encoding UTF8

Write-Host "Attente du backend (http://127.0.0.1:5000/api/health)..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/health" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($res.status -eq "ok") {
            $ready = $true
            break
        }
    } catch {
        # Attente du démarrage de Flask
    }
}

if ($ready) {
    Write-Host "Backend et frontend prêts !" -ForegroundColor Green
    Write-Host "Ouverture du site http://localhost:5173..." -ForegroundColor Cyan
    Start-Process "http://localhost:5173"
    Write-Host "Pour arrêter les serveurs : .\demarrer.ps1 -Arreter" -ForegroundColor Yellow
} else {
    Write-Warning "Le backend n'a pas répondu dans le délai imparti. Vérifiez les fenêtres ouvertes."
}
