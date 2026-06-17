<#
  Instalador do getex para Windows (PowerShell).

  Como rodar (no PowerShell, dentro da pasta do projeto):
      powershell -ExecutionPolicy Bypass -File .\install.ps1

  O que faz:
    1. Encontra o Python 3.
    2. Instala as dependências: windows-curses (curses no Windows) e firebase-admin.
    3. Copia o getex.py para %LOCALAPPDATA%\getex e cria um atalho 'getex.bat'.
    4. Adiciona essa pasta ao PATH do usuário.
    5. Prepara a pasta da credencial do Firebase.
#>

$ErrorActionPreference = "Stop"
function Say  ($m) { Write-Host $m -ForegroundColor Green }
function Warn ($m) { Write-Host $m -ForegroundColor Yellow }
function Err  ($m) { Write-Host $m -ForegroundColor Red }

Say "==> Instalando o getex (Windows)"

# 1. Python 3 ----------------------------------------------------------------
$python = $null
foreach ($c in @("python", "py")) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) { $python = $cmd.Source; break }
}
if (-not $python) {
    Err "Python 3 nao encontrado. Instale em https://www.python.org/downloads/ (marque 'Add to PATH')."
    exit 1
}
Say ("✓ Python: " + (& $python --version))

# 2. Dependencias ------------------------------------------------------------
Say "==> Instalando dependencias (windows-curses, firebase-admin)..."
try {
    & $python -m pip install --user windows-curses firebase-admin
    Say "✓ Dependencias instaladas"
} catch {
    Warn "⚠ Falha ao instalar dependencias automaticamente."
    Warn "  Rode manualmente:  $python -m pip install --user windows-curses firebase-admin"
}

# 3. Instala o getex como comando -------------------------------------------
$dir = Join-Path $env:LOCALAPPDATA "getex"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

$src = Join-Path $PSScriptRoot "getex.py"
if (-not (Test-Path $src)) { $src = Join-Path $PSScriptRoot "getex" }
if (-not (Test-Path $src)) { Err "getex.py nao encontrado ao lado do install.ps1"; exit 1 }
Copy-Item $src (Join-Path $dir "getex.py") -Force

$bat = Join-Path $dir "getex.bat"
"@echo off`r`n`"$python`" `"%~dp0getex.py`" %*" | Set-Content -Encoding ASCII -Path $bat
Say "✓ Comando 'getex' instalado em $dir"

# 4. PATH do usuario ---------------------------------------------------------
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$dir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$dir", "User")
    Warn "PATH atualizado — ABRA UM NOVO terminal para o comando 'getex' funcionar."
}

# 5. Pasta da credencial -----------------------------------------------------
$cred = Join-Path $env:USERPROFILE ".getex\firebase"
New-Item -ItemType Directory -Force -Path $cred | Out-Null
$credFile = Join-Path $cred "service-account.json"
if (Test-Path $credFile) {
    Say "✓ Credencial Firebase ja presente"
} else {
    Warn "Para login/sincronizacao, coloque a credencial do Firebase em:"
    Warn "    $credFile"
    Warn "(peca o arquivo service-account.json ao dono do projeto)"
}

Write-Host ""
Say "Pronto! Abra um NOVO terminal e rode:  getex"
Say "Navegador de arquivos:                 getex get all"
