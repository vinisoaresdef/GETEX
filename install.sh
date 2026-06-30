#!/usr/bin/env bash
#
# Instalador do getex — funciona em macOS e Linux.
#
#   curl -fsSL .../install.sh | bash      (ou)      ./install.sh
#
# O que faz:
#   1. Verifica o Python 3.
#   2. Copia o getex.py para /usr/local/bin/getex e o torna executável.
#
# Login/sincronização funcionam direto, sem configurar nada: o getex já vem
# apontando para o servidor na nuvem (getex.zina.dev.br). Para usar outro
# servidor, exporte GETEX_API_URL antes de rodar o getex.
set -e

GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; RED=$'\033[0;31m'; NC=$'\033[0m'
say()  { printf "%s%s%s\n" "$GREEN" "$1" "$NC"; }
warn() { printf "%s%s%s\n" "$YELLOW" "$1" "$NC"; }
err()  { printf "%s%s%s\n" "$RED" "$1" "$NC"; }

OS="$(uname -s)"
say "==> Instalando o getex ($OS)"

# ── 1. Python 3 ──────────────────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
    err "Python 3 não encontrado."
    if [ "$OS" = "Darwin" ]; then
        warn "No macOS, instale com:  xcode-select --install   (ou: brew install python)"
    else
        warn "No Linux, instale com:  sudo apt install python3"
    fi
    exit 1
fi
say "✓ $(python3 --version)"
say "  (sem dependências: o getex usa só a biblioteca padrão do Python)"

# ── 2. Localiza o getex.py e instala como comando global ─────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
SRC=""
for cand in "$SCRIPT_DIR/getex.py" "$SCRIPT_DIR/getex" "./getex.py" "./getex"; do
    [ -f "$cand" ] && { SRC="$cand"; break; }
done
if [ -z "$SRC" ]; then
    err "getex.py não encontrado ao lado deste script."
    exit 1
fi

DEST="/usr/local/bin/getex"
say "==> Instalando em $DEST"
if [ -w "$(dirname "$DEST")" ]; then
    cp "$SRC" "$DEST" && chmod +x "$DEST"
else
    warn "  (precisa de sudo para escrever em /usr/local/bin)"
    sudo cp "$SRC" "$DEST" && sudo chmod +x "$DEST"
fi
say "✓ Comando 'getex' instalado"

echo
say "Pronto! Abra o editor com:  getex"
say "Navegador de arquivos:      getex get all"
say "No primeiro uso com internet, crie sua conta na tela de login (workspace/email/senha)."
