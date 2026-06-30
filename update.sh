#!/usr/bin/env bash
#
# Atualizador do getex — puxa a versão mais recente do GitHub.
#
#   ./update.sh                                  (dentro do repo clonado)
#   curl -fsSL .../update.sh | bash              (sem ter o repo)
#
# Funciona dos dois jeitos:
#   • Se rodado dentro do clone do repositório → faz `git pull` e reinstala.
#   • Caso contrário → baixa o getex.py mais recente direto do GitHub.
set -e

REPO_RAW="https://raw.githubusercontent.com/vinisoaresdef/GETEX/main/getex.py"

GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; RED=$'\033[0;31m'; NC=$'\033[0m'
say()  { printf "%s%s%s\n" "$GREEN" "$1" "$NC"; }
warn() { printf "%s%s%s\n" "$YELLOW" "$1" "$NC"; }
err()  { printf "%s%s%s\n" "$RED" "$1" "$NC"; }

say "==> Atualizando o getex"

if ! command -v python3 >/dev/null 2>&1; then
    err "Python 3 não encontrado — rode o install.sh primeiro."
    exit 1
fi

# Onde o getex está instalado hoje (senão, o padrão do install.sh).
DEST="$(command -v getex 2>/dev/null || true)"
[ -z "$DEST" ] && DEST="/usr/local/bin/getex"

# Copia preservando permissão e usando sudo só se necessário.
install_to_dest() {
    local src="$1"
    if [ -w "$(dirname "$DEST")" ]; then
        cp "$src" "$DEST" && chmod +x "$DEST"
    else
        warn "  (precisa de sudo para escrever em $DEST)"
        sudo cp "$src" "$DEST" && sudo chmod +x "$DEST"
    fi
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"

if [ -n "$SCRIPT_DIR" ] && git -C "$SCRIPT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    # ── Caso 1: rodando dentro do repositório clonado ────────────────────────
    say "==> Repositório detectado em $SCRIPT_DIR — git pull"
    if ! git -C "$SCRIPT_DIR" pull --ff-only; then
        err "Falha no git pull (há alterações locais não commitadas?)."
        err "Resolva e rode de novo, ou use o modo download:  curl -fsSL $REPO_RAW | ..."
        exit 1
    fi
    SRC="$SCRIPT_DIR/getex.py"
    [ -f "$SRC" ] || SRC="$SCRIPT_DIR/getex"
    [ -f "$SRC" ] || { err "getex.py não encontrado no repositório."; exit 1; }
    install_to_dest "$SRC"
else
    # ── Caso 2: sem repositório — baixa o getex.py do GitHub ──────────────────
    say "==> Baixando a versão mais recente do GitHub"
    TMP="$(mktemp)"
    trap 'rm -f "$TMP"' EXIT
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$REPO_RAW" -o "$TMP"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$TMP" "$REPO_RAW"
    else
        err "Preciso de curl ou wget para baixar."
        exit 1
    fi
    # Sanidade: tem que compilar antes de instalar por cima do atual.
    if ! python3 -m py_compile "$TMP" 2>/dev/null; then
        err "O arquivo baixado não é um getex.py válido — abortando (nada foi alterado)."
        exit 1
    fi
    install_to_dest "$TMP"
fi

say "✓ getex atualizado em $DEST"
say "  $(getex --help >/dev/null 2>&1 && echo 'pronto para uso' || echo 'instalado')"
