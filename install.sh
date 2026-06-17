#!/usr/bin/env bash
#
# Instalador do getex — funciona em macOS e Linux.
#
#   curl -fsSL .../install.sh | bash      (ou)      ./install.sh
#
# O que faz:
#   1. Verifica o Python 3.
#   2. Instala o firebase-admin (opcional — para login/sincronização).
#   3. Copia o getex.py para /usr/local/bin/getex e o torna executável.
#   4. Prepara ~/.getex/firebase para a credencial do Firebase.
#
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

# ── 2. firebase-admin (opcional) ─────────────────────────────────────────────
say "==> Instalando firebase-admin (para login/sincronização)..."
if python3 -c "import firebase_admin" >/dev/null 2>&1; then
    say "✓ firebase-admin já instalado"
else
    if python3 -m pip install --user firebase-admin >/dev/null 2>&1; then
        say "✓ firebase-admin instalado"
    elif python3 -m pip install --user --break-system-packages firebase-admin >/dev/null 2>&1; then
        say "✓ firebase-admin instalado (--break-system-packages)"
    else
        warn "⚠ Não consegui instalar o firebase-admin automaticamente."
        warn "  O getex vai funcionar em MODO LOCAL (sem login/sync)."
        warn "  Para habilitar a nuvem, rode manualmente:"
        warn "    python3 -m pip install --user firebase-admin"
    fi
fi

# ── 3. Localiza o getex.py e instala como comando global ─────────────────────
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

# ── 4. Pasta da credencial do Firebase ───────────────────────────────────────
mkdir -p "$HOME/.getex/firebase"
chmod 700 "$HOME/.getex" "$HOME/.getex/firebase" 2>/dev/null || true
CRED="$HOME/.getex/firebase/service-account.json"
echo
if [ -f "$CRED" ]; then
    say "✓ Credencial Firebase já presente em $CRED"
else
    warn "Para login e sincronização na nuvem, coloque a credencial do Firebase em:"
    warn "    $CRED"
    warn "Peça esse arquivo (service-account.json) ao dono do projeto e rode:"
    warn "    chmod 600 $CRED"
fi

echo
say "Pronto! Abra o editor com:  getex"
say "Navegador de arquivos:      getex get all"
