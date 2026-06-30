<#
  Instalador do getex para Windows (PowerShell).

  Como rodar (no PowerShell, dentro da pasta do projeto):
      powershell -ExecutionPolicy Bypass -File .\install.ps1

  O que faz:
    1. Encontra o Python 3.
    2. Instala a dependencia windows-curses (curses no Windows).
    3. Copia o getex.py para %LOCALAPPDATA%\getex e cria um atalho 'getex.bat'.
    4. Adiciona essa pasta ao PATH do usuario.

  Login/sincronizacao funcionam direto, sem configurar nada: o getex ja vem
  apontando para o servidor na nuvem (getex.zina.dev.br). Para usar outro
  servidor, defina a variavel de ambiente GETEX_API_URL.

  Observacao: este arquivo e mantido em ASCII puro de proposito, para o
  Windows PowerShell 5.1 (que le scripts como ANSI por padrao) nao corromper
  caracteres acentuados/unicode.
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
$ver = (& $python --version)
Say ("[OK] Python: " + $ver)

# 2. Dependencia (apenas windows-curses) -------------------------------------
Say "==> Instalando dependencia (windows-curses)..."
try {
    & $python -m pip install --user windows-curses
    Say "[OK] Dependencia instalada"
} catch {
    Warn "[!] Falha ao instalar windows-curses automaticamente."
    Warn ("    Rode manualmente: " + $python + " -m pip install --user windows-curses")
}

# 3. Instala o getex como comando -------------------------------------------
$dir = Join-Path $env:LOCALAPPDATA "getex"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

$src = Join-Path $PSScriptRoot "getex.py"
if (-not (Test-Path $src)) { $src = Join-Path $PSScriptRoot "getex" }
if (-not (Test-Path $src)) { Err "getex.py nao encontrado ao lado do install.ps1"; exit 1 }
Copy-Item $src (Join-Path $dir "getex.py") -Force

# cria o atalho getex.bat (conteudo em ASCII)
$bat = Join-Path $dir "getex.bat"
$batLines = @(
    "@echo off",
    ('"' + $python + '" "%~dp0getex.py" %*')
)
Set-Content -Encoding ASCII -Path $bat -Value $batLines
Say ("[OK] Comando 'getex' instalado em " + $dir)

# 4. PATH do usuario ---------------------------------------------------------
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$dir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$dir", "User")
    Warn "PATH atualizado -- ABRA UM NOVO terminal para o comando 'getex' funcionar."
}

Write-Host ""
Say "Pronto! Abra um NOVO terminal e rode:  getex"
Say "Navegador de arquivos:                 getex get all"
Say "No primeiro uso com internet, crie sua conta na tela de login (workspace/email/senha)."
