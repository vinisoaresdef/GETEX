<#
  Atualizador do getex para Windows (PowerShell).

  Como rodar:
      powershell -ExecutionPolicy Bypass -File .\update.ps1        (dentro do repo clonado)
      powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/vinisoaresdef/GETEX/main/update.ps1 | iex"

  Funciona dos dois jeitos:
    - Dentro do clone do repositorio -> faz `git pull` e reinstala.
    - Sem o repo -> baixa o getex.py mais recente do GitHub.

  Observacao: ASCII puro de proposito (PowerShell 5.1 le scripts como ANSI).
#>

$ErrorActionPreference = "Stop"
function Say  ($m) { Write-Host $m -ForegroundColor Green }
function Warn ($m) { Write-Host $m -ForegroundColor Yellow }
function Err  ($m) { Write-Host $m -ForegroundColor Red }

$REPO_RAW = "https://raw.githubusercontent.com/vinisoaresdef/GETEX/main/getex.py"

Say "==> Atualizando o getex (Windows)"

# Python 3
$python = $null
foreach ($c in @("python", "py")) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) { $python = $cmd.Source; break }
}
if (-not $python) {
    Err "Python 3 nao encontrado -- rode o install.ps1 primeiro."
    exit 1
}

# Pasta de instalacao (mesma do install.ps1)
$dir  = Join-Path $env:LOCALAPPDATA "getex"
$dest = Join-Path $dir "getex.py"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

# Roda um comando nativo (git/python) sem que o stderr vire erro fatal --
# pegadinha do PowerShell com $ErrorActionPreference='Stop'. Mostra a saida e
# devolve o exit code. Use -Quiet para suprimir a saida (deteccoes).
function Invoke-Native {
    param([string[]]$Cmd, [switch]$Quiet)
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $rest = @($Cmd[1..($Cmd.Count - 1)])
    if ($Quiet) {
        & $Cmd[0] @rest 2>&1 | Out-Null
    } else {
        & $Cmd[0] @rest 2>&1 | ForEach-Object { Write-Host $_ }
    }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $old
    return $code
}

$inRepo = $false
if ($PSScriptRoot) {
    if ((Invoke-Native -Quiet -Cmd @("git", "-C", $PSScriptRoot, "rev-parse", "--is-inside-work-tree")) -eq 0) {
        $inRepo = $true
    }
}

if ($inRepo) {
    # Caso 1: dentro do repositorio clonado
    Say ("==> Repositorio detectado em " + $PSScriptRoot + " -- git pull")
    if ((Invoke-Native -Cmd @("git", "-C", $PSScriptRoot, "pull", "--ff-only")) -ne 0) {
        Err "Falha no git pull (ha alteracoes locais nao commitadas?)."
        exit 1
    }
    $src = Join-Path $PSScriptRoot "getex.py"
    if (-not (Test-Path $src)) { $src = Join-Path $PSScriptRoot "getex" }
    if (-not (Test-Path $src)) { Err "getex.py nao encontrado no repositorio."; exit 1 }
    Copy-Item $src $dest -Force
} else {
    # Caso 2: sem repositorio -- baixa o getex.py do GitHub
    Say "==> Baixando a versao mais recente do GitHub"
    $tmp = [System.IO.Path]::GetTempFileName()
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $REPO_RAW -OutFile $tmp
        # Sanidade: tem que compilar antes de instalar por cima do atual.
        if ((Invoke-Native -Quiet -Cmd @($python, "-m", "py_compile", $tmp)) -ne 0) {
            Err "O arquivo baixado nao e um getex.py valido -- abortando (nada foi alterado)."
            exit 1
        }
        Copy-Item $tmp $dest -Force
    } finally {
        Remove-Item $tmp -ErrorAction SilentlyContinue
    }
}

Say ("[OK] getex atualizado em " + $dest)
