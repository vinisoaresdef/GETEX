<#
  Instalador do getex para Windows (PowerShell).

  Como rodar (no PowerShell, dentro da pasta do projeto):
      powershell -ExecutionPolicy Bypass -File .\install.ps1

  O que faz:
    1. Encontra o Python 3.
    2. Copia o getex.py para %LOCALAPPDATA%\getex e cria um atalho 'getex.bat'.
    3. Adiciona essa pasta ao PATH do usuario.
    4. Instala a dependencia windows-curses (curses no Windows). Se o pip falhar,
       o getex ja fica instalado e o passo de curses pode ser refeito a mao.

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

# 2. Instala o getex como comando -------------------------------------------
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

# 3. PATH do usuario ---------------------------------------------------------
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$dir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$dir", "User")
    Warn "PATH atualizado -- ABRA UM NOVO terminal para o comando 'getex' funcionar."
}

# 4. windows-curses (tolerante a falha) --------------------------------------
# O curses nao e nativo no Windows. Tentamos instalar, mas SEM abortar o
# install caso o pip esteja com problema: o getex ja foi instalado acima.
function Test-Curses {
    & $python -c "import curses" 2>$null
    return ($LASTEXITCODE -eq 0)
}

if (Test-Curses) {
    Say "[OK] windows-curses ja disponivel"
} else {
    Say "==> Instalando dependencia (windows-curses)..."
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $python -m pip install --user windows-curses 2>&1 | Out-Null } catch { }
    if (-not (Test-Curses)) {
        # fallback: sem --user
        try { & $python -m pip install windows-curses 2>&1 | Out-Null } catch { }
    }
    $ErrorActionPreference = $prev

    if (Test-Curses) {
        Say "[OK] windows-curses instalado"
    } else {
        Warn "[!] Nao consegui instalar o windows-curses automaticamente (pip com problema?)."
        Warn "    O comando 'getex' ja esta instalado; para o curses funcionar, rode:"
        Warn "      python -m ensurepip --upgrade"
        Warn "      python -m pip install --upgrade pip"
        Warn "      python -m pip install --user windows-curses"
    }
}

Write-Host ""
Say "Pronto! Abra um NOVO terminal e rode:  getex"
Say "Navegador de arquivos:                 getex get all"
Say "No primeiro uso com internet, crie sua conta na tela de login (workspace/email/senha)."
